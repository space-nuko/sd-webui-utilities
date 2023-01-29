#!/usr/bin/env python

import sys
import safetensors
import json
import mmap
import pprint

model_path = sys.argv[1]
if not model_path:
    print("Provide a model path.")
    exit(1)


def read_metadata(filename):
    """Reads the JSON metadata from a .safetensors file"""
    with open(filename, mode="r", encoding="utf8") as file_obj:
        with mmap.mmap(file_obj.fileno(), length=0, access=mmap.ACCESS_READ) as m:
            header = m.read(8)
            n = int.from_bytes(header, "little")
            metadata_bytes = m.read(n)
            metadata = json.loads(metadata_bytes)

    return metadata.get("__metadata__", {})

pprint.pp(read_metadata(model_path))
