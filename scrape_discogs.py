#!/usr/bin/env python

import argparse
import os
import os.path
import re
import time
import discogs_client
from discogs_client.models import Master, Release
import dotenv
import requests
from pathvalidate import sanitize_filepath

parser = argparse.ArgumentParser()
parser.add_argument("--token", "-t", type=str, default=None)
parser.add_argument("--output-path", "-o", type=str, default=".")
subparsers = parser.add_subparsers(dest="command", help="sub-command help")

parser_list = subparsers.add_parser("list", help="Scrape Discogs list")
parser_list.add_argument("id")

parser_artist = subparsers.add_parser("artist", help="Scrape Discogs artist")
parser_artist.add_argument("id")

COVER_ROLES = ["Design", "Photography By", "Artwork"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
}

re_year = re.compile(r' *\([0-9]+\)$')
re_suffix = re.compile(r'([0-9]+-[a-z0-9_]+)\.[a-z]+$')

def sanitize_name(name):
    name = name.replace(",", "")
    return re_year.sub("", name)

def download_release_images(discogs, arguments, release, outpath, suffix):
    primary_image = next(filter(lambda x: x["type"] == "primary", release.images), None)
    if primary_image:
        tags = []

        for fmt in release.formats:
            if fmt["name"] == "Vinyl":
                tags.append("vinyl record cover")
                if "LP" in fmt["descriptions"]:
                    tags.append("LP")
                if "12\"" in fmt["descriptions"]:
                    tags.append("12-inch")
                if "7\"" in fmt["descriptions"]:
                    tags.append("7-inch")
            elif fmt["name"] == "CD":
                tags.append("CD cover")

        for artist in release.artists:
            artist_name = sanitize_name(artist.name)
            tags.append(artist_name)
        for genre in release.genres:
            genre = genre.replace(",", "")
            tags.append(genre)
        if release.styles:
            for style in release.styles:
                style = style.replace(",", "")
                tags.append(style)

        for label in release.labels:
            label = label.name.replace(",", "")
            tags.append(label)

        decade = 0
        if release.year > 0:
            decade = release.year - (release.year % 10)
            tags.append(f"{decade}s album cover")
            tags.append(str(release.year))

        for extraartist in release.credits:
            if any(extraartist.data["role"].startswith(r) for r in COVER_ROLES):
                tags.append(extraartist.name)

        uri = primary_image["uri"]
        file_basename = f"{release.year}-{release.artists_sort}-{release.title}-{suffix}".replace("/", "-")
        basename = sanitize_filepath(os.path.join(outpath, file_basename))
        tags = [t.replace("/", "-").replace("\\", "-") for t in tags]
        txt = ", ".join(tags)
        image_path = f"{basename}{os.path.splitext(uri)[1]}"

        tries = 0
        MAX_TRIES = 100

        while True:
            if os.path.exists(image_path):
                print(f"*** SKIPPING (file exists): {image_path}")
                break
            else:
                try:
                    resp = requests.get(uri, headers=HEADERS)
                    resp.raise_for_status()
                except Exception as ex:
                    print(f"!!! FAILED saving (attempt {tries+1}/{MAX_TRIES}): {uri}")
                    time.sleep(tries * 60)
                    tries += 1
                    if tries >= MAX_TRIES:
                        return
                    else:
                        continue
                print("Saving: " + image_path)
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                with open(image_path, "wb") as f:
                    for chunk in resp:
                        f.write(chunk)
                break

        txt_name = os.path.splitext(os.path.basename(image_path))[0] + ".txt"
        txt_path = os.path.join(os.path.dirname(image_path), txt_name)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt)


def scrape_artist(discogs, arguments):
    a = discogs.artist(arguments.id)
    print(f"Saving artist releases: {a.id} - {a.name}")

    outpath = os.path.join(arguments.output_path, "discogs")
    outdir = os.path.join(outpath, "artists", f"{a.id}")

    exist = set()
    if os.path.exists(outdir):
        files = os.listdir(outdir)
        for file in files:
            m = re_suffix.search(file)
            if m:
                exist.add(m.group(1))

    for item in a.releases:
        id = item.id
        ty = "master" if isinstance(item, Master) else "release"

        if f"{id}-{ty}" in exist:
            print(f"*** SKIPPING (exists): {id} ({ty})")
            continue

        if ty == "master":
            release = item.main_release
        else:
            release = item
        if not release.images:
            continue

        download_release_images(discogs, arguments, release, outdir, f"{id}-{ty}")

    return 0


def scrape_list(discogs, arguments):
    l = discogs.list(arguments.id)
    print(f"Saving list: {l.id} - {l.name}")

    outpath = os.path.join(arguments.output_path, "discogs")
    outdir = os.path.join(outpath, "lists", f"{l.id}")

    exist = set()
    if os.path.exists(outdir):
        files = os.listdir(outdir)
        for file in files:
            m = re_suffix.search(file)
            if m:
                exist.add(m.group(1))

    for item in l.items:
        id = item.id
        ty = item.type

        if f"{id}-{ty}" in exist:
            print(f"*** SKIPPING (exists): {id} ({ty})")
            continue

        if ty == "master":
            release = discogs.master(id).main_release
        else:
            release = discogs.release(id)
        if not release.images:
            continue

        download_release_images(discogs, arguments, release, outdir, f"{id}-{ty}")

    return 0


def main(arguments):
    user_token = arguments.token or os.getenv("DISCOGS_USER_TOKEN")
    discogs = discogs_client.Client("sd-discogs", user_token=user_token)

    if arguments.command == "list":
        return scrape_list(discogs, arguments)
    elif arguments.command == "artist":
        return scrape_artist(discogs, arguments)
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    dotenv.load_dotenv()
    arguments = parser.parse_args()
    parser.exit(main(arguments))
