#!/usr/bin/env python

import sys
import safetensors
import json
import mmap
import pprint
import argparse
from collections import OrderedDict
import itertools

parser = argparse.ArgumentParser()
parser.add_argument("--tag-frequency", "-t", action="store_true")
parser.add_argument("--max-tags", "-m", type=int, default=20)
parser.add_argument("--show-large", "-l", action="store_true")
parser.add_argument("model_path")
args = parser.parse_args()

model_path = args.model_path
if not model_path:
    print("Provide a model path.")
    exit(1)


large_metadata = ["ss_dataset_dirs", "ss_tag_frequency", "ss_bucket_info"]
no_large = not args.show_large


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

        ordered = OrderedDict()
        for k in sorted(res.keys()):
            ordered[k] = res[k]

        return ordered

meta = read_metadata(model_path)

if args.tag_frequency:
    tag_frequency = meta.get("ss_tag_frequency", None)
    if tag_frequency is None:
        print("No tag frequency found.")
    else:
        for k, v in tag_frequency.items():
            ordered = sorted([(tk, tv) for tk, tv in v.items()], key=lambda t: t[1], reverse=True)
            if args.max_tags > 0:
                ordered = itertools.islice(ordered, args.max_tags)
            print(f"- {k}:")
            for tk, tv in ordered:
                print(f"    {tk.strip()}: {tv}")
else:
    for k, v in meta.items():
        if args.show_large or k not in large_metadata:
            print(f"{k}: {v}")
