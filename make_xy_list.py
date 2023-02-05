#!/usr/bin/env python

import glob
import sys
import safetensors
import json
import mmap
import pprint
import os.path

model_dir = sys.argv[1]
if not model_dir:
    print("Provide a model path.")
    exit(1)

prefix = sys.argv[2].lower()

def read_metadata(filename):
    """Reads the JSON metadata from a .safetensors file"""
    with open(filename, mode="r", encoding="utf8") as file_obj:
        with mmap.mmap(file_obj.fileno(), length=0, access=mmap.ACCESS_READ) as m:
            header = m.read(8)
            n = int.from_bytes(header, "little")
            metadata_bytes = m.read(n)
            metadata = json.loads(metadata_bytes)

    return metadata.get("__metadata__", {})


groups = {}

for filename in glob.iglob(f"{model_dir}/**/*.safetensors", recursive=True):
    if os.path.basename(filename).lower().__contains__(prefix):
        metadata = read_metadata(filename)
        if "ss_session_id" in metadata:
            session_id = metadata["ss_session_id"]
        else:
            session_id = filename
        epoch = int(metadata.get("ss_epoch", 0))
        group = groups.get(session_id, {})
        groups[session_id] = group

        group[epoch] = filename

l = []
for session_id, group in groups.items():
    for key in sorted(int(k) for k in group.keys()):
        filename = group[key]
        l.append(os.path.splitext(os.path.basename(filename))[0])

print(", ".join(l))
