import asyncio
from datetime import date
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile
import json
import pytest
from pydantic import SecretStr, ValidationError
from openpyxl import Workbook
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
from sqlalchemy import select,func
from app.models.intelligence import IntelligenceDocument as Document, IntelligenceChunk as Chunk, IntelligenceFinding as Finding
from app.services import intelligence as service
from app.services.intelligence_extraction import validate_file,extract,ExtractionError
from app.schemas.intelligence import IntelligenceFindingOutput

TEXT='SYNTHETIC REPORT — NOT REAL MARKET DATA.\nBrent price increased to 82 USD/bbl.\nSupply declined by 2% in Nigeria.'


@pytest.fixture
def private_storage(tmp_path,monkeypatch):
    monkeypatch.setattr(service,'storage_root',lambda:tmp_path)
    return tmp_path


@pytest.fixture
def admin_headers(monkeypatch):
    import app.api.intelligence as api
    monkeypatch.setattr(api,'get_settings',lambda:SimpleNamespace(shipping_admin_token=SecretStr('test-private'),intelligence_max_upload_mb=20))
    return {'x-intelligence-admin-token':'test-private'}


def pdf_fixture():
    writer=PdfWriter();page=writer.add_blank_page(width=500,height=700)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 40 650 Td (Synthetic Brent price increased to 82 USD/bbl.) Tj ET')
    page[NameObject('/Contents')]=writer._add_object(stream)
    output=BytesIO();writer.write(output);return output.getvalue()


def docx_fixture():
    output=BytesIO()
    with ZipFile(output,'w') as z:
        z.writestr('[Content_Types].xml','<Types/>')
        z.writestr('word/document.xml',"""<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Synthetic outlook</w:t></w:r></w:p><w:p><w:r><w:t>Brent price increased to 82 USD/bbl.</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Supply declined by 2%.</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>""")
    return output.getvalue()


def xlsx_fixture():
    w=Workbook();w.active.title='Synthetic prices';w.active.append(['Commodity','Price']);w.active.append(['Brent',82]);w.active.append(['Zero',0]);o=BytesIO();w.save(o);return o.getvalue()


@pytest.mark.parametrize('kind,content,locator',[('PDF',pdf_fixture(),'PDF page 1'),('DOCX',docx_fixture(),'DOCX paragraph 2'),('XLSX',xlsx_fixture(),'XLSX sheet Synthetic prices'),('CSV',b'Commodity,Price\nBrent,82\nZero,0','CSV row 2'),('TXT',TEXT.encode(),'TXT lines 1')])
def test_format_extraction_and_real_locators(kind,content,locator):
    chunks,limitations=extract(content,kind)
    assert chunks and any(locator in c['source_locator'] for c in chunks)
    assert any('82' in c['text_content'] for c in chunks)
    if kind=='PDF':assert chunks[0]['page_number']==1
    if kind=='DOCX':assert any(c['chunk_type']=='docx_table' for c in chunks)
    if kind=='XLSX':assert chunks[-1]['structured_data']['cells'][-1]['value']=='0'


def test_validation_filename_mime_and_archive_security():
    name,kind,mime=validate_file('..\\secret.txt',b'hello','text/plain',100)
    assert name=='secret.txt' and kind=='TXT'
    for filename,content,mime in [('fake.pdf',b'not PDF','application/pdf'),('evil.exe',b'test','application/octet-stream'),('file.txt',b'hello','application/pdf'),('file.txt',b'\x00','text/plain')]:
        with pytest.raises(ExtractionError):validate_file(filename,content,mime,100)
    with pytest.raises(ExtractionError):validate_file('too.txt',b'x'*101,'text/plain',100)
    with pytest.raises(ExtractionError):validate_file('fake.docx',b'PKbad','application/octet-stream',100)


def test_extraction_limitations_and_no_ocr_fabrication():
    w=PdfWriter();w.add_blank_page(width=100,height=100);o=BytesIO();w.write(o)
    with pytest.raises(ExtractionError,match='No readable') as error:extract(o.getvalue(),'PDF')
    assert any('PDF page 1' in note for note in error.value.limitations)
    chunks,notes=extract(('line\n'*100).encode(),'TXT',max_chunks=1)
    assert len(chunks)==1 and any('partial' in note for note in notes)


def finding(document,chunk):
    quote='Brent price increased to 82 USD/bbl.'
    return {'source_organisation':document['source_organisation'],'document_title':document['document_title'],'report_date':document['report_date'],
        'commodity':'Brent','geography':'unspecified','signal_type':'Price','direction':'bullish','time_horizon':'unspecified',
        'key_fact':quote,'relevant_numbers':['82 USD/bbl'],'driver':'Reported price increase','risk_implication':'Higher reported prices may raise purchase costs.',
        'confidence':'low','source_chunk_id':chunk['source_chunk_id'],'source_locator':chunk['source_locator'],'evidence_excerpt':quote}


class FakeGemini:
    async def analyse_intelligence(self,document,chunks):return {'findings':[finding(document,chunks[0])]}


def create(db):
    return service.upload(db,TEXT.encode(),'synthetic.txt','text/plain','Other','Synthetic fixture',None)[0]


def test_processing_states_traceability_duplicates_and_original(private_storage,db_session):
    d=create(db_session);original=service.original_path(d).read_bytes()
    duplicate,reused=service.upload(db_session,TEXT.encode(),'different.txt','text/plain','Other','Different title',date(2026,10,13))
    assert reused and duplicate.id==d.id and duplicate.title=='Synthetic fixture' and duplicate.report_date is None
    assert d.processing_status=='uploaded'
    asyncio.run(service.process(db_session,d.id,extract_only=True))
    assert d.processing_status=='extracted'
    asyncio.run(service.process(db_session,d.id,provider=FakeGemini()))
    assert d.processing_status=='completed' and service.original_path(d).read_bytes()==original
    f=db_session.scalar(select(Finding).where(Finding.document_id==d.id))
    assert f and f.evidence_excerpt in service.chunks_for(db_session,d.id)[0].text_content
    assert f.source_locator.startswith('TXT lines')
    asyncio.run(service.process(db_session,d.id,provider=FakeGemini()))
    assert db_session.scalar(select(func.count()).select_from(Finding))==1
    asyncio.run(service.process(db_session,d.id,reprocess=True,provider=FakeGemini()))
    assert db_session.scalar(select(func.count()).select_from(Finding))==1


def test_taxonomy_and_unsupported_finding_rejection(private_storage,db_session):
    d=create(db_session);asyncio.run(service.process(db_session,d.id,extract_only=True));chunk=service.chunks_for(db_session,d.id)[0]
    metadata={'source_organisation':d.source_organisation,'document_title':d.title,'report_date':None}
    valid=finding(metadata,{'source_chunk_id':chunk.id,'source_locator':chunk.source_locator})
    normalized=IntelligenceFindingOutput.model_validate({**valid,'signal_type':' price ','direction':' BULLISH '})
    assert normalized.signal_type=='Price' and normalized.direction=='bullish'
    invalid=[{**valid,'source_locator':'PDF page 99'},{**valid,'key_fact':'Price increased to 999 USD/bbl.'},
        {**valid,'relevant_numbers':['999 USD/bbl']},{**valid,'risk_implication':'Costs increase by 99%.'},
        {**valid,'report_date':'2026-10-13'},{**valid,'signal_type':'Random taxonomy'},{**valid,'evidence_excerpt':'Invented quotation'}]
    accepted,rejected=service.validate_findings({'findings':[valid,*invalid]},d,[chunk])
    assert len(accepted)==1 and rejected==len(invalid)
    with pytest.raises(ValidationError):IntelligenceFindingOutput.model_validate({**valid,'direction':'upwards'})


def test_failed_ai_recovery_keeps_original_chunks_and_previous_findings(private_storage,db_session):
    class Failed:
        async def analyse_intelligence(self,*args):raise RuntimeError('secret-containing provider payload')
    d=create(db_session);asyncio.run(service.process(db_session,d.id,provider=FakeGemini()))
    count=len(service.chunks_for(db_session,d.id));path=service.original_path(d)
    asyncio.run(service.process(db_session,d.id,reprocess=True,provider=Failed()))
    assert d.processing_status=='failed' and path.exists() and len(service.chunks_for(db_session,d.id))==count
    assert 'secret-containing' not in d.error_message
    assert db_session.scalar(select(func.count()).select_from(Finding))==1
    asyncio.run(service.process(db_session,d.id,provider=FakeGemini()))
    assert d.processing_status=='completed'


def test_upload_api_auth_duplicate_download_and_delete(client,private_storage,admin_headers):
    files={'report':('synthetic.txt',TEXT.encode(),'text/plain')};data={'source_organisation':'Other','title':'Synthetic fixture'}
    assert client.post('/api/intelligence/documents',files=files,data=data).status_code==403
    response=client.post('/api/intelligence/documents',files=files,data=data,headers=admin_headers)
    assert response.status_code==200,response.text
    id=response.json()['document']['id'];assert 'storage_path' not in response.text
    assert client.post('/api/intelligence/documents',files=files,data=data,headers=admin_headers).json()['duplicate'] is True
    original=client.get(f'/api/intelligence/documents/{id}/original',headers=admin_headers)
    assert original.content==TEXT.encode()
    assert client.get(f'/api/intelligence/documents/{id}/original').status_code==403
    extracted=client.post(f'/api/intelligence/documents/{id}/process?extract_only=true',headers=admin_headers)
    assert extracted.json()['processing_status']=='extracted'
    detail=client.get(f'/api/intelligence/documents/{id}').json()
    assert detail['chunks'][0]['source_locator'].startswith('TXT lines')
    assert client.get('/api/intelligence/documents?source=Other').json()
    assert client.get(f'/api/intelligence/documents/{id}/findings').json()==[]
    assert client.delete(f'/api/intelligence/documents/{id}',headers=admin_headers).status_code==200
    assert client.get(f'/api/intelligence/documents/{id}').status_code==404
    assert not list(private_storage.iterdir())


def test_processing_lease_prevents_concurrent_analysis(private_storage,db_session):
    d=create(db_session);d.processing_status='analysing';d.processing_started_at=service.now();db_session.commit()
    with pytest.raises(service.ProcessingConflict):asyncio.run(service.process(db_session,d.id,provider=FakeGemini()))
    with pytest.raises(service.ProcessingConflict):service.delete_document(db_session,d.id)


def test_original_integrity_and_unreadable_file_failure(private_storage,db_session):
    d=create(db_session);service.original_path(d).write_bytes(b'changed')
    asyncio.run(service.process(db_session,d.id,provider=FakeGemini()))
    assert d.processing_status=='failed' and 'integrity' in d.error_message


@pytest.mark.parametrize('invalid',[False,True])
def test_existing_gemini_integration_uses_strict_document_schema(monkeypatch,invalid,caplog):
    from google import genai
    from app.providers.ai.gemini import GeminiProvider
    from app.schemas.intelligence import IntelligenceResponse
    captured={}
    class Models:
        async def generate_content(self,**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text=json.dumps({'unexpected':'private-provider-payload'} if invalid else {'findings':[]}))
    async def close():captured['closed']=True
    fake=SimpleNamespace(aio=SimpleNamespace(models=Models(),aclose=close))
    monkeypatch.setattr(genai,'Client',lambda **kwargs:fake)
    provider=GeminiProvider(api_key='test-key-never-log',model='synthetic-model',timeout_seconds=2)
    if invalid:
        with pytest.raises(ValueError):asyncio.run(provider.analyse_intelligence({'report_date':None},[]))
    else:assert asyncio.run(provider.analyse_intelligence({'report_date':None},[]))=={'findings':[]}
    assert captured['closed']
    assert 'additionalProperties' not in str(captured['config'].response_schema)
    assert captured['config'].response_schema is not None
    assert 'private-provider-payload' not in caplog.text and 'test-key-never-log' not in caplog.text


def test_revisions_are_separate_and_completed_document_deletion_cascades(private_storage,db_session):
    first=create(db_session)
    revision,duplicate=service.upload(db_session,(TEXT+'\nRevision: inventory unchanged.').encode(),'revision.txt','text/plain','Other','Revised synthetic',None)
    assert not duplicate and revision.id!=first.id and revision.file_hash!=first.file_hash
    asyncio.run(service.process(db_session,first.id,provider=FakeGemini()))
    path=service.original_path(first);assert path.exists()
    service.delete_document(db_session,first.id)
    assert not path.exists() and db_session.get(Document,first.id) is None
    assert db_session.scalar(select(func.count()).select_from(Finding))==0
    assert db_session.scalar(select(func.count()).select_from(Chunk).where(Chunk.document_id==first.id))==0
    assert service.original_path(revision).exists()


def test_processing_state_is_analysing_during_provider_request(private_storage,db_session):
    d=create(db_session)
    class Probe(FakeGemini):
        async def analyse_intelligence(self,*args):
            assert db_session.get(Document,d.id).processing_status=='analysing'
            assert service.chunks_for(db_session,d.id)
            return await super().analyse_intelligence(*args)
    asyncio.run(service.process(db_session,d.id,provider=Probe()))
    assert d.processing_status=='completed'


def test_office_traversal_macro_and_xml_entities_are_rejected():
    for extra in ['../outside.txt','xl/vbaProject.bin']:
        output=BytesIO()
        with ZipFile(output,'w') as z:
            z.writestr('[Content_Types].xml','<Types/>');z.writestr('xl/workbook.xml','<workbook/>');z.writestr(extra,'unsafe')
        with pytest.raises(ExtractionError):validate_file('unsafe.xlsx',output.getvalue(),'application/octet-stream',10000)
    output=BytesIO()
    with ZipFile(output,'w') as z:
        z.writestr('[Content_Types].xml','<Types/>')
        z.writestr('word/document.xml','<!DOCTYPE doc [<!ENTITY x "unsafe">]><doc/>')
    with pytest.raises(ExtractionError,match='DTD'):extract(output.getvalue(),'DOCX')
