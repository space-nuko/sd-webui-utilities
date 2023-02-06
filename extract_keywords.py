#!/usr/bin/env python

import os
import os.path
from io import StringIO
import torch
import sys
import glob
import shutil
from textblob import TextBlob
from sacremoses import MosesPunctNormalizer
from collections import Counter
import string


regular_punct = list('!"#$%&\'()*+,./:;<=>?@[\\]^`{|}~')
def remove_punctuation(text,punct_list=regular_punct):
    for punc in punct_list:
        if punc in text:
            text = text.replace(punc, '')
    return text.strip()


files = sys.argv[1:]
if not files:
    print("No files provided.")
    exit(1)

txt = StringIO()
for file in files:
    if os.path.isfile(file):
        with open(file, "r", encoding="utf-8") as f:
            txt.write(f.read())
    else:
        raise Exception(f"File not found: {file}")

mpn = MosesPunctNormalizer()

txt.seek(0)
raw = remove_punctuation(mpn.normalize(txt.read()))
blob = TextBlob(raw)
phrases = blob.noun_phrases

counter = Counter([p.strip() for p in phrases])
print(counter)

prompt = ""
i = 0
for noun, frequency in counter.items():
    prompt += noun + ", "
    i += 1
    if i > 30:
        break

prompt = prompt.strip().strip(",")
print(prompt)
