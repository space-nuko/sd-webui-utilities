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

def convert_tag(t):
    return t.replace("_", " ").replace("(", "\(").replace(")", "\)")

for txt in glob.iglob(os.path.join(dir, "**/*.txt"), recursive=True):
    png = os.path.splitext(txt)[0] + ".png"
    jpg = os.path.splitext(txt)[0] + ".jpg"
    if os.path.isfile(png) or os.path.isfile(jpg):
        with open(txt, "r") as f:
            these_tags = [t.strip().lower() for t in f.read().split(",")]

        filename = os.path.splitext(os.path.basename(txt))[0]
        these_tags.insert(1, convert_tag(filename))

        #print(", ".join(these_tags))
        with open(txt, "w") as f:
            print(txt)
            f.write(", ".join(these_tags))
