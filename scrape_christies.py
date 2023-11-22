#!/usr/bin/env python

import os
import os.path
import sys
import urllib.parse
from bs4 import BeautifulSoup
import requests
from pathvalidate import sanitize_filepath
from multiprocessing.pool import ThreadPool as Pool


artist = sys.argv[1]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
}


def worker(lot):
    url = lot["image"]["image_src"]
    path = sanitize_filepath(os.path.join("christies", artist, os.path.basename(url))).replace("jpgmode=max", "jpg")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.exists(path):
        print("*** SKIPPING (exists): " + path)
    else:
        resp = requests.get(url)
        print("Saving: " + url)
        with open(path, "wb") as f:
            for chunk in resp:
                f.write(chunk)

    artist_name = lot["title_primary_txt"].replace(",", "")
    txt_name = os.path.splitext(os.path.basename(path))[0] + ".txt"
    txt_path = os.path.join(os.path.dirname(path), txt_name)
    title = lot["title_secondary_txt"]
    txt = f"{artist_name}, {title}"

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt)


no = 1
while True:
    print(f"=== Page {no} ===")
    params = {
        "keyword": artist,
        "page": no,
        "is_past_lots": True,
        "sortby": "relevance",
        "language": "en",
        "datasourceId": "datasourceId=182f8bb2-d729-4a38-b539-7cf1a901cf2e"
    }
    resp = requests.get(f"https://www.christies.com/api/discoverywebsite/search/lot-infos", params=params, headers=HEADERS)
    print(resp.content)
    resp = resp.json()
    if "lots" not in resp or not resp["lots"]:
        print("Finished.")
        exit(0)

    p = Pool(processes=8)
    for res in p.imap_unordered(worker, resp["lots"]):
        pass
    p.close()
    p.join()

    no += 1
