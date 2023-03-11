# DanBooru IMage Utility functions

import os
import cv2
import numpy as np
from PIL import Image
import tqdm
import requests
import pandas as pd


def smart_imread(img, flag=cv2.IMREAD_UNCHANGED):
    if img.endswith(".gif"):
        img = Image.open(img)
        img = img.convert("RGB")
        img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    else:
        img = cv2.imread(img, flag)
    return img


def smart_24bit(img):
    if img.dtype is np.dtype(np.uint16):
        img = (img / 257).astype(np.uint8)

    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        trans_mask = img[:, :, 3] == 0
        img[trans_mask] = [255, 255, 255, 255]
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


def make_square(img, target_size):
    old_size = img.shape[:2]
    desired_size = max(old_size)
    desired_size = max(desired_size, target_size)

    delta_w = desired_size - old_size[1]
    delta_h = desired_size - old_size[0]
    top, bottom = delta_h // 2, delta_h - (delta_h // 2)
    left, right = delta_w // 2, delta_w - (delta_w // 2)

    color = [255, 255, 255]
    new_im = cv2.copyMakeBorder(
        img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color
    )
    return new_im


def smart_resize(img, size):
    # Assumes the image has already gone through make_square
    if img.shape[0] > size:
        img = cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)
    elif img.shape[0] < size:
        img = cv2.resize(img, (size, size), interpolation=cv2.INTER_CUBIC)
    return img


danbooru_tags = {}
CATEGORIES = {
    "general": 0,
    "artist": 1,
    "copyright": 3,
    "character": 4,
    "meta": 5,
}


def load_danbooru_tags():
    global danbooru_tags
    if not os.path.isfile("danbooru.csv"):
        print("Downloading danbooru.csv tags list...")
        url = "https://github.com/arenatemp/sd-tagging-helper/raw/master/danbooru.csv"
        response = requests.get(url, stream=True)
        with open("danbooru.csv", "wb") as handle:
            for data in tqdm.tqdm(response.iter_content()):
                handle.write(data)

    print("Loading danbooru.csv tags list...")
    new_tags = pd.read_csv("danbooru.csv", engine="pyarrow").set_axis(["tag", "tag_category"], axis=1).set_index("tag").to_dict("index")
    danbooru_tags.clear()
    for k, v in new_tags.items():
        danbooru_tags[k] = v
    print("Done.")
