from pathlib import Path
from pyproj import Transformer
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/processed'
RAW = ROOT / 'data/raw'
FORWARD = Transformer.from_crs(4326, 26916, always_xy=True)
INVERSE = Transformer.from_crs(26916, 4326, always_xy=True)
def project(geometry): return transform(FORWARD.transform, geometry)
def unproject(geometry): return transform(INVERSE.transform, geometry)
