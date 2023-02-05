#!/usr/bin/env python

import os
import os.path
import torch
import sys
import glob
import shutil

dir = sys.argv[1]
if not os.path.isdir(dir):
    print(f"Invalid path {dir}")
    exit(1)

if len(sys.argv) < 3:
    print("Must give at least 1 tag.")
    exit(1)

def convert_tag(t):
    return t.replace("_", " ").replace("(", "\(").replace(")", "\)")

raw_tags = sys.argv[2:]
tags = [convert_tag(t) for t in raw_tags]

print(tags)

outpath = os.path.join(dir, " ".join(raw_tags))

for txt in glob.iglob(os.path.join(dir, "**/*.txt"), recursive=True):
    png = os.path.splitext(txt)[0] + ".png"
    jpg = os.path.splitext(txt)[0] + ".jpg"
    if os.path.isfile(png) or os.path.isfile(jpg):
        with open(txt, "r") as f:
            these_tags = [t.strip().lower() for t in f.read().split(",")]

        for to_add in tags:
            if to_add not in these_tags:
                these_tags.append(to_add)

        #print(", ".join(these_tags))
        print(txt)
        with open(txt, "w") as f:
            print(txt)
            f.write(", ".join(these_tags))
