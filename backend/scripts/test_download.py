"""
Test downloading NBS files using requests Session with headers and cookies.
"""
import requests
import zipfile
import io

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://microdata.nigerianstat.gov.ng/index.php/catalog/154/related-materials",
})

print("1. Visiting catalog page...")
res = session.get("https://microdata.nigerianstat.gov.ng/index.php/catalog/154/related-materials", verify=False, timeout=30)
print(f"Catalog status: {res.status_code}, cookies: {dict(session.cookies)}")

print("2. Downloading download/1435...")
dl_res = session.get("https://microdata.nigerianstat.gov.ng/index.php/catalog/154/download/1435", verify=False, timeout=45)
print(f"Download status: {dl_res.status_code}, content length: {len(dl_res.content)}, content type: {dl_res.headers.get('Content-Type')}")

if dl_res.status_code == 200 and len(dl_res.content) > 1000:
    try:
        zf = zipfile.ZipFile(io.BytesIO(dl_res.content))
        print("ZIP contents:", zf.namelist())
    except Exception as e:
        print("Not a zip:", e, dl_res.content[:200])
