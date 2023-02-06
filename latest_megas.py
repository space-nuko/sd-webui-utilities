#!/usr/bin/env python

# Grabs the latest N mega links from the output of hdg_archive.py, for adding to
# JDownloader2 or similar

import os
import os.path
import re
import argparse


parser = argparse.ArgumentParser(description='Optional app description')
parser.add_argument('path', type=str, help='Path to input directory')
parser.add_argument('--num-threads', '-n', type=int, default=5, help='Find only the N most recent threads')

args = parser.parse_args()
txts = []


for site in os.listdir(args.path):
    bp = os.path.join(args.path, site)
    for board in os.listdir(bp):
        bp2 = os.path.join(bp, board)
        i = 0
        for thread in os.listdir(bp2):
            mega = os.path.join(bp2, thread, "mega.txt")
            if os.path.isfile(mega):
                txts.append(mega)
                i += 1
                if i > args.num_threads:
                    break


folder_re = re.compile(r'^(http.*/folder/.*)/folder/.*') # strip mega subfolders
links = set()


for txt in txts:
    with open(txt, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            m = folder_re.search(line)
            if m:
                line = m.group(1)
                print(line)
            links.add(line.strip())


for link in links:
    print(link)
