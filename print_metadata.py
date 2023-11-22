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
parser.add_argument("--merge-recipe", "-r", action="store_true")
parser.add_argument("--max-tags", "-m", type=int, default=20)
parser.add_argument("--show-large", "-l", action="store_true")
parser.add_argument("model_path", nargs="+")
args = parser.parse_args()

model_path = args.model_path
if not model_path:
    print("Provide at least one model path.")
    exit(1)


large_metadata = ["ss_dataset_dirs", "ss_tag_frequency", "ss_bucket_info", "sd_merge_models", "sd_merge_recipe"]
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

for path in model_path:
    try:
        meta = read_metadata(path)
    except Exception as ex:
        print(f"!!! {ex}")
        continue

    print(f"* {path}:")
    printed = False

    if args.tag_frequency:
        printed = True
        tag_frequency = meta.get("ss_tag_frequency", None)
        if tag_frequency is None:
            print("No tag frequency found.")
        else:
            for k, v in tag_frequency.items():
                ordered = sorted([(tk, tv) for tk, tv in v.items()], key=lambda t: t[1], reverse=True)
                if args.max_tags > 0:
                    ordered = itertools.islice(ordered, args.max_tags)
                print(f"  - {k}:")
                for tk, tv in ordered:
                    print(f"      {tk.strip()}: {tv}")
    elif args.merge_recipe:
        merge_models = meta.get("sd_merge_models", None)
        merge_recipe = meta.get("sd_merge_recipe", None)

        if merge_models:
            print("  - Models:")
            for k, v in merge_models.items():
                printed = True
                print(f"    - {k}:")
                for k, v in v.items():
                    if (k == "sd_merge_recipe" or k == "merge_recipe") and v:
                        print(f"        {k}:")
                        for k, v in v.items():
                            print(f"          {k}: {v}")
                    else:
                        print(f"        {k}: {v}")

        if merge_recipe:
            print("  - Recipe:")
            for k, v in merge_recipe.items():
                printed = True
                print(f"      {k}: {v}")
    else:
        for k, v in meta.items():
            if args.show_large or k not in large_metadata:
                print(f"  - {k}: {v}")
                printed = True

    if not printed:
        print("  (No metadata)")
    print()
