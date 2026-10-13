"""Run one Shipping Intelligence pilot collector outside FastAPI."""
import argparse
import asyncio
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.shipping_collector import collect

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration",type=int,help="Stop after this many seconds (omit for standalone worker)")
    parser.add_argument("--enable-retention",action="store_true",help="Explicitly enable configurable detailed-history cleanup")
    args=parser.parse_args()
    if args.duration is not None and args.duration<1: parser.error("Duration must be positive")
    try: asyncio.run(collect(args.duration,args.enable_retention))
    except KeyboardInterrupt: pass
    except Exception as exc:
        print("Collector could not run: "+type(exc).__name__+"; check backend configuration/migrations or singleton ownership.")
        raise SystemExit(1)
