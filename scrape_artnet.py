#!/usr/bin/env python

import os
import os.path
import sys
import urllib.parse
import re
import json
from bs4 import BeautifulSoup
import requests
from pathvalidate import sanitize_filepath
from multiprocessing.pool import ThreadPool as Pool
from urllib.parse import urlparse, parse_qs, urljoin


artist = sys.argv[1]
work_type = sys.argv[2]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Content-Type": "application/json; charset=UTF-8",
}


def worker(item):
    resp = requests.get(urljoin("https://www.artnet.com", item["ImgHref"]), headers=HEADERS)
    page = BeautifulSoup(resp.text, features="html5lib")
    imgArea = page.find(id="imgArea")
    if not imgArea:
        print(f"*** SKIPPING (no images): {item['ImgHref']}")
        return
    img = imgArea.find("img")
    if not img:
        print(f"*** SKIPPING (no images): {item['ImgHref']}")
        return
    url = "https:" + img.get("src")

    path = sanitize_filepath(os.path.join("artnet", artist, os.path.basename(url)))
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.exists(path):
        print("*** SKIPPING (exists): " + path)
    else:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            print(f"!!! FAILED saving: {url}")
            return
        print("Saving: " + url)
        with open(path, "wb") as f:
            for chunk in resp:
                f.write(chunk)

    artist_name = item["ArtistName"]
    artwork_name = item["ArtworkTitle"]
    year = item["WorkYearFrom"]
    txt = f"{artist_name}, {artwork_name}, {year}"

    txt_name = os.path.splitext(os.path.basename(path))[0] + ".txt"
    txt_path = os.path.join(os.path.dirname(path), txt_name)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt)


no = 1
while True:
    print(f"=== Page {no} ===")

    params = {
        "artistId": artist,
        "type": work_type,
        "page": no
    }
    resp = requests.get("https://www.artnet.com/artists/ArtistOverview.aspx/GetArtworks", params=params, headers=HEADERS)
    resp.raise_for_status()
    resp = resp.json()
    if "d" not in resp:
        print("Finished.")
        break

    j = json.loads(resp["d"])
    if not j["items"]:
        print("Finished.")
        break

    p = Pool(processes=8)
    for res in p.imap_unordered(worker, j["items"]):
        pass
    p.close()
    p.join()

    no += 1
