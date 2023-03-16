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
from urllib.parse import urlparse, parse_qs, urljoin


artist = sys.argv[1]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
}


def worker(td):
    a = td.find("a")
    resp = requests.get(urljoin("http://www.artnet.com/usernet/awc/awc_thumbnail.asp", a.get("href")), headers=HEADERS)
    page = BeautifulSoup(resp.text, features="html5lib")
    tables = page.find_all("table")
    url = tables[6].find("img").get("src")

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

    artist_name = page.find("a", id="artisth1").text
    artwork_name = tables[7].find_all("td")[4].text
    txt = f"{artist_name}, {artwork_name}"

    txt_name = os.path.splitext(os.path.basename(path))[0] + ".txt"
    txt_path = os.path.join(os.path.dirname(path), txt_name)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt)


no = 1
while True:
    print(f"=== Page {no} ===")

    params = {
        "AID": artist,
        "GID": artist,
        "CID": 15766,
        "page": no,
        "recs": 6,
        "works_of_art": 1
    }
    resp = requests.post("http://www.artnet.com/usernet/awc/awc_thumbnail.asp", params=params)
    page = BeautifulSoup(resp.text, features="html5lib")
    tds = page.find_all("td", class_="regText")
    if not tds:
        print("Finished.")
        exit(0)

    p = Pool(processes=8)
    for res in p.imap_unordered(worker, tds):
        pass
    p.close()
    p.join()

    no += 1
