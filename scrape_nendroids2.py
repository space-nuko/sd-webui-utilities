#!/usr/bin/env python

# Scrapes the international catalogue that has discontinued products included.

import os
import os.path
from bs4 import BeautifulSoup
import requests
from pathvalidate import sanitize_filepath
from multiprocessing.pool import ThreadPool as Pool


def worker(link):
    resp = requests.get(link)
    page = BeautifulSoup(resp.text, features="html5lib")
    produkt_gallery = page.find(class_="itemPhotos")
    if not produkt_gallery:
        print(f"*** SKIPPING LINK (no images): {link}")
        return

    for img in produkt_gallery.find_all("img", itemprop="image"):
        url = "https:" + img.get("src")
        heading = page.find(itemprop="name").text
        path = sanitize_filepath("./Figma/" + heading.replace("/", "-") + "/" + os.path.basename(url))
        print(url)
        print(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        resp = requests.get(url, stream=True)

        if os.path.exists(path):
            print("*** SKIPPING (exists): " + path)
        else:
            print(f"Saving: {heading} - {path}")
            with open(path, "wb") as f:
                for chunk in resp:
                    f.write(chunk)

        txt_name = os.path.splitext(os.path.basename(path))[0] + ".txt"
        txt_path = os.path.join(os.path.dirname(path), txt_name)

        txt = f"{heading}"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt)


no = 1
while True:
    print(f"=== Page {no} ===")
    resp = requests.get(f"https://www.goodsmile.info/en/products/category/figma/page/{no}")

    page = BeautifulSoup(resp.text, features="html5lib")
    produkts = page.find(class_="hitList")

    links = list(set(filter(lambda x: x, [a.get("href") for a in produkts.find_all("a")])))
    if not links:
        print("Finished.")
        break

    p = Pool(processes=8)
    for res in p.imap_unordered(worker, links):
        pass
    p.close()
    p.join()

    no += 1
