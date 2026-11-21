import time, httpx, rasterio, numpy as np
from rasterio.windows import from_bounds
from pyproj import Transformer
UA={"User-Agent":"RolnikSzukaWody/0.1 (HackNation 2026 prototype)"}
lat,lon=52.1717,21.5901
ENV=dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF",GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",VSI_CACHE="TRUE")
for coll,asset,half in [("cop-dem-glo-30","data",400),("esa-worldcover","map",200)]:
    t=time.perf_counter()
    tok=httpx.get(f"https://planetarycomputer.microsoft.com/api/sas/v1/token/{coll}",headers=UA,timeout=15).json()["token"]
    f=httpx.post("https://planetarycomputer.microsoft.com/api/stac/v1/search",json={"collections":[coll],
        "intersects":{"type":"Point","coordinates":[lon,lat]},"limit":5},headers=UA,timeout=20).json()["features"]
    f=sorted(f,key=lambda x:x["properties"].get("datetime") or x["properties"].get("start_datetime",""))[-1]
    with rasterio.Env(**ENV), rasterio.open(f["assets"][asset]["href"]+"?"+tok) as ds:
        tx,ty=Transformer.from_crs(4326,ds.crs,always_xy=True).transform(lon,lat)
        d=half/111000 if ds.crs.to_epsg()==4326 else half
        a=ds.read(1,window=from_bounds(tx-d,ty-d,tx+d,ty+d,ds.transform))
    vals,counts=np.unique(a,return_counts=True)
    print(coll,f["id"],ds.crs,a.shape,"min",a.min(),"max",a.max(), dict(zip(vals.tolist()[:6],counts.tolist()[:6])) if coll=="esa-worldcover" else "",f"{time.perf_counter()-t:.2f}s")
