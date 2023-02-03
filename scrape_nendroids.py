#!/usr/bin/env python

# Not as suspicious as the name sounds!

import os
import os.path
from bs4 import BeautifulSoup
import requests
from pathvalidate import sanitize_filepath
from multiprocessing.pool import ThreadPool as Pool


def worker(link):
    resp = requests.get(link)
    page = BeautifulSoup(resp.text, features="html5lib")
    produkt_gallery = page.find(id="product-gallery")
    for img in produkt_gallery.find_all("a"):
        url = img.get("href")
        path = sanitize_filepath("." + url[url.find('/image'):])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        resp = requests.get(url, stream=True)

        if os.path.exists(path):
            print("*** SKIPPING (exists): " + path)
        else:
            print("Saving: " + path)
            with open(path, "wb") as f:
                for chunk in resp:
                    f.write(chunk)

        txt_name = os.path.splitext(os.path.basename(path))[0] + ".txt"
        txt_path = os.path.join(os.path.dirname(path), txt_name)

        heading = page.find(class_="heading-title").text

        txt = f"{heading}, nendroid, photo \(medium\)"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt)


no = 1
while True:
    print(f"=== Page {no} ===")
    resp = requests.get(f"https://www.goodsmileus.com/category/nendoroid-268?page={no}")

    page = BeautifulSoup(resp.text, features="html5lib")
    produkts = page.find(class_="main-products")

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
