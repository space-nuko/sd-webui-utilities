# Got a bunch of .ckpt files to convert?
# Here's a handy script to take care of all that for you!
# Original .ckpt files are not touched!
# Make sure you have enough disk space! You are going to DOUBLE the size of your models folder!
#
# First, run:
# pip install torch torchsde==0.2.5 safetensors==0.2.5
#
# Place this file in the **SAME DIRECTORY** as all of your .ckpt files, open a command prompt for that folder, and run:
# python convert_to_safe.py

import os
import os.path
import torch
import sys
import glob
from safetensors.torch import save_file
exts = [".ckpt", ".pt"]

path = sys.argv[1]
if not os.path.isdir(path):
    print(f"Invalid path {path}")
    exit(1)

for ext in exts:
    files = glob.iglob(f"{path}/**/*{ext}", recursive=True)
    for f in files:
        print(f'Loading {f}...')
        fn = f"{f.replace(ext, '')}.safetensors"

        if os.path.isfile(fn):
            print(f'Skipping, as {fn} already exists.')
            continue

        try:
            with torch.no_grad():
                weights = torch.load(f)
                fn = f"{f.replace(ext, '')}.safetensors"
                print(f'Saving {fn}...')
                save_file(weights, fn)
        except Exception as ex:
            print(f'ERROR converting {f}: {ex}')

print('Done!')
