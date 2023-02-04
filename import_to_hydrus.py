#!/usr/bin/env python3

# Copyright (C) 2021 cryzed
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import argparse
import collections
import os
import re
import dotenv
import tqdm
from PIL import Image
from pprint import pp
import prompt_parser

import hydrus_api
import hydrus_api.utils

ERROR_EXIT_CODE = 1
REQUIRED_PERMISSIONS = {hydrus_api.Permission.IMPORT_FILES, hydrus_api.Permission.ADD_TAGS}
addnet_re = re.compile(r'^addnet_.+_\d+')
addnet_model_re = re.compile(r'(.*)\(([a-f0-9]+)\)$')


argument_parser = argparse.ArgumentParser()
argument_parser.add_argument("paths", nargs="+")
argument_parser.add_argument("--tag", "-t", action="append", dest="tags", default=[])
argument_parser.add_argument("--service", "-s", action="append", dest="services", default=["stable-diffusion-webui"])
argument_parser.add_argument("--no-recursive", "-n", action="store_false", dest="recursive")
argument_parser.add_argument("--no-protect-decompression", "-d", action="store_false", dest="protect_decompression")
#argument_parser.add_argument("--no-read-metadata", "-m", action="store_false", dest="read_metadata")
argument_parser.add_argument("--api-url", "-a", default=hydrus_api.DEFAULT_API_URL)
argument_parser.add_argument("--api_key", "-k", default=None)


def yield_paths(path, predicate=lambda path: path, recursive=True):
    for path, directories, file_names in os.walk(path, followlinks=True):
        if predicate(path):
            yield path

        for file_name in file_names:
            file_path = os.path.join(path, file_name)
            if predicate(file_path):
                yield file_path

        if not recursive:
            break


def valid_file_path(path):
    return os.path.isfile(path) or os.path.islink(path) and os.path.isfile(os.path.realpath(path))


def get_negatives(line):
    negatives = line.replace("negative prompt: ","negative:",1)
    return negatives


def get_settings(line):
    setup = line.replace(": ",":")          # Removes the space between the namespace and tag
    settings = setup.split(",")
    settings = [setting.strip().replace(" ","_") for setting in settings]
    return settings


def get_tokens(line):
    prompt = line.replace(":",";")          # Replace : to avoid unwanted namespaces
    tokens = prompt.split(",")
    tokens = [token.strip().replace(" ","_") for token in tokens]
    tokens = list(filter(None, tokens))
    return tokens


def get_tags_from_pnginfo(image):
    params = image.info["parameters"].lower()
    lines = params.split("\n")
    settings = get_settings(lines[len(lines)-1])
    lines.remove(lines[len(lines)-1])
    negatives = None
    prompt = ""

    line_is_negative = False

    if len(lines) == 2:
        prompt = lines[0]
        negatives = get_negatives(lines[1])
    else:
        for line in lines:
            stripped_line = line.strip()
            if stripped_line == "":
                continue

            if line_is_negative:
                negatives += ", " + stripped_line
                continue

            if stripped_line.startswith("negative prompt: "):
                line_is_negative = True
                negatives = get_negatives(stripped_line)
                continue

            prompt += stripped_line + "\n"

    addnet_models = []
    to_remove = []
    for tag in settings:
        if addnet_re.search(tag):
            to_remove.append(tag)
            if tag.startswith("addnet_model"):
                t = re.sub(addnet_re, "", tag).strip(":")
                name, hash = addnet_model_re.search(t).groups()
                t1 = f"addnet_model:{t}"
                t2 = f"addnet_model_name:{name}"
                t3 = f"addnet_model_hash:{hash}"
                addnet_models.append(t1)
                addnet_models.append(t2)
                addnet_models.append(t3)
    settings += addnet_models
    tokens = set()

    steps = 20
    if "steps" in settings:
        steps = int(settings["steps"])

    # Reconstruct tags from parsed attention
    for parsed in prompt_parser.get_learned_conditioning_prompt_schedules([prompt], steps):
        if len(parsed) > 1:
            settings.append("uses_prompt_editing:true")
        for t in parsed:
            step, prompt = t
            ts = prompt_parser.parse_prompt_attention(prompt)
            full_line = ""
            for token, weight in ts:
                full_line += token
            all_tokens = get_tokens(full_line)
            tokens.update(all_tokens)

    tags = list(tokens) + settings
    if negatives:
        tags += [negatives]

    tags = set(tags)
    for r in to_remove:
        tags.remove(r)

    print(tags)

    return tags


def import_path(client, path, tags=(), recursive=True, service_names=("stable-diffusion-webui",)):
    default_tags = tags
    tag_sets = collections.defaultdict(set)

    for path in tqdm.tqdm(list(yield_paths(path, valid_file_path, recursive))):
        if os.path.splitext(path)[1].lower() != ".png":
            continue

        directory_path, filename = os.path.split(path)
        image = Image.open(path)
        image.load()
        if "parameters" not in image.info:
            continue

        tags = get_tags_from_pnginfo(image)
        tags.update(default_tags)
        tag_sets[tuple(sorted(tags))].add(os.path.realpath(path))

    for tags, paths in tqdm.tqdm(tag_sets.items()):
        results = client.add_and_tag_files(paths, tags, service_names)
        for path, result in zip(paths, results):
            print(path + ":" + str(result))
            if "hash" in result:
                client.set_notes({"filename": path}, hash_=result["hash"])


def main(arguments):
    api_key = arguments.api_key or os.getenv("HYDRUS_ACCESS_KEY")
    client = hydrus_api.Client(api_key, arguments.api_url)
    if not hydrus_api.utils.verify_permissions(client, REQUIRED_PERMISSIONS):
        print("The API key does not grant all required permissions:", REQUIRED_PERMISSIONS)
        return ERROR_EXIT_CODE

    if not arguments.protect_decompression:
        Image.MAX_IMAGE_PIXELS = None

    for path in arguments.paths:
        print(f"Importing {path}...")
        import_path(
            client,
            path,
            arguments.tags,
            arguments.recursive,
            arguments.services,
        )


if __name__ == "__main__":
    dotenv.load_dotenv()
    arguments = argument_parser.parse_args()
    argument_parser.exit(main(arguments))
