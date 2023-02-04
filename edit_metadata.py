#!/usr/bin/env python

import sys
import os
import os.path
import shutil
import safetensors_hack
from safetensors.torch import save_file


file = sys.argv[1]
if not os.path.isfile(file) or os.path.splitext(file)[1] != ".safetensors":
    print(f"Invalid .safetensors file {file}")
    exit(1)

if len(sys.argv) != 4:
    print("Provide a metadata key and its new value like \"ss_metadata_name\" \"Model Name\"")
    print("You can also pass \"None\" as the value to delete it.")
    exit(1)


def write_model_metadata(model_path, updates):
  if model_path.startswith("\"") and model_path.endswith("\""): # trim '"' at start/end
    model_path = model_path[1:-1]
  if not os.path.exists(model_path):
    return None

  back_up = True
  if back_up:
    backup_path = model_path + ".backup"
    if not os.path.exists(backup_path):
      print(f"Backing up current model to {backup_path}")
      shutil.copyfile(model_path, backup_path)

  metadata = None
  tensors = {}
  if os.path.splitext(model_path)[1] == '.safetensors':
    tensors, metadata = safetensors_hack.load_file(model_path, "cpu")

    for k, v in updates.items():
      if v is None and k in metadata:
          metadata.pop(k)
      else:
          metadata[k] = str(v)

    save_file(tensors, model_path, metadata)
    print(f"Model saved: {model_path}")

key = sys.argv[2].strip()
value = sys.argv[3].strip()
if not key:
    print(f"Invalid key or value: {key}: {value}")
    exit(1)
if not value or value == "None":
    value = None

print(f"Setting metadata key '{key}' to value: '{value}'")
write_model_metadata(file, {key: value})
