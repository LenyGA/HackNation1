import time, httpx, rasterio, numpy as np
from concurrent.futures import ThreadPoolExecutor
from rasterio.windows import from_bounds
from pyproj import Transformer
UA={"User-Agent":"RolnikSzukaWody/0.1 (HackNation 2026 prototype)"}
lat,lon=52.1717,21.5901
ENV=dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF",GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",GDAL_HTTP_MULTIPLEX="YES",GDAL_HTTP_VERSION="2",VSI_CACHE="TRUE",GDAL_INGESTED_BYTES_AT_OPEN="32768")
t=time.perf_counter()
tok=httpx.get("https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-2-l2a",headers=UA,timeout=15).json()["token"]
print("token",round(time.perf_counter()-t,2),"s")
t=time.perf_counter()
feats=[]
for yr in range(2016,2026):
    r=httpx.post("https://planetarycomputer.microsoft.com/api/stac/v1/search",json={"collections":["sentinel-2-l2a"],
      "intersects":{"type":"Point","coordinates":[lon,lat]},"datetime":f"{yr}-06-10T00:00:00Z/{yr}-07-10T23:59:59Z",
      "sortby":[{"field":"eo:cloud_cover","direction":"asc"}],"limit":1},headers=UA,timeout=20).json()["features"]
    if r: feats.append(r[0])
print("PC search 10 yrs",round(time.perf_counter()-t,2),"s years",[f["properties"]["datetime"][:10]+f" cc={f['properties']['eo:cloud_cover']:.0f}" for f in feats])
def ndvi(f):
    t=time.perf_counter()
    with rasterio.Env(**ENV):
        out=[]
        for b in ("B04","B08"):
            with rasterio.open(f["assets"][b]["href"]+"?"+tok) as ds:
                tx,ty=Transformer.from_crs(4326,ds.crs,always_xy=True).transform(lon,lat)
                w=from_bounds(tx-100,ty-100,tx+100,ty+100,ds.transform); out.append(ds.read(1,window=w).astype(float))
    r_,n_=out; v=np.nanmean((n_-r_)/(n_+r_+1e-9))
    return f["properties"]["datetime"][:10], round(float(v),2), round(time.perf_counter()-t,2)
t=time.perf_counter()
with ThreadPoolExecutor(10) as ex: res=list(ex.map(ndvi,feats))
print(res); print("PC read total",round(time.perf_counter()-t,2),"s")
