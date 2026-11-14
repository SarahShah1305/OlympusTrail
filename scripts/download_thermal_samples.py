"""Retrieve calibrated PBT pixels needed by the existing 3 km analysis grid.

HTTP byte ranges avoid transferring whole 100 m scenes. This is nearest-pixel
sampling of historical measurements, not interpolation into uncovered areas.
The original Person 2 raster is read only. Source headers and range responses
are kept in the supplied cache directory for audit/retry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from email import policy
from email.parser import BytesParser
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import rowcol, xy
from rasterio.warp import transform

ROOT = Path(__file__).resolve().parents[1]


def field(text, name):
    match = re.search(r'^\s*'+re.escape(name)+r'\s*=\s*([^\r\n]+)', text, re.M)
    if not match:
        raise ValueError('Missing PDS field '+name)
    return match.group(1).strip().strip('"')


def range_parts(headers: bytes, body: bytes):
    statuses = re.findall(rb'(?im)^HTTP/\S+\s+(\d+)', headers)
    if not statuses or statuses[-1] != b'206':
        raise ValueError('Expected HTTP 206; no full-scene fallback')
    content_types = re.findall(rb'(?im)^Content-Type:\s*([^\r\n]+)', headers)
    if not content_types:
        raise ValueError('Missing response content type')
    content_type = content_types[-1]
    if b'multipart/byteranges' in content_type.lower():
        message = BytesParser(policy=policy.default).parsebytes(
            b'Content-Type: '+content_type+b'\r\nMIME-Version: 1.0\r\n\r\n'+body)
        result = {}
        for part in message.iter_parts():
            match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', part.get('Content-Range', ''))
            if match is None:
                raise ValueError('Missing/malformed multipart byte range')
            start, end, total = map(int, match.groups())
            payload = part.get_payload(decode=True)
            if start in result or not (0 <= start <= end < total) or len(payload) != end-start+1:
                raise ValueError('Invalid/truncated multipart byte range')
            result[start] = payload
        return result
    ranges = re.findall(rb'(?im)^Content-Range:\s*bytes\s+(\d+)-(\d+)/(\d+)', headers)
    if not ranges:
        raise ValueError('Server did not honor the byte range; no full-scene fallback')
    start, end, _ = map(int, ranges[-1])
    if len(body) != end-start+1:
        raise ValueError('Truncated byte-range response')
    return {start: body}


def fetch_ranges(url, ranges, cache):
    specification = ','.join(f'{start}-{end}' for start, end in ranges)
    key = hashlib.sha256((url+specification).encode()).hexdigest()[:24]
    headers, body = cache/(key+'.http.txt'), cache/(key+'.bin')
    if not body.exists() or not headers.exists():
        subprocess.run(['curl.exe','-fsSL','--retry','2','--connect-timeout','15','--max-time','120',
                        '--range',specification,'--max-filesize','3000000','-D',str(headers),
                        url,'-o',str(body)],check=True, capture_output=True)
    parts = range_parts(headers.read_bytes(), body.read_bytes())
    for start, end in ranges:
        if start not in parts or len(parts[start]) != end-start+1:
            raise ValueError('Incomplete/mismatched multipart range response')
    return parts


def sample_product(product, needed, reference, cache):
    header = Path(product['header_path'])
    if not header.is_absolute():
        header = ROOT/header
    label = header.read_bytes().decode('ascii', errors='ignore')
    bits = int(field(label,'SAMPLE_BITS'))
    sample_type = field(label,'SAMPLE_TYPE')
    dtype = {'PC_REAL':'<f4','IEEE_REAL':'>f4','MSB_REAL':'>f4'}.get(sample_type)
    if bits != 32 or dtype is None:
        raise ValueError('Only explicitly encoded float32 PBT is sampled: '+sample_type)
    if field(label,'ODY:SAMPLE_UNIT').upper() != 'KELVIN':
        raise ValueError('PBT units are not Kelvin')
    record_bytes = int(field(label,'RECORD_BYTES'))
    image_record = int(field(label,'^IMAGE'))
    offset = (image_record-1)*record_bytes
    with rasterio.open(header) as source:
        if source.crs is None or source.count != 1:
            raise ValueError('Missing source map projection or unexpected bands')
        rr, cc = np.where(needed)
        xs, ys = xy(reference.transform, rr, cc)
        sx, sy = transform(reference.crs, source.crs, xs, ys)
        sr, sc = rowcol(source.transform, sx, sy)
        sr, sc = np.array(sr), np.array(sc)
        inside = (sr >= 0) & (sr < source.height) & (sc >= 0) & (sc < source.width)
        rr, cc, sr, sc = (values[inside] for values in (rr, cc, sr, sc))
        width, nodata = source.width, source.nodata
        source_geometry = dict(shape=list(source.shape), transform=list(source.transform)[:6],
                               crs=source.crs.to_wkt())
    rows = {}
    for target_r, target_c, source_r, source_c in zip(rr,cc,sr,sc):
        rows.setdefault(int(source_r),[]).append((int(target_r),int(target_c),int(source_c)))
    records = []
    for source_r, points in rows.items():
        lo, hi = min(p[2] for p in points), max(p[2] for p in points)
        start = offset+(source_r*width+lo)*4
        end = offset+(source_r*width+hi+1)*4-1
        records.append((start,end,lo,points))
    batches = [records[index:index+24] for index in range(0,len(records),24)]
    cache.mkdir(parents=True,exist_ok=True)

    def retrieve(batch):
        parts=fetch_ranges(product['url'],[(item[0],item[1]) for item in batch],cache)
        sampled=[]
        for start,end,lo,points in batch:
            values=np.frombuffer(parts[start],dtype=dtype)
            for r,c,col in points:
                value=float(values[col-lo])
                if np.isfinite(value) and value != nodata and 0 < value < 500:
                    sampled.append((r,c,value))
        return sampled

    samples=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for part in pool.map(retrieve,batches):
            samples.extend(part)
    responses=[]
    for batch in batches:
        specification=','.join(f'{start}-{end}' for start,end,_,_ in batch)
        key=hashlib.sha256((product['url']+specification).encode()).hexdigest()[:24]
        body=cache/(key+'.bin')
        responses.append(dict(ranges=specification, bytes=body.stat().st_size,
                              sha256=hashlib.sha256(body.read_bytes()).hexdigest()))
    return samples, dict(id=product['id'],url=product['url'],
                         header_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),
                         timestamp=field(label,'START_TIME'),
                         source_geometry=source_geometry, responses=responses,
                         acquisition=product.get('detail_fields', {}),
                         sampled_cells=len(samples), requested_rows=len(rows),
                         sampling='nearest 100 m PBT pixel at each 3 km analysis-cell center')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=ROOT/'data/person1_complete')
    parser.add_argument('--cache',type=Path,default=ROOT/'work/downloads/thermal/ranges')
    args=parser.parse_args()
    products=json.loads(args.candidates.read_text())['products']
    for product in products:
        product.setdefault('url', product.get('pbt_url'))
        if not product['url']:
            raise ValueError('Missing verified product URL')
    args.out.mkdir(parents=True,exist_ok=True)
    with rasterio.open(ROOT/'data/processed/thermal_brightness_temperature_k.tif') as reference:
        mosaic=reference.read(1,masked=True).filled(np.nan).astype('float32')
        initial=int(np.isfinite(mosaic).sum())
        source_ids=np.where(np.isfinite(mosaic),0,-1).astype('int16')
        profile=reference.profile.copy()
        inventory=[]
        for index,product in enumerate(products,1):
            try:
                samples,record=sample_product(product,~np.isfinite(mosaic),reference,
                                               args.cache/product['id'])
                for row,col,value in samples:
                    mosaic[row,col]=value
                    source_ids[row,col]=index
                record['coverage_fraction_after']=float(np.isfinite(mosaic).mean())
                inventory.append(record)
                print(json.dumps(record),flush=True)
            except (ValueError,subprocess.CalledProcessError,OSError) as error:
                inventory.append(dict(id=product['id'],url=product['url'],error=str(error)))
                print(json.dumps(inventory[-1]),flush=True)
    profile.update(dtype='float32',nodata=np.nan,compress='deflate',predictor=3,tiled=True)
    with rasterio.open(args.out/'thermal_observations_k.tif','w',**profile) as dst:
        dst.write(mosaic,1)
        dst.update_tags(1,UNIT='K',DATA_CLASS='historical_observation_atlas',
                        SAMPLING='PDS byte ranges; nearest native pixel at target center')
    profile.update(dtype='int16',nodata=-1,predictor=2)
    with rasterio.open(args.out/'thermal_observation_source_id.tif','w',**profile) as dst:
        dst.write(source_ids,1)
        dst.update_tags(1,UNIT='source_index',SOURCE_ZERO='Original Person 2 three-scene mosaic')
    summary=dict(initial_valid_cells=initial,valid_cells=int(np.isfinite(mosaic).sum()),
                 total_cells=int(mosaic.size),coverage_fraction=float(np.isfinite(mosaic).mean()),
                 products=inventory,source_id_mapping={str(i):p['id'] for i,p in enumerate(products,1)},
                 caveat='Historical observations at different dates/local times; not one contemporaneous map. Unobserved cells remain nodata.')
    (args.out/'thermal_provenance.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({key:value for key,value in summary.items() if key not in ['products','source_id_mapping']}))


if __name__ == '__main__':
    main()
