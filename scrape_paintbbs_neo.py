#!/usr/bin/env python

import os
import os.path
import sys
from bs4 import BeautifulSoup
import requests
from pathvalidate import sanitize_filepath
from multiprocessing.pool import ThreadPool as Pool
import urllib.parse


#BASE_URL = "https://paintbbs.sakura.ne.jp"
#BASE_URL = "https://paintbbs.sakura.ne.jp/pastlog/poti/relm"
BASE_URL = "https://paintbbs.sakura.ne.jp/pastlog/poti/2"


sitename = urllib.parse.urlparse(BASE_URL).netloc
artist = sys.argv[1]
outpath = os.path.join(sys.argv[2], sitename, artist)




def worker(link):
    resp = requests.get(link)
    page = BeautifulSoup(resp.text, features="html5lib")
    posted_image = page.find(class_="posted_image")
    if not posted_image:
        print(f"*** SKIPPING LINK (no images): {link}")
        return

    img = posted_image.find("img")

    url = urllib.parse.urljoin(resp.url, img.get("src"))
    heading = page.find(class_="article_title").text
    path = sanitize_filepath(os.path.join(outpath, os.path.basename(url)), platform="Windows")
    print(url + " -> " + path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    resp = requests.get(url, stream=True)

    if os.path.exists(path):
        print("*** SKIPPING (exists): " + path)
    else:
        #print(f"Saving: {heading} - {path}")
        with open(path, "wb") as f:
            for chunk in resp:
                f.write(chunk)


no = 0
while True:
    print(f"=== Page {no} ===")
    resp = requests.get(BASE_URL + "/newimage.php", params={"page": no * 60 + 1, "artist": artist, "radio": 2})

    page = BeautifulSoup(resp.text, features="html5lib")
    newimg = page.find(class_="newimg")

    links = list(set(filter(lambda x: x, [BASE_URL + "/" + a.get("href") for a in newimg.find_all("a")])))
    print(links)
    if not links:
        print("Finished.")
        break

    p = Pool(processes=8)
    for res in p.imap_unordered(worker, links):
        pass
    p.close()
    p.join()

    no += 1
