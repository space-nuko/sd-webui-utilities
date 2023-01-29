#!/usr/bin/env python

import glob
import sys
import safetensors
import json
import mmap
import pprint
import os.path

import safetensors_hack

model_dir = sys.argv[1]
if not model_dir:
    print("Provide a model path.")
    exit(1)

for filename in glob.iglob(f"{model_dir}/**/*.safetensors", recursive=True):
    metadata = safetensors_hack.read_metadata(filename)
    precalc_hash = metadata.get("sshs_model_hash", None)
    precalc_legacy_hash = metadata.get("sshs_legacy_hash", None)
    hash = safetensors_hack.hash_file(filename)
    legacy_hash = safetensors_hack.legacy_hash_file(filename)

    print(f"File: {filename}")
    print(f"  - Precalc. Hash: {precalc_hash}")
    print(f"  - Precalc. Legacy Hash: {precalc_legacy_hash}")
    print(f"  - Hash: {hash}")
    print(f"  - Legacy Hash: {legacy_hash}")
