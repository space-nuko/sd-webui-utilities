#!/usr/bin/env python

import sys
import safetensors
import json
import mmap
import pprint
from collections import OrderedDict

model_path = sys.argv[1]
if not model_path:
    print("Provide a model path.")
    exit(1)


large_metadata = ["ss_dataset_dirs", "ss_tag_frequency", "ss_bucket_info"]
no_large = True


def read_metadata(filename):
    with open(filename, mode="rb") as file:
        metadata_len = file.read(8)
        metadata_len = int.from_bytes(metadata_len, "little")
        json_start = file.read(2)

        assert metadata_len > 2 and json_start in (b'{"', b"{'"), f"{filename} is not a safetensors file"
        json_data = json_start + file.read(metadata_len-2)
        json_obj = json.loads(json_data)

        res = {}
        for k, v in json_obj.get("__metadata__", {}).items():
            res[k] = v
            if isinstance(v, str) and v[0:1] == '{':
                try:
                    res[k] = json.loads(v)
                except Exception as e:
                    pass

        if no_large:
            for k in large_metadata:
                res.pop(k, None)

        ordered = OrderedDict()
        for k in sorted(res.keys()):
            ordered[k] = res[k]

        return ordered

meta = read_metadata(model_path)
for k, v in meta.items():
    print(f"{k}: {v}")
