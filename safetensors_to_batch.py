#!/usr/bin/env python

import sys
import os.path
from decimal import Decimal
import safetensors

model_path = sys.argv[1]
dataset_name = sys.argv[2]

if not model_path:
    print("Provide a model path and dataset name.")
    exit(1)
if not dataset_name:
    print("Provide a dataset name.")
    exit(1)

def format_sci(s):
    return "{:e}".format(Decimal(s))

with safetensors.safe_open(model_path, framework="pt") as f:
    metadata = f.metadata()
    if not metadata:
        print(f"Model has no metadata: {model_path}")
        exit(1)

    name = os.path.basename(os.path.splitext(model_path)[0])
    dataset = dataset_name
    model_name = metadata["ss_sd_model_name"]
    vae_name = metadata.get("ss_vae_name", "animefull-latest.ckpt")
    learning_rate = format_sci(metadata["ss_learning_rate"])
    unet_lr = format_sci(metadata["ss_unet_lr"])
    text_encoder_lr = format_sci(metadata["ss_text_encoder_lr"])
    batch_size = metadata["ss_batch_size_per_device"]
    num_epochs = metadata["ss_num_epochs"]
    scheduler = metadata["ss_lr_scheduler"]
    network_dim = metadata["ss_network_dim"]
    save_every_n_epochs = 2
    network_alpha = network_dim

    row = [name, dataset, model_name, vae_name, learning_rate, unet_lr, text_encoder_lr, batch_size, num_epochs, save_every_n_epochs, scheduler, network_dim, network_alpha]
    row = [str(s) for s in row]
    print(", ".join(row))
