"""Serve the built Expo web app and real-data API together."""
import argparse,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8765);args=p.parse_args()
    required=['data/processed/graph.json','data/processed/samples.npz','data/raw/canopy/UTCMosaic2023.tif','apps/mobile/dist/index.html']
    missing=[x for x in required if not (root/x).exists()]
    if missing:raise SystemExit('Missing built inputs: '+', '.join(missing)+'. Follow README.md first.')
    import uvicorn
    uvicorn.run('services.api:app',host=args.host,port=args.port)
