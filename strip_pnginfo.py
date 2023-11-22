#!/usr/bin/env python

from PIL.PngImagePlugin import PngImageFile, PngInfo
import sys
import os
import glob

exts = [".png"]

path = sys.argv[1]
if os.path.isdir(path):
    files = []
    for ext in exts:
        files += list(glob.iglob(f"{path}/**/*{ext}", recursive=True))
elif os.path.isfile(path):
    ext = os.path.splitext(path)[1]
    if ext not in exts:
        print(f"Invalid file {path}")
        exit(1)
    files = [path]
else:
    print(f"Invalid path {path}")
    exit(1)

for f in files:
    targetImage = PngImageFile(f)
    metadata = PngInfo()
    targetImage.save(os.path.join(os.path.dirname(f), os.path.basename(f) + "_stripped.png"), pnginfo=metadata)

print(f"Stripped {len(files)} files.")
