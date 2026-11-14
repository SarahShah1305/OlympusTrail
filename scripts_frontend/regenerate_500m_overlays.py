"""Render the Arcadia 500 m planning rasters as compact EPSG:4326 map overlays."""
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import ColorInterp
from rasterio.io import MemoryFile
from rasterio.shutil import copy as copy_dataset
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/person1/arcadia_500m"
OUT = ROOT / "frontend/public/layers"
MARS_GEOGRAPHIC = "+proj=longlat +a=3396190 +b=3396190 +no_defs +type=crs"
PALETTES = {
 "elevation": ["#2F174B", "#63418F", "#A879B4", "#F0D5ED"],
 "slope": ["#FFF0D2", "#F5B952", "#D87934", "#8F302B"],
 "aspect": ["#3E1C75", "#165D9D", "#138077", "#B08E23", "#BD503A", "#3E1C75"],
 "ice": ["#E0F2EF", "#9DD8D1", "#3AA7A3", "#07585E"],
 "dust": ["#E6E6E2", "#B7B7B1", "#806C77", "#402E3A"],
 "temperature": ["#3B1459", "#87447A", "#D4685D", "#FFC879"],
 "sunlight": ["#0B352D", "#28745C", "#75A96C", "#C8DC7E"],
}
SPECS = [
 ("elevation", "elevation_m.tif", "Elevation", "m", "MOLA MEGDR elevation, source grid 500 m." , "MOLA 500 m terrain"),
 ("slope", "slope_deg.tif", "Steepness", "degrees", "Slope derived from the 500 m MOLA grid." , "MOLA 500 m terrain"),
 ("aspect", "aspect_deg.tif", "Slope direction", "degrees clockwise from north", "Downhill bearing from the 500 m MOLA grid; flat-cell bearings are unreliable." , "MOLA 500 m terrain"),
 ("ice", "ice_consistency.tif", "Ice evidence", "index (0–1)", "SWIM ice consistency index in the upper metre; native source is approximately 3 km." , "SWIM, native ~3 km"),
 ("dust", "dust_optical_depth.tif", "Dust risk", "optical depth", "MCD climatology; coarse model data, not a surface hazard map." , "MCD v6.2 model"),
 ("temperature", "temperature_lt12_k.tif", "Temperature at local noon", "K", "MCD climatology surface temperature; coarse model data, not a local forecast." , "MCD v6.2 model"),
 ("sunlight", "sunlight_mean_w_m2.tif", "Sunlight", "W/m²", "Mean of four local-time MCD model samples; coarse model data." , "MCD v6.2 model"),
]

def main():
 OUT.mkdir(parents=True, exist_ok=True)
 manifest = json.loads((SRC / "manifest.json").read_text(encoding="utf-8"))
 layers=[]; shared_bounds=None; shared_size=None
 for ident, filename, label, units, desc, source in SPECS:
  path=SRC/filename
  with rasterio.open(path) as src:
   # GDAL cannot infer a datum transform for Mars. Explicitly reproject its
   # spherical equirectangular coordinates to Mars longitude/latitude degrees.
   west,south,east,north=manifest["bounds_lonlat"]
   # Match the 500 m source grid size; the longitude step corresponds to
   # 500 m at the source's 49 degree standard parallel.
   width,height=manifest["width"],manifest["height"]
   dst_transform=from_bounds(west,south,east,north,width,height)
   values=np.full((height,width), np.nan, np.float32)
   reproject(rasterio.band(src,1), values, src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
             dst_transform=dst_transform, dst_crs=MARS_GEOGRAPHIC, dst_nodata=np.nan,
             resampling=Resampling.nearest if ident=="aspect" else Resampling.bilinear)
  # All rasters share the identical georeferenced extent/resolution.
  valid=np.isfinite(values); lo=float(values[valid].min()); hi=float(values[valid].max())
  norm=np.zeros(values.shape,np.float32) if hi==lo else np.clip((np.nan_to_num(values,nan=lo)-lo)/(hi-lo),0,1)
  stops=np.array([[int(c[i:i+2],16) for i in (1,3,5)] for c in PALETTES[ident]],dtype=np.float32)
  pos=np.linspace(0,1,len(stops)); palette=np.zeros((256,3),np.uint8)
  palette[:255]=np.stack([np.interp(np.linspace(0,1,255),pos,stops[:,c]) for c in range(3)],axis=-1).astype(np.uint8)
  indices=np.minimum((norm*254).astype(np.uint8),254); indices[~valid]=255
  rgba=np.zeros((height,width,4),np.uint8)
  rgba[:,:,:3]=palette[indices]
  rgba[:,:,3]=np.where(valid,255,0).astype(np.uint8)
  image_path=OUT/f"{ident}.webp"
  with MemoryFile() as memory:
   with memory.open(driver="GTiff",width=width,height=height,count=4,dtype="uint8",crs="EPSG:4326",transform=dst_transform) as image:
    image.write(rgba.transpose(2,0,1))
    image.colorinterp=(ColorInterp.red,ColorInterp.green,ColorInterp.blue,ColorInterp.alpha)
   with memory.open() as image:
    quality=28 if ident=="aspect" else 86
    with rasterio.Env(GDAL_PAM_ENABLED="NO"):
     copy_dataset(image,image_path,driver="WEBP",QUALITY=str(quality),strict=True)
  (OUT/f"{ident}.png").unlink(missing_ok=True)
  # Leaflet bounds and metadata use the exact EPSG:4326 target grid.
  west=dst_transform.c; north=dst_transform.f; east=west+width*dst_transform.a; south=north+height*dst_transform.e
  latlng=[[south,west],[north,east]]
  if shared_bounds is None: shared_bounds=latlng; shared_size=[width,height]
  layers.append({"id":ident,"image":f"{ident}.webp","bounds_latlng":latlng,"width":width,"height":height,
   "pixel_size_degrees":[abs(dst_transform.a),abs(dst_transform.e)],"min":lo,"max":hi,"units":units,
   "coverage_percent":round(100*valid.sum()/valid.size,2),"label":label,"description":desc,"source":source,
   "source_pixel_m":500 if ident in ("elevation","slope","aspect") else None,"legend_colors":PALETTES[ident],
   "image_quality":28 if ident=="aspect" else 86})
 meta={"region":"Arcadia Planitia, 40–58°N","crs":"EPSG:4326 (reprojected from 500 m equirectangular Mars rasters)",
  "pixel_size_m":500,"image_format":"WebP; alpha retained for nodata; quality 28 for aspect and 86 for other overlays","bounds_lonlat":manifest["bounds_lonlat"],"bounds_latlng":shared_bounds,"width":shared_size[0],"height":shared_size[1],"layers":layers}
 (OUT/"layers.json").write_text(json.dumps(meta,indent=2)+"\n",encoding="utf-8")
 print(f"Wrote {len(layers)} overlays at {shared_size[0]}x{shared_size[1]}; EPSG:4326 bounds {shared_bounds}")

if __name__=="__main__": main()
