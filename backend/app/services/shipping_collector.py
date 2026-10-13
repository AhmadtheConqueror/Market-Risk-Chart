"""One standalone listener, bounded queue, batched persistence and heartbeat."""
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import logging
import random
import uuid
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import tempfile

from sqlalchemy import text
from sqlalchemy.orm import Session
from websockets.asyncio.client import connect
from app.config import get_settings
from app.db.session import get_engine
from app.models.shipping import ShippingCollectorState as State
from app.services.shipping_normalization import normalize, TYPES, BOX
from app.services.shipping import persist_messages, sweep_rules, prune_positions

URL="wss://stream.aisstream.io/v0/stream"


def backoff(attempt): return min(60,2**min(attempt,6))+random.uniform(0,0.5)


@contextmanager
def singleton(engine):
    """Session advisory lock across hosts on PostgreSQL; OS lock for local SQLite."""
    if engine.dialect.name=="postgresql":
        connection=engine.connect()
        try:
            if not connection.execute(text("SELECT pg_try_advisory_lock(794218503)")).scalar():
                raise RuntimeError("A shipping collector is already running")
            connection.commit()
            yield
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(794218503)"));connection.commit();connection.close()
    else:
        name=sha256(str(engine.url).encode()).hexdigest()[:16]
        file=open(Path(tempfile.gettempdir())/f"oil-shipping-{name}.lock","a+b")
        try:
            file.seek(0);file.write(b"0");file.flush();file.seek(0)
            if __import__("os").name=="nt":
                import msvcrt
                msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            yield
        finally: file.close()


async def receive(stop,queue,state,counters,key,connector=connect):
    failures=0
    while not stop.is_set():
        state["status"]="connecting" if failures==0 else "reconnecting"
        try:
            async with connector(URL,compression="deflate",open_timeout=12,close_timeout=1,
                ping_interval=20,ping_timeout=20,max_queue=32,max_size=1024*1024,logger=logging.getLogger("websockets")) as socket:
                await socket.send(json.dumps({"APIKey":key,"BoundingBoxes":[BOX],"FilterMessageTypes":TYPES}))
                async for frame in socket:
                    if stop.is_set(): break
                    try: data=json.loads(frame.decode("utf-8") if isinstance(frame,bytes) else frame)
                    except (UnicodeError,json.JSONDecodeError): counters["malformed"]+=1;continue
                    if not isinstance(data,dict): counters["malformed"]+=1;continue
                    if data.get("error") or data.get("Error"):
                        state["last_error"]="Provider/subscription error; payload withheld"
                        counters["errors"]+=1;state["status"]="error";stop.set();return
                    if data.get("MessageType")=="SubscriptionConfirmation":
                        confirmation=data.get("Message") or {};confirmation=confirmation.get("SubscriptionConfirmation",confirmation)
                        state["status"]="connected";state["compression_enabled"]=bool(confirmation.get("CompressionEnabled"))
                        failures=0;print("Shipping collector subscribed; compression="+str(state["compression_enabled"]),flush=True);continue
                    if data.get("MessageType") not in TYPES: continue
                    counters["messages_received"]+=1
                    receipt=datetime.now(timezone.utc);state["latest_message_at"]=receipt
                    item=normalize(data,receipt,key)
                    if item:
                        try: queue.put_nowait(item)
                        except asyncio.QueueFull: counters["queue_dropped"]+=1
                    else: counters["invalid_messages"]+=1
        except asyncio.CancelledError: raise
        except Exception as exc:
            state["last_error"]=type(exc).__name__;counters["errors"]+=1
            print("Shipping connection error: "+type(exc).__name__,flush=True)
        if stop.is_set(): break
        failures+=1;counters["reconnects"]+=1
        if failures>=8: state["status"]="error";stop.set();break
        state["status"]="reconnecting"
        try: await asyncio.wait_for(stop.wait(),timeout=backoff(failures-1))
        except TimeoutError: pass


def write_batch(engine,items,state,counters,run_id,retention):
    with Session(engine) as db:
        increment=persist_messages(db,items)
        sweep_rules(db)
        if retention: increment["positions_pruned"]=prune_positions(db)
        row=db.get(State,1)
        if row is None:
            row=State(id=1,run_id=run_id,status=state["status"],heartbeat_at=datetime.now(timezone.utc),started_at=state["started_at"])
            db.add(row)
        row.run_id=run_id;row.status=state["status"];row.heartbeat_at=datetime.now(timezone.utc)
        row.started_at=state["started_at"];row.stopped_at=state.get("stopped_at");row.latest_message_at=state.get("latest_message_at")
        row.compression_enabled=state["compression_enabled"];row.last_error=state.get("last_error")
        totals=dict(counters)
        for k,v in increment.items(): totals[k]=totals.get(k,0)+v
        row.counters=totals;db.commit()
        return increment


async def collect(duration=None,enable_retention=False):
    settings=get_settings();secret=settings.aisstream_api_key
    if not secret or not secret.get_secret_value(): raise RuntimeError("AISSTREAM_API_KEY is not configured")
    engine=get_engine();run_id=str(uuid.uuid4());stop=asyncio.Event();queue=asyncio.Queue(maxsize=1000)
    counters=Counter();state={"status":"connecting","started_at":datetime.now(timezone.utc),"compression_enabled":False}
    logging.getLogger("websockets").disabled=True
    loop=asyncio.get_running_loop()
    import signal
    for sig in (signal.SIGINT,signal.SIGTERM):
        try: loop.add_signal_handler(sig,stop.set)
        except (NotImplementedError,RuntimeError): signal.signal(sig,lambda *_:loop.call_soon_threadsafe(stop.set))
    with singleton(engine):
        await asyncio.to_thread(write_batch,engine,[],state,counters,run_id,False)
        reader=asyncio.create_task(receive(stop,queue,state,counters,secret.get_secret_value()))
        timer=loop.call_later(duration,stop.set) if duration else None
        try:
            while not stop.is_set():
                batch=[]
                try: batch.append(await asyncio.wait_for(queue.get(),timeout=5))
                except TimeoutError: pass
                while len(batch)<100 and not queue.empty(): batch.append(queue.get_nowait())
                try:
                    increment=await asyncio.to_thread(write_batch,engine,batch,state,counters,run_id,enable_retention)
                    counters.update(increment)
                except Exception as exc:
                    # No raw SQL exception text, credentials or vessel payloads in routine logs.
                    counters["persistence_errors"]+=1;state["last_error"]=type(exc).__name__
                    state["status"]="error";stop.set()
                    print("Shipping persistence error: "+type(exc).__name__,flush=True)
            reader.cancel()
            try: await reader
            except asyncio.CancelledError: pass
            # Drain already-received records on graceful shutdown, without deleting any during verification.
            while not queue.empty():
                batch=[]
                while len(batch)<100 and not queue.empty(): batch.append(queue.get_nowait())
                counters.update(await asyncio.to_thread(write_batch,engine,batch,state,counters,run_id,False))
        finally:
            if timer: timer.cancel()
            if not reader.done():
                reader.cancel()
                try: await reader
                except asyncio.CancelledError: pass
            state["status"]="offline";state["stopped_at"]=datetime.now(timezone.utc)
            await asyncio.to_thread(write_batch,engine,[],state,counters,run_id,False)
            print("Shipping collector stopped: "+json.dumps(dict(counters),sort_keys=True),flush=True)
    return dict(counters)
