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
parser_add_tags.add_argument('--if', '-i', type=str, dest='iftags', help='Only add if these tags are present (comma-separated, danbooru format)')
parser_add_tags.add_argument('path', type=str, help='Path to caption files')
parser_add_tags.add_argument('tags', type=str, nargs='+', help='Tags to add')

parser_add_tags = subparsers.add_parser('remove', help='Remove tags from captions (delimited by commas)')
parser_add_tags.add_argument('path', type=str, help='Path to caption files')
parser_add_tags.add_argument('tags', type=str, nargs='+', help='Tags to remove')
parser.add_argument('--no-convert-tags', '-n', action="store_false", dest="convert_tags", help='Do not convert tags to NAI format')

parser_replace_tag = subparsers.add_parser('replace', help='Replace tags in captions (delimited by commas)')
parser_replace_tag.add_argument('path', type=str, help='Path to caption files')
parser_replace_tag.add_argument('to_find', type=str, help='Tag to find')
parser_replace_tag.add_argument('to_replace', type=str, help='Tag to replace with')

parser_move_tags_to_front = subparsers.add_parser('move_to_front', help='Move tags in captions (delimited by commas) to front of list')
parser_move_tags_to_front.add_argument('path', type=str, help='Path to caption files')
parser_move_tags_to_front.add_argument('tags', type=str, nargs='+', help='Tags to move')

parser_move_categories_to_front = subparsers.add_parser('move_categories_to_front', help='Move danbooru tag categories in captions (delimited by commas) to front of list')
parser_move_categories_to_front.add_argument('path', type=str, help='Path to caption files')
parser_move_categories_to_front.add_argument('categories', type=str, nargs='+', help='Categories to move')

parser_merge = subparsers.add_parser('merge', help='Merge two directories of caption files based on filenames')
parser_merge.add_argument('target_path', type=str, help='Path with caption files to edit')
parser_merge.add_argument('to_merge', type=str, help='Path with caption files to merge')

parser_strip_tag_suffix = subparsers.add_parser('strip_suffix', help='Strips a suffix from all tags ("neptune_(neptune_series)" -> "neptune")')
parser_strip_tag_suffix.add_argument('path', type=str, help='Path to caption files')
parser_strip_tag_suffix.add_argument('suffix', type=str, help='Suffix to find')

parser_validate = subparsers.add_parser('validate', help='Validate a dataset')
parser_validate.add_argument('path', type=str, help='Path to root of dataset folder')

parser_stats = subparsers.add_parser('stats', help='Show dataset image counts/repeats')
parser_stats.add_argument('path', type=str, help='Path to caption files')

parser_organize = subparsers.add_parser('organize', help='Move images with specified tags (delimited by commas) into a subfolder')
parser_organize.add_argument('path', type=str, help='Path to caption files')
parser_organize.add_argument('tags', type=str, nargs='+', help='Tags to move, all tags must be present to match')
parser_organize.add_argument('--folder-name', '-n', type=str, help='Name of subfolder')
parser_organize.add_argument('--split-rest', '-s', action="store_true", help='Move all non-matching images into another folder')

parser_organize_lowres = subparsers.add_parser('organize_lowres', help='Move images with low resolution into a subfolder')
parser_organize_lowres.add_argument('path', type=str, help='Path to caption files')
parser_organize_lowres.add_argument('--folder-name', '-n', type=str, help='Name of subfolder')
parser_organize_lowres.add_argument('--split-rest', '-s', action="store_true", help='Move all non-matching images into another folder')

parser_backup_tags = subparsers.add_parser('backup_tags', help='Copy tags to new folder maintaining directory structure')
parser_backup_tags.add_argument('--outpath', '-o', type=str, help='Output path')
parser_backup_tags.add_argument('path', type=str, help='Path to caption files')

parser_dedup = subparsers.add_parser('dedup', help='Deduplicate images and captions')
parser_dedup.add_argument('--outpath', '-o', type=str, help='Output path')
parser_dedup.add_argument('--threshold', '-t', type=int, default=10, help="Hamming distance threshold for perceptual hasher")
parser_dedup.add_argument('--no-cache', action="store_false", dest="cache", help="Normally a cache of the duplicated files found is saved, pass this flag to ignore it and recalculate")
parser_dedup.add_argument('--debug', '-d', action="store_true", help="Show plots of discovered duplicate images")
parser_dedup.add_argument('path', type=str, help='Path to caption files')

args = parser.parse_args()


gallery_dl_txt_re = re.compile(r'^(.*)\.[a-z]{3}\.txt')
IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif"]
repeats_folder_re = re.compile(r'^(\d+)_(.*)$')


def convert_tag(t):
    return t.replace("_", " ").replace("(", "\(").replace(")", "\)").replace("  ", " ")


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


def get_image_file_caption(img):
    basename = os.path.splitext(img)[0]
    path = basename + ".txt"
    if os.path.isfile(path):
        return path
    return None


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
    tags = args.tags
    if args.convert_tags:
        tags = [convert_tag(t) for t in args.tags]
    modified = 0
    total = 0
    if args.iftags:
        iftags = args.iftags.split(",")
        if args.convert_tags:
            iftags = [convert_tag(t) for t in iftags]
    else:
        iftags = []

    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=args.recursive))):
        found = False
        if get_caption_file_image(txt):
            with open(txt, "r", encoding="utf-8") as f:
                these_tags = [t.strip().lower() for t in f.read().split(",")]

            for to_add in tags:
                if to_add not in these_tags and all(t in these_tags for t in iftags):
                    found = True
                    these_tags.append(to_add)

            with open(txt, "w", encoding="utf-8") as f:
                f.write(", ".join(these_tags))

            if found:
                modified += 1
            total += 1

    print(f"Updated {modified}/{total} caption files.")


def remove(args):
    tags = args.tags
    if args.convert_tags:
        tags = [convert_tag(t) for t in args.tags]
    modified = 0
    total = 0
    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=args.recursive))):
        found = False
        if get_caption_file_image(txt):
            with open(txt, "r", encoding="utf-8") as f:
                these_tags = [t.strip().lower() for t in f.read().split(",")]

            for to_find in tags:
                if to_find in these_tags:
                    found = True
                    index = these_tags.index(to_find)
                    these_tags.pop(index)

            with open(txt, "w", encoding="utf-8") as f:
                f.write(", ".join(these_tags))

            if found:
                modified += 1
            total += 1

    print(f"Updated {modified}/{total} caption files.")


def replace(args):
    if args.convert_tags:
        to_find = convert_tag(args.to_find)
        to_replace = convert_tag(args.to_replace)
    else:
        to_find = args.to_find
        to_replace = args.to_replace
    modified = 0
    total = 0
    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=args.recursive))):
        if get_caption_file_image(txt):
            with open(txt, "r", encoding="utf-8") as f:
                these_tags = [t.strip().lower() for t in f.read().split(",")]

            if to_find in these_tags:
                if to_replace in these_tags:
                    index_existing = these_tags.index(to_replace)
                    these_tags.pop(index_existing)

                index = these_tags.index(to_find)
                these_tags.pop(index)
                these_tags.insert(index, to_replace)

                with open(txt, "w", encoding="utf-8") as f:
                    f.write(", ".join(these_tags))

                modified += 1

        total += 1

    print(f"Updated {modified}/{total} caption files.")


def strip_suffix(args):
    suffix = convert_tag(args.suffix)
    modified = 0
    total = 0
    stripped_tags = 0
    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=args.recursive))):
        found = False
        if get_caption_file_image(txt):
            with open(txt, "r", encoding="utf-8") as f:
                these_tags = [t.strip().lower() for t in f.read().split(",")]

            new_tags = []
            for t in these_tags:
                if t.endswith(suffix):
                    found = True
                    t = t.removesuffix(suffix).strip()
                    stripped_tags += 1
                new_tags.append(t)

            with open(txt, "w", encoding="utf-8") as f:
                f.write(", ".join(new_tags))

            if found:
                modified += 1

        total += 1

    print(f"Updated {modified}/{total} caption files, {stripped_tags} tags stripped.")


def move_to_front(args):
    tags = list(reversed([convert_tag(t) for t in args.tags]))
    modified = 0
    total = 0
    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=args.recursive))):
        found = False
        if get_caption_file_image(txt):
            with open(txt, "r", encoding="utf-8") as f:
                these_tags = [t.strip().lower() for t in f.read().split(",")]

            for t in tags:
                if t in these_tags:
                    found = True
                    these_tags.insert(0, these_tags.pop(these_tags.index(t)))

            with open(txt, "w", encoding="utf-8") as f:
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
            with open(txt, "r", encoding="utf-8") as f:
                these_tags = list(sorted(to_danbooru_tag(t) for t in f.read().split(",")))

            for tag_category in order:
                for t in these_tags:
                    this_category = danbooru_tags.get(t)
                    if this_category is not None:
                        this_category = this_category["tag_category"]
                        if tag_category == this_category:
                            found = True
                            these_tags.insert(0, these_tags.pop(these_tags.index(t)))

            these_tags = [convert_tag(t) for t in these_tags]

            with open(txt, "w", encoding="utf-8") as f:
                f.write(", ".join(these_tags))

            if found:
                modified += 1
            total += 1

    print(f"Updated {modified}/{total} caption files.")


def merge(args):
    modified = 0
    total = 0
    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.target_path, "*.txt"), recursive=False))):
        found = False

        other_txt = os.path.join(args.to_merge, os.path.basename(txt))
        if get_caption_file_image(txt) and os.path.isfile(other_txt) and get_caption_file_image(other_txt):
            with open(txt, "r", encoding="utf-8") as f:
                these_tags = [to_danbooru_tag(t) for t in f.read().split(",")]

            with open(other_txt, "r", encoding="utf-8") as f:
                their_tags = [to_danbooru_tag(t) for t in f.read().split(",")]

            these_tags = [convert_tag(t) for t in these_tags]
            their_tags = [convert_tag(t) for t in their_tags]

            for tag in their_tags:
                if tag not in these_tags:
                    found = True
                    these_tags.append(tag)

            with open(txt, "w", encoding="utf-8") as f:
                f.write(", ".join(these_tags))

            if found:
                modified += 1
            total += 1

    print(f"Updated {modified}/{total} caption files.")


def do_move(txt, img, outpath):
    os.makedirs(outpath, exist_ok=True)
    basename = os.path.splitext(os.path.basename(txt))[0]
    img_ext = os.path.splitext(img)[1]
    out_txt = os.path.join(outpath, basename + ".txt")
    out_img = os.path.join(outpath, basename + img_ext)
    # print(f"{img} -> {out_img}")
    shutil.move(txt, out_txt)
    shutil.move(img, out_img)


def organize(args):
    tags = [convert_tag(t) for t in args.tags]
    folder_name = args.folder_name or " ".join(args.tags)
    def test(txt, img):
        with open(txt, "r", encoding="utf-8") as f:
            these_tags = {t.strip().lower(): True for t in f.read().split(",")}
        return all(t in these_tags for t in tags)

    return do_organize(args, test, folder_name)


def organize_lowres(args):
    folder_name = "lowres"
    def test(txt, img):
        pil = Image.open(img)
        return pil.size[0] < 400 or pil.size[1] < 400

    return do_organize(args, test, folder_name)


def do_organize(args, test, folder_name):
    outpath = os.path.join(args.path, folder_name)
    # if os.path.exists(outpath):
    #     print(f"Error: Folder already exists - {outpath}")
    #     return 1

    if args.split_rest:
        split_path = os.path.join(args.path, "(rest)")
        # if os.path.exists(split_path):
        #     print(f"Error: Folder already exists - {split_path}")
        #     return 1

    modified = 0
    total = 0

    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=args.recursive))):
        img = get_caption_file_image(txt)
        if img:
            if test(txt, img):
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

        with open(txt, "r", encoding="utf-8") as f:
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


def backup_tags(args):
    outpath = args.outpath or os.path.join(args.path, "backup")
    if os.path.exists(outpath):
        print(f"Path already exists: {outpath}")
        return 1

    for txt in tqdm.tqdm(list(glob.iglob(os.path.join(args.path, "**/*.txt"), recursive=True))):
        if get_caption_file_image(txt):
            rel = os.path.relpath(txt, args.path)
            new_txt = os.path.join(outpath, rel)
            os.makedirs(os.path.dirname(new_txt), exist_ok=True)
            shutil.copy2(txt, new_txt)


def dedup(args):
    outpath = args.outpath or os.path.join(args.path, "duplicates")
    if os.path.exists(outpath):
        print(f"Path already exists: {outpath}")
        return 1

    cache_file = os.path.join(args.path, "duplicates.json")

    if args.cache and not args.debug and os.path.isfile(cache_file):
        print("Load duplicates from cache")
        with open(cache_file, "r", encoding="utf-8") as f:
            duplicates = json.load(f)
    else:
        from imagededup.methods import PHash
        phasher = PHash(verbose=False)
        encodings = phasher.encode_images(image_dir=args.path, recursive=args.recursive)
        if not encodings:
            print(f"No images found in path: {args.path}")
            return 1
        duplicates = phasher.find_duplicates(encoding_map=encodings, scores=args.debug, max_distance_threshold=args.threshold)
        print("Save duplicates to cache")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(duplicates, f)

    if args.debug:
        from imagededup.utils import plot_duplicates
        for imagepath, dupepaths in tqdm.tqdm(duplicates.items()):
            if not dupepaths:
                continue
            print(imagepath)
            print(dupepaths)
            plot_duplicates(image_dir=args.path,
                            duplicate_map=duplicates,
                            filename=imagepath)
        return 0

    def find_largest(images):
        largest = None
        max_size = 0
        for image in images:
            filesize = os.path.getsize(image)
            if filesize > max_size:
                largest = image
                max_size = filesize

        assert largest is not None
        return largest, [i for i in images if i != largest]

    def find_best_caption(images):
        best_txt = None
        most_tags = 0
        for image in images:
            txt = get_image_file_caption(image)
            if txt:
                with open(txt, "r", encoding="utf-8") as f:
                    split = f.read().split(",")
                    if len(split) > most_tags:
                        most_tags = len(split)
                        best_txt = txt

        return best_txt

    total = 0
    moved = 0
    seen = set()

    for imagepath, dupepaths in tqdm.tqdm(duplicates.items()):
        total += 1

        if not dupepaths:
            # print("SKIPPING (no duplicates)")
            continue

        if imagepath in seen:
            # print(f"SKIPPING (already seen): {imagepath}")
            continue

        allimages = list(filter(lambda x: x not in seen, [imagepath] + dupepaths))

        if len(allimages) < 2:
            # print("SKIPPING (no images)")
            continue

        for img in allimages:
            seen.add(img)

        allimages = [os.path.join(args.path, i) for i in allimages]

        main_image, rest = find_largest(allimages)
        caption = find_best_caption(allimages)

        if caption:
            newcaption = os.path.splitext(main_image)[0] + ".txt"
            if caption != newcaption:
                print(f"copy caption: {caption} -> {newcaption}")
                shutil.copy(caption, newcaption)

        for img in rest:
            newpath = os.path.join(outpath, os.path.dirname(os.path.relpath(img, args.path)))
            os.makedirs(newpath, exist_ok=True)
            print(f"move image: {img} -> {newpath}")
            shutil.move(img, newpath)
            txt = get_image_file_caption(img)
            if txt:
                print(f"move txt: {txt} -> {newpath}")
                shutil.move(txt, newpath)
            total += 1
            moved += 1

    print(f"Moved {moved}/{total} duplicate image files and their captions.")


def main(args):
    if args.command == "fixup":
        return fixup(args)
    elif args.command == "add":
        return add(args)
    elif args.command == "remove":
        return remove(args)
    elif args.command == "replace":
        return replace(args)
    elif args.command == "strip_suffix":
        return strip_suffix(args)
    elif args.command == "move_to_front":
        return move_to_front(args)
    elif args.command == "move_categories_to_front":
        return move_categories_to_front(args)
    elif args.command == "merge":
        return merge(args)
    elif args.command == "organize":
        return organize(args)
    elif args.command == "organize_lowres":
        return organize_lowres(args)
    elif args.command == "validate":
        return validate(args)
    elif args.command == "stats":
        return stats(args)
    elif args.command == "backup_tags":
        return backup_tags(args)
    elif args.command == "dedup":
        return dedup(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    args = parser.parse_args()
    parser.exit(main(args))
