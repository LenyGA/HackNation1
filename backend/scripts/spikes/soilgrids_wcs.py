import time, io, httpx, rasterio
from rasterio.io import MemoryFile
pts=[(52.55,17.60),(53.60,15.40),(50.90,22.10),(52.05,19.20),(54.10,19.00)]
UA={"User-Agent":"RolnikSzukaWody/0.1 (HackNation 2026 prototype)"}
d=0.004
with httpx.Client(headers=UA, timeout=20) as c:
    for lat,lon in pts:
        for prop in ["sand","clay","soc"]:
            t=time.perf_counter()
            params=[("map",f"/map/{prop}.map"),("SERVICE","WCS"),("VERSION","2.0.1"),("REQUEST","GetCoverage"),
                ("COVERAGEID",f"{prop}_0-5cm_mean"),("FORMAT","image/tiff"),
                ("SUBSET",f"long({lon-d},{lon+d})"),("SUBSET",f"lat({lat-d},{lat+d})"),
                ("SUBSETTINGCRS","http://www.opengis.net/def/crs/EPSG/0/4326"),("OUTPUTCRS","http://www.opengis.net/def/crs/EPSG/0/4326")]
            r=c.get("https://maps.isric.org/mapserv",params=params)
            if not r.content.startswith(b"II") and not r.content.startswith(b"MM"):
                print(lat,lon,prop,"NOT TIFF",r.status_code,r.text[:200].replace("\n"," ")); continue
            with MemoryFile(r.content) as mf, mf.open() as ds:
                a=ds.read(1); print(lat,lon,prop,a.shape,"vals",sorted(set(a.ravel().tolist()))[:4],"nodata",ds.nodata,f"{time.perf_counter()-t:.2f}s")
