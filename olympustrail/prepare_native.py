"""Package the build host's Expat library for Vercel's minimal Linux runtime.

Run during the Linux build, not on requests. No binary is downloaded or
committed; the runtime preloads this file before importing Rasterio/GDAL.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import shutil
import sys
from pathlib import Path


def prepare(root: Path):
    if sys.platform != "linux":
        print("Native packaging skipped: only needed for the Linux deployment.")
        return
    soname = ctypes.util.find_library("expat")
    candidates = [
        Path("/lib64/libexpat.so.1"), Path("/usr/lib64/libexpat.so.1"),
        Path("/lib/x86_64-linux-gnu/libexpat.so.1"),
        Path("/usr/lib/x86_64-linux-gnu/libexpat.so.1"),
    ]
    if soname and Path(soname).is_absolute():
        candidates.insert(0, Path(soname))
    source = next((path.resolve() for path in candidates if path.is_file()), None)
    if source is None:
        raise RuntimeError("The Linux build image does not contain libexpat.so.1")
    target = root / "olympustrail" / "_native" / "libexpat.so.1"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    ctypes.CDLL(str(target), mode=ctypes.RTLD_GLOBAL)
    print(f"Packaged libexpat.so.1 ({target.stat().st_size} bytes).")


if __name__ == "__main__":
    prepare(Path(__file__).resolve().parents[1])
