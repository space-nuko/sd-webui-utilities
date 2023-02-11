#!/usr/bin/env python

import os
import os.path
import sys
from bs4 import BeautifulSoup
import requests
from pathvalidate import sanitize_filepath
from multiprocessing.pool import ThreadPool as Pool


ARTIST = sys.argv[1]


def worker(painting):
    path = sanitize_filepath(os.path.join("wikiart", ARTIST, os.path.basename(painting["image"])))
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.exists(path):
        print("*** SKIPPING (exists): " + path)
    else:
        resp = requests.get(painting["image"])
        print("Saving: " + painting["image"])
        with open(path, "wb") as f:
            for chunk in resp:
                f.write(chunk)

    txt_name = os.path.splitext(os.path.basename(path))[0] + ".txt"
    txt_path = os.path.join(os.path.dirname(path), txt_name)
    title = painting['title'].replace(",", "")
    txt = f"{painting['artistName']}, {title}, {painting['year']}"

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt)


no = 1
while True:
    print(f"=== Page {no} ===")
    resp = requests.get(f"https://www.wikiart.org/en/{ARTIST}/mode/all-paintings", params={"json": 2, "layout": "new", "page": no, "resultType": "masonry"})
    resp = resp.json()
    if "Paintings" not in resp or resp["Paintings"] is None:
        print("Finished.")
        exit(0)

    p = Pool(processes=8)
    for res in p.imap_unordered(worker, resp["Paintings"]):
        pass
    p.close()
    p.join()

    no += 1
