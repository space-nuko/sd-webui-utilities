#!/usr/bin/env python

# A Swiss-Army-Knife sort of script for dealing with Stable Diffusion caption
# files in .txt format.

import argparse
import collections
import os
import re
import dotenv
import tqdm
from PIL import Image
from pprint import pp
import prompt_parser
import glob
import sys
import safetensors
import json
import mmap
import pprint
import os.path
from sacremoses import MosesPunctNormalizer
import unicodedata
import re
import shutil
import requests
import pandas


parser = argparse.ArgumentParser()
parser.add_argument('--recursive', '-r', action="store_true", help='Edit caption files recursively')
subparsers = parser.add_subparsers(dest="command", help='sub-command help')

parser_fixup_tags = subparsers.add_parser('fixup', help='Fixup caption files, converting from gallery-dl format and normalizing UTF-8')
parser_fixup_tags.add_argument('path', type=str, help='Path to caption files')

parser_add_tags = subparsers.add_parser('add', help='Add tags to captions (delimited by commas)')
parser_add_tags.add_argument('path', type=str, help='Path to caption files')
parser_add_tags.add_argument('tags', type=str, nargs='+', help='Tags to add')

parser_add_tags = subparsers.add_parser('remove', help='Remove tags from captions (delimited by commas)')
parser_add_tags.add_argument('path', type=str, help='Path to caption files')
parser_add_tags.add_argument('tags', type=str, nargs='+', help='Tags to remove')

parser_replace_tag = subparsers.add_parser('replace', help='Replace tags in captions (delimited by commas)')
parser_replace_tag.add_argument('path', type=str, help='Path to caption files')
parser_replace_tag.add_argument('to_find', type=str, help='Tag to find')
parser_replace_tag.add_argument('to_replace', type=str, help='Tag to replace with')

parser_move_tags_to_front = subparsers.add_parser('move_to_front', help='Move tags in captions (delimited by commas) to front of list')
parser_move_tags_to_front.add_argument('path', type=str, help='Path to caption files')
parser_move_tags_to_front.add_argument('tags', type=str, nargs='+', help='Tags to move')

parser_move_categories_to_front = subparsers.add_parser('move_categories_to_front', help='Move tag categories in captions (delimited by commas) to front of list')
parser_move_categories_to_front.add_argument('path', type=str, help='Path to caption files')
parser_move_categories_to_front.add_argument('categories', type=str, nargs='+', help='Categories to move')

parser_validate = subparsers.add_parser('validate', help='Validate a dataset')
parser_validate.add_argument('path', type=str, help='Path to root of dataset folder')

parser_stats = subparsers.add_parser('stats', help='Show dataset image counts/repeats')
parser_stats.add_argument('path', type=str, help='Path to caption files')

parser_organize_images = subparsers.add_parser('organize_images', help='Move images with specified tags (delimited by commas) into a subfolder')
parser_organize_images.add_argument('path', type=str, help='Path to caption files')
parser_organize_images.add_argument('tags', type=str, nargs='+', help='Tags to move')
parser_organize_images.add_argument('--folder-name', '-n', type=str, help='Name of subfolder')
parser_organize_images.add_argument('--split-rest', '-s', action="store_true", help='Move all non-matching images into another folder')

args = parser.parse_args()


gallery_dl_txt_re = re.compile(r'^(.*)\.[a-z]{3}\.txt')
IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif"]
repeats_folder_re = re.compile(r'^(\d+)_(.*)$')


def convert_tag(t):
    return t.replace("_", " ").replace("(", "\(").replace(")", "\)")


def get_caption_file_image(txt):
    basename = os.path.splitext(txt)[0]
    for ext in IMAGE_EXTS:
        path = basename + ext
        if os.path.isfile(path):
            return path
    return None


def get_caption_file_images(txt):
    basename = os.path.splitext(txt)[0]
    images = []
    for ext in IMAGE_EXTS:
        path = basename + ext
        if os.path.isfile(path):
            images.append(path)
    return images


def fixup(args):
    # rename gallery-dl-format .txt files (<...>.png.txt, etc.)
    renamed = 0
    total = 0
    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=args.recursive))):
        m = gallery_dl_txt_re.match(txt)
        if m:
            basename = m.groups(1)[0]
            print("RENAME: " + basename + ".txt")
            shutil.move(txt, basename + ".txt")
            renamed += 1
        total += 1

    print(f"Renamed {renamed}/{total} caption files.")

    mpn = MosesPunctNormalizer()

    # join newlines, deduplicate tags, fix unicode chars, remove spaces and escape parens
    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=args.recursive))):
        if get_caption_file_image(txt):
            with open(txt, "r", encoding="utf-8") as f:
                s = f.read()

            s = unicodedata.normalize("NFKC", mpn.normalize(s))
            s = ", ".join(s.split("\n"))
            these_tags = [convert_tag(t.strip().lower()) for t in s.split(",")]

            fixed_tags = []
            for i in these_tags:
                if i not in fixed_tags:
                    fixed_tags.append(i)

            with open(txt, "w", encoding="utf-8") as f:
                f.write(", ".join(fixed_tags))


def add(args):
    tags = [convert_tag(t) for t in args.tags]
    modified = 0
    total = 0
    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=args.recursive))):
        found = False
        if get_caption_file_image(txt):
            with open(txt, "r") as f:
                these_tags = [t.strip().lower() for t in f.read().split(",")]

            for to_add in tags:
                if to_add not in these_tags:
                    found = True
                    these_tags.append(to_add)

            with open(txt, "w") as f:
                f.write(", ".join(these_tags))

            if found:
                modified += 1
            total += 1

    print(f"Updated {modified}/{total} caption files.")


def remove(args):
    tags = [convert_tag(t) for t in args.tags]
    modified = 0
    total = 0
    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=args.recursive))):
        found = False
        if get_caption_file_image(txt):
            with open(txt, "r") as f:
                these_tags = [t.strip().lower() for t in f.read().split(",")]

            for to_find in tags:
                if to_find in these_tags:
                    found = True
                    index = these_tags.index(to_find)
                    these_tags.pop(index)

            with open(txt, "w") as f:
                f.write(", ".join(these_tags))

            if found:
                modified += 1
            total += 1

    print(f"Updated {modified}/{total} caption files.")


def replace(args):
    to_find = convert_tag(args.to_find)
    to_replace = convert_tag(args.to_replace)
    modified = 0
    total = 0
    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=args.recursive))):
        if get_caption_file_image(txt):
            with open(txt, "r") as f:
                these_tags = [t.strip().lower() for t in f.read().split(",")]

            if to_find in these_tags:
                assert to_replace not in these_tags
                index = these_tags.index(to_find)
                these_tags.pop(index)
                these_tags.insert(index, to_replace)

                with open(txt, "w") as f:
                    f.write(", ".join(these_tags))

                modified += 1

        total += 1

    print(f"Updated {modified}/{total} caption files.")


def move_to_front(args):
    tags = list(reversed([convert_tag(t) for t in args.tags]))
    modified = 0
    total = 0
    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=args.recursive))):
        found = False
        if get_caption_file_image(txt):
            with open(txt, "r") as f:
                these_tags = [t.strip().lower() for t in f.read().split(",")]

            for t in tags:
                if t in these_tags:
                    found = True
                    these_tags.insert(0, these_tags.pop(these_tags.index(t)))

            with open(txt, "w") as f:
                f.write(", ".join(these_tags))

            if found:
                modified += 1
            total += 1

    print(f"Updated {modified}/{total} caption files.")


CATEGORIES = {
    "general": 0,
    "artist": 1,
    "copyright": 3,
    "character": 4,
    "meta": 5,
}


def to_danbooru_tag(t):
    return t.strip().lower().replace(" ", "_").replace("\(", "(").replace("\)", ")")


def move_categories_to_front(args):
    if not os.path.isfile("danbooru.csv"):
        print("Downloading danbooru.csv tags list...")
        url = "https://github.com/arenatemp/sd-tagging-helper/raw/master/danbooru.csv"
        response = requests.get(url, stream=True)
        with open("danbooru.csv", "wb") as handle:
            for data in tqdm.tqdm(response.iter_content()):
                handle.write(data)

    print("Loading danbooru.csv tags list...")
    danbooru_tags = pandas.read_csv("danbooru.csv", engine="pyarrow").set_axis(["tag", "tag_category"], axis=1).set_index("tag").to_dict("index")
    order = [CATEGORIES[cat] for cat in reversed(args.categories)]
    print("Done.")

    modified = 0
    total = 0
    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=args.recursive))):
        found = False
        if get_caption_file_image(txt):
            with open(txt, "r") as f:
                these_tags = [to_danbooru_tag(t) for t in f.read().split(",")]

            for tag_category in order:
                for t in these_tags:
                    this_category = danbooru_tags.get(t)
                    if this_category is not None:
                        this_category = this_category["tag_category"]
                        if tag_category == this_category:
                            found = True
                            these_tags.insert(0, these_tags.pop(these_tags.index(t)))

            with open(txt, "w") as f:
                f.write(", ".join(these_tags))

            if found:
                modified += 1
            total += 1

    print(f"Updated {modified}/{total} caption files.")


def organize_images(args):
    tags = [convert_tag(t) for t in args.tags]
    folder_name = args.folder_name or " ".join(args.tags)
    outpath = os.path.join(args.path, folder_name)
    if os.path.exists(outpath):
        print(f"Error: Folder already exists - {outpath}")
        return 1

    if args.split_rest:
        split_path = os.path.join(args.path, "(rest)")
        if os.path.exists(split_path):
            print(f"Error: Folder already exists - {split_path}")
            return 1

    modified = 0
    total = 0

    def do_move(txt, img, outpath):
        os.makedirs(outpath, exist_ok=True)
        basename = os.path.splitext(os.path.basename(txt))[0]
        img_ext = os.path.splitext(img)[1]
        out_txt = os.path.join(outpath, basename + ".txt")
        out_img = os.path.join(outpath, basename + img_ext)
        # print(f"{img} -> {out_img}")
        shutil.move(txt, out_txt)
        shutil.move(img, out_img)

    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=args.recursive))):
        img = get_caption_file_image(txt)
        if img:
            with open(txt, "r", encoding="utf-8") as f:
                these_tags = {t.strip().lower(): True for t in f.read().split(",")}

            if all(t in these_tags for t in tags):
                do_move(txt, img, outpath)
                modified += 1
            elif args.split_rest:
                do_move(txt, img, split_path)
                modified += 1
        total += 1

    print(f"Moved {modified}/{total} images and caption files to {outpath}.")


def validate(args):
    problems = []
    total = 0

    print("Validating folder names...")
    for dirname in tqdm.tqdm(os.listdir(args.path)):
        path = os.path.join(args.path, dirname)
        if os.path.isdir(path):
            m = repeats_folder_re.match(dirname)
            if not m:
                problems.add((path, "Folder is not in \"5_concept\" format"))
                continue
            img_count = len(list(glob.iglob(os.path.join(path, "*.txt"))))
            if img_count == 0:
                problems.add((path, "Folder contains no captions"))

    print("Validating image files...")
    for ext in IMAGE_EXTS:
        for img in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, f"**/*{ext}"), recursive=True))):
            txt = os.path.splitext(img)[0] + ".txt"
            if not os.path.isfile(txt):
                problems.add((img, "Image file is missing caption"))

            try:
                pil = Image.open(img)
                pil.load()
            except Exception as ex:
                problems.append((img, f"Failed to open image file: {ex}"))
                continue

    print("Validating captions...")
    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=True))):
        total += 1

        images = get_caption_file_images(txt)
        if not images:
            problems.append((txt, "Caption file is missing corresponding image"))
            continue
        elif len(images) > 1:
            problems.append((txt, "Caption file has more than one corresponding image"))
            continue

        with open(txt, "r") as f:
            tag_string = f.read().strip()

        if not tag_string:
            problems.append((txt, "Caption file is empty"))
            continue

        if "\n" in tag_string:
            problems.append((txt, "Caption file contains newlines"))
        if "_" in tag_string:
            problems.append((txt, "Caption file contains underscores"))

        tags = {t.strip().lower(): True for t in tag_string.split(",")}
        if not tags:
            problems.append((txt, "Caption file has no tags"))
        elif any(not t for t in tags.keys()):
            problems.append((txt, "Caption file contains at least one blank tag"))

    if problems:
        for filename, problem in problems:
            print(f"{filename} - {problem}")
        return 1

    print(f"No problems found for {total} image/caption pairs.")
    return 0


def stats(args):
    problems = []
    total_images = 0
    total_seen = 0

    rows = [["folder name", "repeats", "image count", "total seen"]]

    for dirname in os.listdir(args.path):
        path = os.path.join(args.path, dirname)
        if os.path.isdir(path):
            m = repeats_folder_re.match(dirname)
            repeats, folder_name = int(m.group(1)), m.group(2)
            img_count = len(list(glob.iglob(os.path.join(path, "*.txt"))))
            rows.append([dirname, repeats, img_count, repeats * img_count])
            total_images += img_count
            total_seen += img_count * repeats

    rows.append(["(Total)", "", total_images, total_seen])

    col_width = max(len(str(word)) for row in rows for word in row) + 2
    for i, row in enumerate(rows):
        print("".join(str(word).ljust(col_width) for word in row))
        if i == 0:
            print(("=" * (col_width - 1) + " ") * len(rows[0]))
        elif i == len(rows) - 2:
            print(("-" * (col_width - 1) + " ") * len(rows[0]))


def main(args):
    if args.command == "fixup":
        return fixup(args)
    elif args.command == "add":
        return add(args)
    elif args.command == "remove":
        return remove(args)
    elif args.command == "replace":
        return replace(args)
    elif args.command == "move_to_front":
        return move_to_front(args)
    elif args.command == "move_categories_to_front":
        return move_categories_to_front(args)
    elif args.command == "organize_images":
        return organize_images(args)
    elif args.command == "validate":
        return validate(args)
    elif args.command == "stats":
        return stats(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    args = parser.parse_args()
    parser.exit(main(args))
