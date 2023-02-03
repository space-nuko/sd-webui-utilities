#!/usr/bin/env python

# /hdg/ archive script
# Searches for archived threads on /h/ with "https://rentry.org/voldy" in the OP
# and downloads all images/catbox files from them
#
# Dependencies: pip install requests pathvalidate urlextract mimetypes
#
# Usage: python hdg_archive.py [output folder] [--board h] [--process-count 8] [--catbox-only] [--images-only] [--ignore-deleted]

import requests
import json
import sys
import os
import os.path
import re
import mimetypes
from pathvalidate import sanitize_filepath
from urlextract import URLExtract
import argparse
from multiprocessing.pool import ThreadPool as Pool

import signal

g_run_loops = True
def signal_handler(signum, frame):
   global g_run_loops
   g_run_loops = False


parser = argparse.ArgumentParser(description='Optional app description')
parser.add_argument('path', type=str, help='Path to output directory')
parser.add_argument('--board', type=str, default="h", help='Board to search for threads')
parser.add_argument('--process-count', type=int, default=8, help='Number of threads to use for downloading')
parser.add_argument('--catbox-only', action='store_true', help='Only download catbox links')
parser.add_argument('--images-only', action='store_true', help='Only download images and videos (no .safetensors, .zip, etc)')
parser.add_argument('--ignore-deleted', action='store_true', help='Ignore deleted posts')

args = parser.parse_args()


sites = {
    "https://desuarchive.org": ["a", "aco", "an", "c", "cgl", "co", "d", "fit", "g", "his", "int", "k", "m", "mlp", "mu", "q", "qa", "r9k", "tg", "trash", "vr", "wsg"],
    "https://archiveofsins.com": ["h", "hc", "hm", "i", "lgbt", "r", "s", "soc", "t", "u"]
}

board_to_site = {}
for site, boards in sites.items():
    for board in boards:
        board_to_site[board] = site


site = board_to_site.get(args.board, None)
if not site:
    print(f"Error: Unsupported 4chan archived board {args.board}")
    exit(1)


passed_path = args.path


sitename = os.path.splitext(os.path.basename(site))[0]
BASE_URL = site
OUTPATH = os.path.join(passed_path, sitename, args.board)
catbox_re = re.compile(r'^http(|s)://(files|litter).catbox.moe/.+')
mega_re = re.compile(r'^http(|s)://mega(\.co|).nz/.+')
catbox_file_re = re.compile(r'^catbox_(.*)\.(.*)')
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246",
}


class BaseDownloader():
    def __init__(self, site, board):
        self.site = site
        self.board = board

    def name(self):
        pass

    def get_posts(self, page):
        pass

    def get_thread(self, post):
        pass

    def download_op_media(self, thread):
        pass

    def extract_links(self, thread):
        pass


class FourChanDownloader(BaseDownloader):
    def __init__(self, site, board):
        self.site = site
        self.board = board

    def name(self):
        return f"{self.site}/{self.board}"

    def get_posts(self, page):
        result = requests.get(BASE_URL + "/_/api/chan/search/", params={"board": args.board, "text": "https://rentry.org/voldy", "page": page}, headers=HEADERS)
        result = result.json()

        if "0" not in result:
            return None

        posts = result["0"]["posts"]
        return posts

    def get_thread(self, post):
        thread_num = post["thread_num"]

        print(f"=== THREAD: {thread_num}")

        resp = requests.get(BASE_URL + "/_/api/chan/thread/", params={"board": args.board, "num": thread_num}, headers=HEADERS)
        thread = resp.json()

        if thread_num not in thread:
            print(f"!!! SKIP THREAD (not found): {thread_num}")
            return None

        return thread[thread_num]

    def _extract_links(self, basepath, posts):
        links = []
        mega_links = []
        seen = {}
        for post_id, post in posts.items():
            bp = basepath
            if post["deleted"] == "1":
                if args.ignore_deleted:
                    continue
                else:
                    bp = os.path.join(basepath, "deleted")

            post_media = post.get("media")
            if post_media and not args.catbox_only:
                link = get_media_link(bp, post_media)
                if link and not link[1].lower() in seen:
                    links.append(link)
                    seen[link[1].lower()] = True

            l, ml = get_post_links(bp, post)
            for link in l:
                if link and not link[1].lower() in seen:
                    links.append(link)
                    seen[link[1].lower()] = True

            mega_links.extend(ml)

        mega_path = os.path.join(basepath, "mega.txt")
        os.makedirs(os.path.dirname(mega_path), exist_ok=True)
        print(f"Saving {len(mega_links)} mega links: {mega_path}")
        with open(mega_path, "w") as f:
            f.write("\n".join(mega_links))

        return links

    def extract_links(self, thread):
        thread_num = thread["op"]["num"]
        basepath = os.path.join(OUTPATH, thread_num)

        links = []

        op_media = thread["op"].get("media")
        if op_media:
            link = get_media_link(basepath, op_media)
            if link:
                links.append(link)

        if "posts" not in thread:
            print(f"!!! SKIP THREAD (no posts): {thread_num}")
            return links

        posts = thread["posts"]
        return links + self._extract_links(basepath, posts)


os.makedirs(OUTPATH, exist_ok=True)
print(f"Saving files in {site}/{args.board} to {OUTPATH}...")


def save_link(basepath, url, real_name):
    global g_run_loops
    if not g_run_loops:
        return

    if args.images_only:
        mimetype = mimetypes.guess_type(url)[0]
        if not mimetype or (not mimetype.startswith("image/") and not mimetype.startswith("video/")):
            return

    path = os.path.join(basepath, real_name)
    if len(path) >= 259:
        p, e = os.path.splitext(path)
        p = p[:250]
        path = f"{p}{e}"
        path = sanitize_filepath(path, platform="Windows")

    if os.path.isfile(path):
        print(f"--- SKIPPING (file exists): {path}")
        return

    print(f"Saving: {path}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    resp = requests.get(url, stream=True, headers=HEADERS)
    if resp.status_code == 200:
        try:
            with open(path, 'wb') as f:
                for chunk in resp:
                    if not g_run_loops:
                        raise KeyboardInterrupt()

                    f.write(chunk)
        except KeyboardInterrupt:
            print(f"*** DELETING partial file: {path}")
            os.unlink(path)
    else:
        print(f"*** FAILED saving: {url}")


def get_media_link(basepath, media):
    m = catbox_file_re.match(media["media_filename"])
    if m: # Convert catbox userscript link
        catbox_id = m.group(1)
        catbox_ext = m.group(2)
        real_name = f"{catbox_id}.{catbox_ext}"
        url = f"https://files.catbox.moe/{real_name}"
        basepath = os.path.join(basepath, "catbox")
    else:
        if args.catbox_only:
            return
        media_basename, media_ext = os.path.splitext(media["media"])
        media_filename = os.path.splitext(media["media_filename"])[0]
        real_name = f"{media_basename}_{media_filename}{media_ext}"
        url = media["media_link"]
    return (basepath, url, real_name)


def get_post_links(basepath, post):
    basepath = os.path.join(basepath, "catbox")
    comment = post["comment"]
    if not comment:
        return [], []

    links = []
    mega_links = []

    extractor = URLExtract()
    urls = extractor.find_urls(comment)
    for url in urls:
        if catbox_re.match(url):
            real_name = os.path.basename(url)
            links.append((basepath, url, real_name))
        elif mega_re.match(url):
            mega_links.append(url)

    return links, mega_links


def worker(t):
    basepath, url, real_name = t
    save_link(basepath, url, real_name)


page = 1
downloader = FourChanDownloader(site, board)


while True:
    print(f"*** Page {page} ***")

    posts = downloader.get_posts(page)
    if posts is None:
        print("Finished")
        break

    for post in posts:
        thread = downloader.get_thread(post)
        if not thread:
            continue

        links = downloader.extract_links(thread)

        print(f"+++ {len(links)} links to download.")

        original_sigint = signal.getsignal(signal.SIGINT)

        p = Pool(processes=max(1, args.process_count))
        signal.signal(signal.SIGINT, signal_handler)

        for res in p.imap_unordered(worker, links):
            if not g_run_loops:
                p.close()
                p.join()
                print("Interrupted, exiting")
                exit(1)

        p.close()
        p.join()
        signal.signal(signal.SIGINT, original_sigint)

    page += 1
