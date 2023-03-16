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
    found = False
    for image in lot["lotImages"]:
        url = urllib.parse.urljoin("https://assets.phillips.com/image/upload/v1", image["imagePath"])
        path = sanitize_filepath(os.path.join("phillips", artist, os.path.basename(url)))
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if os.path.exists(path):
            print("*** SKIPPING (exists): " + path)
        else:
            found = True
            resp = requests.get(url)
            if resp.status_code != 200:
                print(f"!!! FAILED saving: {url}")
                return
            print("Saving: " + url)
            with open(path, "wb") as f:
                for chunk in resp:
                    f.write(chunk)

        artist_name = lot["makerName"].replace(",", "")
        title = lot["description"]
        year = lot["circa"]
        txt = f"{artist_name}, {title}, {year}"

        txt_name = os.path.splitext(os.path.basename(path))[0] + ".txt"
        txt_path = os.path.join(os.path.dirname(path), txt_name)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt)
    return found


no = 1
while True:
    print(f"=== Page {no} ===")
    params = {
        "page": no,
        "resultsperpage": 24,
        "lotStatus": "past",
    }
    resp = requests.get(f"https://api.phillips.com/api/maker/{artist}/lots", params=params, headers=HEADERS)
    resp = resp.json()
    if "data" not in resp or not resp["data"]:
        print("Finished.")
        exit(0)

    found = False
    p = Pool(processes=8)
    for res in p.imap_unordered(worker, resp["data"]):
        found = found or res
    p.close()
    p.join()

    no += 1

    if not found:
        print("Finished.")
        break
