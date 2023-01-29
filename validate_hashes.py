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

total = 0
with_hash = 0
mismatches = 0

for filename in glob.iglob(f"{model_dir}/**/*.safetensors", recursive=True):
    metadata = safetensors_hack.read_metadata(filename)
    if "sshs_model_hash" in metadata and "sshs_legacy_hash" in metadata:
        precalc_hash = metadata["sshs_model_hash"]
        precalc_legacy_hash = metadata["sshs_legacy_hash"]
        hash = safetensors_hack.hash_file(filename)
        legacy_hash = safetensors_hack.legacy_hash_file(filename)

        mismatch = False
        if precalc_hash != hash:
            print(f"HASH MISMATCH - {filename} ({precalc_hash} != {hash})")
            mismatch = True
        if precalc_legacy_hash != legacy_hash:
            print(f"LEGACY HASH MISMATCH - {filename} ({precalc_legacy_hash} != {legacy_hash})")
            mismatch = True

        with_hash += 1
        if mismatch:
            mismatches += 1

    total += 1

print(f"Validated: {total} total, {with_hash} with embedded hash, {mismatches} mismatches")
