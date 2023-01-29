#!/usr/bin/env python

import os
import os.path
import torch
import sys
import glob
import shutil
from safetensors.torch import save_file

dir = sys.argv[1]
if not os.path.isdir(dir):
    print(f"Invalid path {dir}")
    exit(1)

if len(sys.argv) < 2:
    print("No tags provided.")
    exit(1)

def convert_tag(t):
    return t.replace("_", " ").replace("(", "\(").replace(")", "\)")

raw_tags = sys.argv[2:]
tags = [convert_tag(t) for t in raw_tags]

print(tags)

outpath = os.path.join(dir, " ".join(raw_tags))

for txt in glob.iglob(os.path.join(dir, "**/*.txt"), recursive=True):
    png = os.path.splitext(txt)[0] + ".png"
    if os.path.isfile(png):
        with open(txt, "r") as f:
            these_tags = {t.strip().lower(): True for t in f.read().split(",")}

        if all(t in these_tags for t in tags):
            os.makedirs(outpath, exist_ok=True)
            basename = os.path.splitext(os.path.basename(txt))[0]
            out_txt = os.path.join(outpath, basename + ".txt")
            out_png = os.path.join(outpath, basename + ".png")
            print(f"{png} -> {out_png}")
            shutil.move(txt, out_txt)
            shutil.move(png, out_png)
