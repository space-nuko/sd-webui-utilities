#!/usr/bin/env python

import requests
import dotenv
import sys
import os
import os.path
import signal
import json
import time
from datetime import datetime
from multiprocessing.pool import ThreadPool as Pool

dotenv.load_dotenv()

dir = sys.argv[1]
if not os.path.isdir(dir):
    print("Invalid output directory.")
    exit(1)

type = sys.argv[2]

the_no = None
if len(sys.argv) > 3:
    the_no = int(sys.argv[3])


dbr_login = os.getenv("DANBOORU_LOGIN")
dbr_token = os.getenv("DANBOORU_TOKEN")
dbr_auth = (dbr_login, dbr_token)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246",}


g_run_loops = True
def signal_handler(signum, frame):
   global g_run_loops
   g_run_loops = False


def worker(post):
    global outdir, g_run_loops
    if not g_run_loops:
        return
    folder = str(post["id"] % 1000).rjust(4, "0")
    outpath = os.path.join(outdir, folder, f"{post['id']}.json")
    #print(f"Saving: {outpath}")
    if os.path.isfile(outpath):
        print(f"EXISTS: {outpath}")
        return False
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    try:
        with open(outpath, 'w', encoding="utf-8") as f:
            json.dump(post, f)
    except KeyboardInterrupt:
        print(f"*** DELETING partial file: {outpath}")
        os.unlink(outpath)
    return True


today = datetime.now()
datestr = today.strftime('%Y_%m_%d_%H-%M-%S')
limit = 200

def dump(meta_type):
    resp = requests.get(f"https://danbooru.donmai.us/{meta_type}.json", params={"tags": "status:any", "limit": limit}, headers=HEADERS, auth=dbr_auth)
    posts = resp.json()
    assert len(posts) == limit
    no = the_no or max([p["id"] for p in posts])

    while no > limit * -2:
        retries = 0
        results = []
        print(f"===== Page {no} =====")
        while True:
            resp = requests.get(f"https://danbooru.donmai.us/{meta_type}.json", params={"page": f"b{no}", "tags": "status:any", "limit": limit}, headers=HEADERS, auth=dbr_auth)
            if resp.status_code == 200:
                break
            retries += 1
            secs = 2.0 ** retries
            print(f"[WARN] hit rate limit, sleeping {time} seconds")
            print(resp)
            print(resp.status_code)
            time.sleep(secs)

        posts = resp.json()

        original_sigint = signal.getsignal(signal.SIGINT)

        p = Pool(processes=8)
        signal.signal(signal.SIGINT, signal_handler)

        for res in p.imap_unordered(worker, posts):
            if not g_run_loops:
                p.close()
                p.join()
                print("Interrupted, exiting")
                exit(1)
            results.append(res)

        p.close()
        p.join()
        signal.signal(signal.SIGINT, original_sigint)

        if len(results) == limit and all(not r for r in results):
            print("!!!!! All items on this page were found already. !!!!!")
            break

        if posts:
            min_id = min([p["id"] for p in posts])

            with open(os.path.join(outdir, f"pages-{datestr}.txt"), "w", encoding="utf-8") as f:
                json.dump({"page": no, "min_id": min_id}, f)

        no -= 200

    print("Finished.")

ALL_TYPES = ["posts", "artists", "artist_commentaries", "artist_urls", "notes", "pools", "wiki_pages", "comments", "forum_posts", "forum_topics", "dtext_links", "post_approvals", "post_replacements", "post_appeals", "post_flags", "tags", "tag_aliases", "tag_implications", "users", "artist_versions", "artist_commentary_versions", "note_versions", "pool_versions", "post_versions", "wiki_page_versions"]

if type == "all":
    # for type in ALL_TYPES:
    #     print(f"Verify: {type}")
    #     resp = requests.get(f"https://danbooru.donmai.us/{type}.json", params={"tags": "status:any", "limit": limit}, headers=HEADERS, auth=dbr_auth)
    #     items = resp.json()
    #     assert len(items) == limit

    for type in ALL_TYPES:
        outdir = os.path.join(dir, type)
        os.makedirs(type, exist_ok=True)
        print(f"++++++++++++++++++++ Dumping: {type} ++++++++++++++++++++")
        dump(type)
else:
    outdir = os.path.join(dir, type)
    os.makedirs(type, exist_ok=True)
    dump(type)
