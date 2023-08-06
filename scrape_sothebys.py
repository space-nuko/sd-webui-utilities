#!/usr/bin/env python

import sys
import os
import urllib.parse
import re
import json
import urllib
from bs4 import BeautifulSoup
import requests
from pathvalidate import sanitize_filepath
from multiprocessing.pool import ThreadPool as Pool
from urllib.parse import urlparse, parse_qs, urljoin


query = sys.argv[1]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
    "Host": "o28sy4q7wu-dsn.algolia.net",
}


def worker(item):
    image_url = item["image"]
    parsed_url = urlparse(image_url)
    parsed_qs = parse_qs(parsed_url.query)
    url = parsed_qs["url"][0]
    if url is None:
        print(f"!!! WARNING: No original URL: {image_url}")
        url = image_url

    artist = item["artistName"]
    if artist is None:
        print("*** SKIPPING (no artist): " + url)
        return

    path = sanitize_filepath(os.path.join("sothebys", artist, os.path.basename(url)))
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.exists(path):
        print("*** SKIPPING (exists): " + path)
    else:
        resp = requests.get(url)
        if resp.status_code != 200:
            print(f"!!! FAILED saving: {url}")
            return
        print("Saving: " + url)
        with open(path, "wb") as f:
            for chunk in resp:
                f.write(chunk)

    artists = ", ".join(item["artists"])
    artwork_name = item["title"]
    departments = ", ".join(item["departments"])
    txt = f"{artists}, {artwork_name}, {departments}"

    if "fullText" in item:
        txt += f", {item['fullText']}"

    txt_name = os.path.splitext(os.path.basename(path))[0] + ".txt"
    txt_path = os.path.join(os.path.dirname(path), txt_name)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt)


no = 1
while True:
    print(f"=== Page {no} ===")

    req_params = {
        "highlightPreTag": "<ais-highlight-0000000000>",
        "highlightPostTag": "</ais-highlight-0000000000>",
        "clickAnalytics": "true",
        "hitsPerPage": "51",
        "maxValuesPerFacet": "9999",
        "page": str(no - 1),
        "filters": 'type:"Bid" OR type:"Buy Now" OR type:"Lot" OR type:"Private Sale" OR type:"Retail"',
        "query": query,
        "facets": '["type","endDate","lowEstimate","highEstimate","artists"]',
        "tagFilters": "",
    }
    params = {
        "requests": [
            {
                "indexName": "bsp_dotcom_prod_en",
                "params": urllib.parse.urlencode(req_params),
            }
        ],
    }
    query_params = {
        "x-algolia-agent": "Algolia for JavaScript (4.2.0); Browser (lite); react (16.13.1); react-instantsearch (6.7.0); JS Helper (3.2.2)",
        "x-algolia-api-key": "e732e65c70ebf8b51d4e2f922b536496",
        "x-algolia-application-id": "O28SY4Q7WU",
    }
    resp = requests.post(
        "https://o28sy4q7wu-dsn.algolia.net/1/indexes/*/queries",
        data=json.dumps(params),
        params=query_params,
        headers=HEADERS,
    )
    resp.raise_for_status()
    resp = resp.json()
    if "results" not in resp:
        print("Finished.")
        break

    j = resp["results"]
    if not j:
        print("Finished.")
        break

    j = j[0]["hits"]
    if not j:
        print("Finished.")
        break

    p = Pool(processes=8)
    for res in p.imap_unordered(worker, j):
        pass
    p.close()
    p.join()

    no += 1
