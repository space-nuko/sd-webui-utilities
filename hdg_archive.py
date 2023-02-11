#!/usr/bin/env python

# /hdg/ archive script
# Searches for archived threads on /h/ with "https://rentry.org/voldy" in the OP
# and downloads all images/catbox files from them
#
# Dependencies: pip install requests pathvalidate urlextract beautifulsoup4 dateutil
#
# Usage: python hdg_archive.py [output folder] [--board h] [--process-count 8] [--catbox-only] [--images-only] [--ignore-deleted]
#
# Set --board to "liveuranus" for fate.5ch.net, "hdg" for the haven

import requests
import json
import sys
import os
import os.path
import re
import mimetypes
from datetime import datetime
import dateutil.parser
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filepath
from urlextract import URLExtract
import urllib.parse
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
parser.add_argument('--num-threads', '-n', type=int, default=None, help='Archive only the N most recent threads')
parser.add_argument('--sanitize-filepaths', action='store_true', help='Strip non-ASCII characters from output filepaths')


args = parser.parse_args()


sites = {
    "https://desuarchive.org": ["a", "aco", "an", "c", "cgl", "co", "d", "fit", "g", "his", "int", "k", "m", "mlp", "mu", "q", "qa", "r9k", "tg", "trash", "vr", "wsg"],
    "https://archiveofsins.com": ["h", "hc", "hm", "i", "lgbt", "r", "s", "soc", "t", "u"],
#   "https://warosu.org": ["vt"],
    "https://archive.palanq.win": ["vt", "e"],
    "https://8chan.moe": ["hdg"],
    "https://fate.5ch.net": ["liveuranus"]
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
print(site)


sitename = os.path.splitext(os.path.basename(site))[0]
BASE_URL = site
OUTPATH = os.path.join(passed_path, sitename, args.board)
catbox_re = re.compile(r'^http(|s)://files.catbox.moe/.+')
litterbox_re = re.compile(r'^http(|s)://litter.catbox.moe/.+')
mega_re = re.compile(r'^http(|s)://mega(\.co|).nz/.+')
majinai_re = re.compile(r'^http(|s)://(www.|)majinai.art/.+\.(gif|png|jpg|jpeg)')
catbox_file_re = re.compile(r'^catbox_(.*)\.(.*)')
imgur_re = re.compile(r'^http(|s)://(i.|)imgur.com/.+\.(gif|png|jpg|jpeg)')
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246",}


class BaseDownloader():
    def __init__(self, site, board):
        self.site = site
        self.board = board
        self.headers = HEADERS

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


class FoolFuukaDownloader(BaseDownloader):
    def __init__(self, site, board):
       super(FoolFuukaDownloader, self).__init__(site, board)

    def name(self):
        return f"{self.site}/{self.board}"

    def get_posts(self, page):
        result = requests.get(BASE_URL + "/_/api/chan/search/", params={"board": args.board, "text": "https://rentry.org/voldy", "page": page}, headers=self.headers)
        result = result.json()

        if "0" not in result:
            return None

        posts = filter(lambda p: p["op"] == "1" and p["board"]["shortname"] == args.board, result["0"]["posts"])
        return posts

    def get_thread(self, post):
        thread_num = post["thread_num"]
        print(thread_num)
        print(post["num"])

        print(f"=== THREAD: {thread_num}")

        resp = requests.get(BASE_URL + "/_/api/chan/thread/", params={"board": args.board, "num": thread_num}, headers=self.headers)
        thread = resp.json()

        basepath = os.path.join(OUTPATH, thread_num)

        if thread_num not in thread:
            print(f"!!! SKIP THREAD (not found): {thread_num}")
            return None

        if resp.status_code == 200:
           os.makedirs(basepath, exist_ok=True)
           with open(os.path.join(basepath, "thread.json"), "w", encoding="utf-8") as f:
              f.write(resp.text)

        return thread[thread_num]


    def get_media_link(self, basepath, media, mtime):
        m = catbox_file_re.match(media["media_filename"])
        if m: # Convert catbox userscript link
            catbox_id = m.group(1)
            catbox_ext = m.group(2)
            real_name = f"{catbox_id}.{catbox_ext}"
            url = f"https://files.catbox.moe/{real_name}"
            basepath = os.path.join(basepath, "catbox")
        else:
            if args.catbox_only:
                return None
            media_basename, media_ext = os.path.splitext(media["media"])
            media_filename = os.path.splitext(media["media_filename"])[0]
            real_name = f"{media_basename}_{media_filename}{media_ext}"
            url = media["media_link"]
        return (basepath, url, real_name, mtime)


    def get_post_links(self, basepath, post, mtime):
        comment = post["comment"]
        if not comment:
            return [], []

        links = []
        mega_links = []

        extractor = URLExtract()
        urls = extractor.find_urls(comment)
        for url in urls:
            if catbox_re.match(url):
                bp = os.path.join(basepath, "catbox")
                real_name = os.path.basename(url)
                links.append((bp, url, real_name, mtime))
            elif litterbox_re.match(url):
                bp = os.path.join(basepath, "litterbox")
                real_name = os.path.basename(url)
                links.append((bp, url, real_name, mtime))
            elif mega_re.match(url):
                mega_links.append(url)
            elif majinai_re.match(url):
                bp = os.path.join(basepath, "majinai")
                real_name = os.path.basename(url)
                links.append((bp, url, real_name, mtime))

        return links, mega_links


    def _extract_links(self, basepath, posts):
        links = []
        mega_links = []
        seen = {}
        for post_id, post in posts.items():
            bp = basepath
            mtime = post["timestamp"]
            if post["deleted"] == "1":
                if args.ignore_deleted:
                    continue
                else:
                    bp = os.path.join(basepath, "deleted")

            post_media = post.get("media")
            if post_media:
                link = self.get_media_link(bp, post_media, mtime)
                if link and not link[1].lower() in seen:
                    links.append(link)
                    seen[link[1].lower()] = True

            l, ml = self.get_post_links(bp, post, mtime)
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
            mtime = thread["op"]["timestamp"]
            link = self.get_media_link(basepath, op_media, mtime)
            if link:
                links.append(link)

        if "posts" not in thread:
            print(f"!!! SKIP THREAD (no posts): {thread_num}")
            return links

        posts = thread["posts"]
        return links + self._extract_links(basepath, posts)


class FiveChanDownloader(BaseDownloader):
    def __init__(self, site, board):
       super(FiveChanDownloader, self).__init__(site, board)
       self.query = "なんJNVA"

    def name(self):
        return "5chan"

    def get_posts(self, page):
        if page > 1:
           return None

        query = urllib.parse.quote(self.query)
        print(query)
        resp = requests.get(f"https://find.5ch.net/search?q={query}", headers=self.headers)
        page = BeautifulSoup(resp.text, features="html5lib")
        posts = []

        seen = {}
        pages = []

        if os.path.isfile("5ch_cache.txt"):
           with open("5ch_cache.txt", "r") as f:
              for url in f.read().split("\n"):
                 if "liveuranus" in url:
                     seen[url] = True

        links = []
        hrefs = list(page.find_all("a", class_="list_line_link"))
        for i, a in enumerate(hrefs):
           link = a.get("href").strip("/")
           link_title = a.find("div", class_="list_line_link_title").text.strip()
           if link not in seen or i == len(hrefs) - 1:
              print(f"Add link: {link_title} ({link})")
              links.append(link)
              seen[link] = True
           else:
              print(f"Link in cache: {link_title} ({link})")

        r = re.compile(r'/(\d*)$')
        links.append(list(sorted(seen.keys(), key=lambda l: int(r.search(l).groups(1)[0]), reverse=True))[-1])

        while links:
           link = links.pop()
           resp = requests.get(link, headers=self.headers)
           page = BeautifulSoup(resp.text, features="html5lib")
           page_title = page.find("h1", class_="title").text.strip()
           if self.query not in page_title and "なんJnove" not in page_title:
              print(f"SKIPPING THREAD (unrelated): {page_title} (link)")
              continue

           pages.append((link, page))
           print(f"Scan page: {page_title} ({link})")
           for i in range(1, 40):
               first = page.find("div", class_="post", id=str(i))
               if not first:
                  print(f"SKIPPING THREAD (no posts): {link}")
                  continue

               extractor = URLExtract()
               urls = extractor.find_urls(first.text)
               for url in urls:
                  url = url.lower().strip("/").replace("http://", "https://")
                  if "fate.5ch.net/test/read.cgi/" in url and not url in seen:
                     seen[url] = True
                     links.append(url)
                     print(f"Found new link: {url}")

                     with open("5ch_cache.txt", "w") as f:
                        f.write("\n".join(seen.keys()))

        downloaded = {k[0]: True for k in pages}
        for link in seen.keys():
           if not link in downloaded:
              pages.append((link, None))

        pages = sorted(pages, key=lambda l: l[0], reverse=True)

        return pages

    def get_thread(self, post):
       link, page = post

       r = re.compile(r'liveuranus/(\d*)')
       thread_num = r.search(link).groups(1)[0]
       print(f"=== THREAD: {thread_num}")

       if not page:
           resp = requests.get(link, headers=self.headers)
           if resp.status_code == 200:
               page = BeautifulSoup(resp.text, features="html5lib")

       basepath = os.path.join(OUTPATH, thread_num)
       os.makedirs(basepath, exist_ok=True)
       if page:
          with open(os.path.join(basepath, "thread.html"), "w", encoding="utf-8") as f:
             f.write(str(page))

       return (link, page)

    def extract_links(self, thread):
        url, page = thread
        r = re.compile(r'liveuranus/(\d*)')
        thread_num = r.search(url).groups(1)[0]
        basepath = os.path.join(OUTPATH, thread_num)
        thread = page.find("div", class_="thread")

        links = []
        mega_links = []

        date_re = re.compile(r'\([^)]+\)')
        extractor = URLExtract()
        for post in thread.find_all("div", class_="post"):
            date = post.find("span", class_="date")
            if "Over" in date.text: # Over 1000
               continue

            date_str = re.sub(date_re, "", date.text)
            mtime = int(datetime.timestamp(datetime.strptime(date_str, '%Y/%m/%d %H:%M:%S.%f')))

            message = post.find("div", class_="message")
            urls = extractor.find_urls(message.text)
            for url in urls:
                url = url.replace("http://jump.5ch.net/?", "")
                real_name = os.path.basename(url)
                print(url)
                if catbox_re.match(url):
                    links.append((os.path.join(basepath, "catbox"), url, real_name, mtime))
                if litterbox_re.match(url):
                    links.append((os.path.join(basepath, "litterbox"), url, real_name, mtime))
                elif mega_re.match(url):
                    mega_links.append(url)
                elif imgur_re.match(url):
                    real_name = os.path.basename(url)
                    links.append((os.path.join(basepath, "imgur"), url, real_name, mtime))
                elif majinai_re.match(url):
                    real_name = os.path.basename(url)
                    links.append((os.path.join(basepath, "majinai"), url, real_name, mtime))

        mega_path = os.path.join(basepath, "mega.txt")
        os.makedirs(os.path.dirname(mega_path), exist_ok=True)
        print(f"Saving {len(mega_links)} mega links: {mega_path}")
        with open(mega_path, "w") as f:
            f.write("\n".join(mega_links))

        return links


class EightChanDownloader(BaseDownloader):
    def __init__(self, site, board):
       super(EightChanDownloader, self).__init__(site, board)
       self.headers["Cookie"] = "splash=1;"

    def name(self):
        return f"{self.site}/{self.board}"

    def get_posts(self, page):
        if page > 1:
           return None
        result = requests.get(f"{BASE_URL}/{self.board}/catalog.json", params={"page": page}, headers=self.headers)
        result = result.json()

        if not result:
            return None

        return result

    def get_thread(self, post):
        thread_num = post["threadId"]

        print(f"=== THREAD: {thread_num}")

        resp = requests.get(f"{BASE_URL}/{self.board}/res/{thread_num}.json", headers=self.headers)
        thread = resp.json()

        basepath = os.path.join(OUTPATH, str(thread_num))
        os.makedirs(basepath, exist_ok=True)

        if "posts" not in thread:
            print(f"!!! SKIP THREAD (not found): {thread_num}")
            return None

        if resp.status_code == 200:
           with open(os.path.join(basepath, "thread.json"), "w", encoding="utf-8") as f:
              f.write(resp.text)

        return thread


    def get_file_link(self, basepath, file, mtime):
        m = catbox_file_re.match(file["originalName"])
        if m: # Convert catbox userscript link
            catbox_id = m.group(1)
            catbox_ext = m.group(2)
            real_name = f"{catbox_id}.{catbox_ext}"
            url = f"https://files.catbox.moe/{real_name}"
            basepath = os.path.join(basepath, "catbox")
        else:
            if args.catbox_only:
                return
            media_basename, media_ext = os.path.splitext(os.path.basename(file["path"]))
            media_filename = os.path.splitext(file["originalName"])[0]
            real_name = f"{media_basename}_{media_filename}{media_ext}"
            url = f"{BASE_URL}{file['path']}"
        return (basepath, url, real_name, mtime)


    def get_post_links(self, basepath, post, mtime):
        message = post["message"]
        if not message:
            return [], []

        links = []
        mega_links = []

        extractor = URLExtract()
        urls = extractor.find_urls(message)
        for url in urls:
            if catbox_re.match(url):
                real_name = os.path.basename(url)
                links.append((os.path.join(basepath, "catbox"), url, real_name, mtime))
            elif litterbox_re.match(url):
                real_name = os.path.basename(url)
                links.append((os.path.join(basepath, "litterbox"), url, real_name, mtime))
            elif mega_re.match(url):
                mega_links.append(url)

        return links, mega_links


    def _extract_links(self, basepath, posts):
        links = []
        mega_links = []
        seen = {}
        for post in posts:
            post_files = post.get("files", [])
            mtime = datetime.timestamp(dateutil.parser.isoparse(post["creation"]))
            for post_file in post_files:
                link = self.get_file_link(basepath, post_file, mtime)
                if link and not link[1].lower() in seen:
                    links.append(link)
                    seen[link[1].lower()] = True

            l, ml = self.get_post_links(basepath, post, mtime)
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
        thread_num = thread["threadId"]
        basepath = os.path.join(OUTPATH, str(thread_num))

        links = []

        op_files = thread.get("files", [])
        for file in op_files:
            mtime = datetime.timestamp(dateutil.parser.isoparse(thread["creation"]))
            link = self.get_file_link(basepath, file, mtime)
            if link:
                links.append(link)

        if "posts" not in thread:
            print(f"!!! SKIP THREAD (no posts): {thread_num}")
            return links

        posts = thread["posts"]
        return links + self._extract_links(basepath, posts)


class WarosuDownloader(BaseDownloader):
    def __init__(self, site, board):
       super(WarosuDownloader, self).__init__(site, board)

    def name(self):
        return f"{self.site}/{self.board}"

    def get_posts(self, page):
        result = requests.get(f"{BASE_URL}/{self.board}/", params={"offset": (page-1) * 24, "task": "search", "ghost": "", "search_text": "rentry.org/voldy"}, headers=self.headers)

        if not result:
            return None

        page = BeautifulSoup(result.text, features="html5lib")
        replies = page.find_all("td", class_="reply")

        return replies

    def get_thread(self, post):
        thread_num = post["id"].replace("p", "")
        print(thread_num)

        print(f"=== THREAD: {thread_num}")

        resp = requests.get(f"{BASE_URL}/{self.board}/thread/S{thread_num}", headers=self.headers)

        basepath = os.path.join(OUTPATH, str(thread_num))
        os.makedirs(basepath, exist_ok=True)
        if resp.status_code == 200:
           with open(os.path.join(basepath, "thread.html"), "w", encoding="utf-8") as f:
              f.write(resp.text)

        return BeautifulSoup(resp.text, features="html5lib")


    def get_file_link(self, basepath, post, mtime):
        span = post.find("span", text=re.compile(r'^File:'))
        if not span:
           return None

        split = span.text.split(",", 3)
        original_name = split[2].strip()
        a = post.find("img", class_="thumb").parent
        url = "https:" + a.get("href")

        m = catbox_file_re.match(original_name)
        if m: # Convert catbox userscript link
            catbox_id = m.group(1)
            catbox_ext = m.group(2)
            real_name = f"{catbox_id}.{catbox_ext}"
            url = f"https://files.catbox.moe/{real_name}"
            basepath = os.path.join(basepath, "catbox")
        else:
            if args.catbox_only:
                return
            media_basename, media_ext = os.path.splitext(os.path.basename(url))
            media_filename = os.path.splitext(original_name)[0]
            real_name = f"{media_basename}_{media_filename}{media_ext}"
        return (basepath, url, real_name, mtime)


    def get_post_links(self, basepath, post, mtime):
        message = post.select_one("p", itemprop="text")
        if not message:
            return [], []

        links = []
        mega_links = []

        for a in message.find_all("a"):
            url = a.get("href")
            if catbox_re.match(url):
                real_name = os.path.basename(url)
                links.append((os.path.join(basepath, "catbox"), url, real_name, mtime))
            elif litterbox_re.match(url):
                real_name = os.path.basename(url)
                links.append((os.path.join(basepath, "litterbox"), url, real_name, mtime))
            elif mega_re.match(url):
                mega_links.append(url)

        return links, mega_links


    def _extract_links(self, basepath, posts):
        links = []
        mega_links = []
        seen = {}
        for post in posts:
            mtime = int(post.find("span", class_="posttime").get("title")[:-3]) - (5 * 60 * 60) # date is in America/New_York timezone
            link = self.get_file_link(basepath, post, mtime)
            if link and not link[1].lower() in seen:
                links.append(link)
                seen[link[1].lower()] = True

            l, ml = self.get_post_links(basepath, post, mtime)
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
        content = thread.select_one(".content > div")
        if not content:
           return []

        thread_num = content["id"].replace("p", "")
        basepath = os.path.join(OUTPATH, str(thread_num))

        posts = thread.find_all("td", class_="reply")
        return self._extract_links(basepath, posts)


def extra_sanitize_filepath(path):
    if len(path) >= 259:
        p, e = os.path.splitext(path)
        p = p[:250]
        path = f"{p}{e}"
    if args.sanitize_filepaths:  # strip out emoji and other non-ASCII characters
       path = path.encode("ascii", errors="replace").decode("utf-8").replace("?", "_")
    path = sanitize_filepath(path, platform="Windows")
    return path


def save_link(basepath, url, real_name, mtime):
    global g_run_loops
    if not g_run_loops:
        return

    if args.images_only:
        mimetype = mimetypes.guess_type(url)[0]
        if not mimetype or (not mimetype.startswith("image/") and not mimetype.startswith("video/")):
            return

    path = os.path.join(basepath, real_name)
    path = extra_sanitize_filepath(path)

    if os.path.isfile(path):
        print(f"--- SKIPPING (file exists): {path}")
        os.utime(path, (mtime, mtime))
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

    if os.path.isfile(path):
        os.utime(path, (mtime, mtime))


def worker(t):
    basepath, url, real_name, mtime = t
    save_link(basepath, url, real_name, mtime)


page = 1
if site == "https://fate.5ch.net":
   downloader = FiveChanDownloader(site, "liveuranus")
elif site == "https://8chan.moe":
   downloader = EightChanDownloader(site, args.board)
elif site == "https://warosu.org":
   downloader = WarosuDownloader(site, args.board)
else:
   downloader = FoolFuukaDownloader(site, args.board)


os.makedirs(OUTPATH, exist_ok=True)
print(f"Saving files in /{downloader.name()} to {OUTPATH}...")


threads = 0


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
        if not links:
           print("!!! SKIPPING (no links)")
           continue

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

        threads += 1

        if args.num_threads and threads >= args.num_threads:
           print(f"Finished archiving latest {args.num_threads}.")
           exit(0)

    page += 1
