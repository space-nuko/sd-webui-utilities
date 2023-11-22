
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

def write_model_metadata(model_path):
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

    save_file(tensors, model_path, {})
    print(f"Model saved: {model_path}")

write_model_metadata(file)
