#!/usr/bin/env python

import os
import os.path
import sys
import urllib.parse
import re
from bs4 import BeautifulSoup
import requests
from pathvalidate import sanitize_filepath
from multiprocessing.pool import ThreadPool as Pool


artist = sys.argv[1]
if len(sys.argv) > 2:
    cookie = sys.argv[2]
else:
    cookie = None

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "www.mutualart.com",
    "Cookie": "" if not cookie else f"blca={cookie}",
    "X-Requested-With": "XMLHttpRequest"
}

re_artist_name = re.compile(r'(Artwork by|After)? ([^,]*),')
re_date = re.compile(r'([0-9]+)')


def worker(artwork):
    page_url = urllib.parse.urljoin("https://www.mutualart.com", artwork["url"])
    resp = requests.get(page_url, headers=HEADERS)
    page = BeautifulSoup(resp.text, features="html5lib")
    slide = page.find("div", class_="slide")
    if not slide:
        print("*** SKIPPING (no artwork): " + page_url)
        return

    url = slide.find("img").get("data-src")
    path = sanitize_filepath(os.path.join("mutualart", artist, os.path.basename(url)))
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

    artist_name = re_artist_name.search(artwork["image"]["title"]).group(2).removeprefix("Artwork by ")
    print(artist_name)
    artwork_name = artwork["name"]
    medium = artwork["mediumText"]
    creationDate = re_date.search(artwork["creationDate"])
    txt = f"{artist_name}, {artwork_name}, {medium}"
    if creationDate:
        txt += ", " + creationDate.group(1)

    txt_name = os.path.splitext(os.path.basename(path))[0] + ".txt"
    txt_path = os.path.join(os.path.dirname(path), txt_name)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt)


no = 0
while True:
    print(f"=== Page {no} ===")
    data = {
        "page": no,
        "artistId": artist
    }
    resp = requests.post(f"https://www.mutualart.com/api/artists/artworks", headers=HEADERS, data=data)
    resp.raise_for_status()
    resp = resp.json()
    if "Data" not in resp or not resp["Data"]["Artworks"]:
        print("Finished.")
        exit(0)

    p = Pool(processes=8)
    for res in p.imap_unordered(worker, resp["Data"]["Artworks"]):
        pass
    p.close()
    p.join()

    no += 1
