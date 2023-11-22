#!/usr/bin/env python
# Usage: browse "all artist's artworks" page, look in Inspector tab for call to /search?, pass the integer ID to script

import os
import os.path
import sys
import urllib.parse
from bs4 import BeautifulSoup
import requests
from pathvalidate import sanitize_filepath
from multiprocessing.pool import ThreadPool as Pool


artist = int(sys.argv[1])
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
}


def worker(work):
    url = (
        work["media"]["base_url"]
        + f"/img/orig/work/{work['media']['data']['version_orig']}/{work['media']['media_id']}.webp"
    )
    path = sanitize_filepath(
        os.path.join("arthive", str(artist), os.path.basename(url))
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.exists(path):
        print("*** SKIPPING (exists): " + url)
    else:
        print("Saving: " + url)
        resp = requests.get(url)
        if resp.status_code != 200:
            raise Exception(resp.content)
        with open(path, "wb") as f:
            for chunk in resp:
                f.write(chunk)

    artist_name = work["artist"]["full_name"].replace(",", "")
    txt_name = os.path.splitext(os.path.basename(path))[0] + ".txt"
    txt_path = os.path.join(os.path.dirname(path), txt_name)
    title = work["name"]
    txt = f"{artist_name}, {title}"

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt)


no = 1
while True:
    print(f"=== Page {no} ===")
    resp = requests.get(
        f"https://arthive.com/action/vue/works/search",
        params={"artist": artist, "p": no},
        headers=HEADERS,
    )
    resp = resp.json()
    if "works" not in resp or not resp["works"]:
        print("Finished.")
        exit(0)

    p = Pool(processes=8)
    for res in p.imap_unordered(worker, resp["works"]):
        pass
    p.close()
    p.join()

    no += 1
