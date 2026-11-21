import time, httpx, rasterio, numpy as np
from concurrent.futures import ThreadPoolExecutor
from rasterio.io import MemoryFile
from rasterio.windows import from_bounds
from pyproj import Transformer
UA={"User-Agent":"RolnikSzukaWody/0.1 (HackNation 2026 prototype)"}
lat,lon=52.1717,21.5901  # parcel 141201_1.0001.6509
x,y=Transformer.from_crs(4326,2180,always_xy=True).transform(lon,lat)
# --- NMT WCS
t=time.perf_counter()
params=[("SERVICE","WCS"),("VERSION","2.0.1"),("REQUEST","GetCoverage"),("COVERAGEID","DTM_PL-KRON86-NH_TIFF"),
        ("FORMAT","image/tiff"),("SUBSET",f"x({x-250},{x+250})"),("SUBSET",f"y({y-250},{y+250})")]
try:
    r=httpx.get("https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF",params=params,headers=UA,timeout=30)
    if r.content[:2] in (b"II",b"MM"):
        with MemoryFile(r.content) as mf, mf.open() as ds:
            a=ds.read(1); print("NMT",ds.crs,a.shape,ds.res,"min",a.min(),"max",a.max(),f"{time.perf_counter()-t:.2f}s",len(r.content)//1024,"KB")
    else: print("NMT not tiff",r.status_code,r.text[:300])
except Exception as e: print("NMT FAIL",e)
# --- Sentinel-2 windowed read, 10 years
s=httpx.post("https://earth-search.aws.element84.com/v1/search",json={"collections":["sentinel-2-l2a"],
  "intersects":{"type":"Point","coordinates":[lon,lat]},"datetime":"2016-06-01T00:00:00Z/2025-07-15T00:00:00Z",
  "query":{"eo:cloud_cover":{"lt":20}},"limit":200},headers=UA,timeout=30).json()["features"]
by={}
for f in s:
    yr=f["properties"]["datetime"][:4]; md=f["properties"]["datetime"][5:10]
    if "06-10"<=md<="07-10" and (yr not in by or f["properties"]["eo:cloud_cover"]<by[yr]["properties"]["eo:cloud_cover"]): by[yr]=f
print("years with scene:",sorted(by))
def ndvi(f):
    t=time.perf_counter()
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",AWS_NO_SIGN_REQUEST="YES"):
        out=[]
        for b in ("red","nir"):
            with rasterio.open(f["assets"][b]["href"]) as ds:
                tx,ty=Transformer.from_crs(4326,ds.crs,always_xy=True).transform(lon,lat)
                w=from_bounds(tx-100,ty-100,tx+100,ty+100,ds.transform); out.append(ds.read(1,window=w).astype(float))
    r_,n_=out; v=np.nanmean((n_-r_)/(n_+r_+1e-9))
    return f["properties"]["datetime"][:10], round(float(v),2), round(time.perf_counter()-t,2)
t=time.perf_counter()
with ThreadPoolExecutor(10) as ex: res=list(ex.map(ndvi,by.values()))
print(res); print("S2 total",round(time.perf_counter()-t,2),"s")
