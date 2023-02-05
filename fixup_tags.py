#!/usr/bin/env python

# Removes duplicate tags in captions and fixes extra newlines added by the wd1.4 append behavior

import glob
import sys
import safetensors
import json
import mmap
import pprint
import os.path

dir = sys.argv[1]
if not os.path.isdir(dir):
    print(f"Invalid path {dir}")
    exit(1)

for txt in glob.iglob(os.path.join(dir, "**/*.txt"), recursive=True):
    png = os.path.splitext(txt)[0] + ".png"
    jpg = os.path.splitext(txt)[0] + ".jpg"
    gif = os.path.splitext(txt)[0] + ".gif"
    if os.path.isfile(png) or os.path.isfile(jpg) or os.path.isfile(gif):
        with open(txt, "r") as f:
            s = f.read()

        s = ", ".join(s.split("\n"))
        these_tags = [t.strip().lower() for t in s.split(",")]

        fixed_tags = []
        for i in these_tags:
          if i not in fixed_tags:
            fixed_tags.append(i)

        print(txt)
        with open(txt, "w") as f:
            print(txt)
            f.write(", ".join(fixed_tags))
