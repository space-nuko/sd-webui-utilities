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
from collections import defaultdict
from io import BytesIO
import os
import re
import dotenv
import tqdm
from PIL import Image
from pprint import pp
import prompt_parser
from typing import Tuple, Any
from pprint import pp

import hydrus_api
import hydrus_api.utils


ERROR_EXIT_CODE = 1
REQUIRED_PERMISSIONS = {hydrus_api.Permission.IMPORT_FILES, hydrus_api.Permission.ADD_TAGS, hydrus_api.Permission.SEARCH_FILES}
addnet_re = re.compile(r'^addnet_.+_\d+')
addnet_model_re = re.compile(r'(.*)\(([a-f0-9]+)\)$')
re_AND = re.compile(r"\bAND\b")


parser = argparse.ArgumentParser()
parser.add_argument("--service", "-s", default="stable-diffusion-webui")
parser.add_argument("--api-url", "-a", default=hydrus_api.DEFAULT_API_URL)
parser.add_argument("--api_key", "-k", default=None)
parser.add_argument("--no-protect-decompression", "-d", action="store_false", dest="protect_decompression")
subparsers = parser.add_subparsers(dest="command", help='sub-command help')

parser_import = subparsers.add_parser('import', help='Import new files')
parser_import.add_argument("paths", nargs="+")
parser_import.add_argument("--tag", "-t", action="append", dest="tags", default=[])
parser_import.add_argument("--no-recursive", "-n", action="store_false", dest="recursive")
parser_import.add_argument("--no-protect-decompression", "-d", action="store_false", dest="protect_decompression")
#parser_import.add_argument("--no-read-metadata", "-m", action="store_false", dest="read_metadata")

parser_retag = subparsers.add_parser('retag', help='Retag existing files')
#parser_import.add_argument("--no-read-metadata", "-m", action="store_false", dest="read_metadata")


cache = set()


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
    global cache
    realpath = os.path.realpath(path)
    return realpath not in cache and os.path.isfile(path) or os.path.islink(path) and os.path.isfile(realpath) and realpath.endswith(".png")


re_whitespace = re.compile(r'  +')


def get_negatives(line):
    negatives = line.replace("Negative prompt: ","negative:",1).strip()
    negatives = re.sub(re_whitespace, " ", negatives)
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
    tokens = list(filter(lambda t: t, tokens))
    return tokens


annoying_infotext_fields = ["Wildcard prompt", "X Values", "Y Values", "Z Values"]
re_annoying_infotext_fields = re.compile(rf'({"|".join(annoying_infotext_fields)}): "[^"]*?"(?:, |$)')
re_extra_net = re.compile(r"<(\w+):([^>]+)>")


def strip_annoying_infotext_fields(settings):
    return re.sub(re_annoying_infotext_fields, "", settings)


def parse_prompt(prompt):
    res = defaultdict(list)

    def found(m):
        name = m.group(1)
        args = m.group(2)

        res[name].append(args.split(":"))

        return ""

    prompt = re.sub(re_extra_net, found, prompt)

    return prompt, res


def parse_prompts(prompts):
    res = []
    extra_data = None

    for prompt in prompts:
        updated_prompt, parsed_extra_data = parse_prompt(prompt)

        if extra_data is None:
            extra_data = parsed_extra_data

        res.append(updated_prompt)

    return res, extra_data


TEMPLATE_LABEL = "Template"
NEGATIVE_TEMPLATE_LABEL = "Negative Template"


def strip_template_info(settings) -> str:
    """dynamic-prompts"""
    split_by = None
    if (
        f"\n{TEMPLATE_LABEL}:" in settings
        and f"\n{NEGATIVE_TEMPLATE_LABEL}:" in settings
    ):
        split_by = f"{TEMPLATE_LABEL}"
    elif f"\n{NEGATIVE_TEMPLATE_LABEL}:" in settings:
        split_by = f"\n{NEGATIVE_TEMPLATE_LABEL}:"
    elif f"\n{TEMPLATE_LABEL}:" in settings:
        split_by = f"\n{TEMPLATE_LABEL}:"

    if split_by:
        settings = (
            settings.split(split_by)[0].strip()
        )
    return settings


def parse_tags_from_pnginfo(params):
    raw_prompt, extra_network_params = parse_prompt(params)

    lines = raw_prompt.split("\n")
    settings_lines = ""
    negative_prompt = ""
    negatives = None
    prompt = ""

    line_is = "positive"

    if len(lines) == 2:
        prompt = lines[0]
        negatives = get_negatives(lines[1])
    else:
        for line in lines:
            stripped_line = line.strip()
            if stripped_line == "":
                continue

            if stripped_line.startswith("Steps: "):
                line_is = "settings"
                settings_lines = stripped_line + "\n"
                continue
            if line_is == "negative":
                negatives += ", " + stripped_line
                continue
            elif line_is == "settings":
                settings_lines += stripped_line + "\n"
                continue

            if stripped_line.startswith("Negative prompt: "):
                line_is = "negative"
                negatives = get_negatives(stripped_line)
                continue

            prompt += stripped_line + "\n"

    settings_lines = strip_annoying_infotext_fields(settings_lines)
    settings_lines = strip_template_info(settings_lines)
    settings = get_settings(settings_lines.lower())

    addnet_models = []
    to_remove = []
    for tag in settings:
        tag = tag.lower()
        if addnet_re.search(tag):
            to_remove.append(tag)
            if tag.startswith("addnet_model"):
                t = re.sub(addnet_re, "", tag).strip(":")
                m = addnet_model_re.search(t)
                if not m:
                    print(f"COULD NOT FIND: {t}")
                    continue
                name, hash = m.groups()
                t1 = f"addnet_model:{t}"
                t2 = f"addnet_model_name:{name}"
                t3 = f"addnet_model_hash:{hash}"
                addnet_models.append(t1)
                addnet_models.append(t2)
                addnet_models.append(t3)
    settings += addnet_models
    tokens = set()

    steps = 20
    for t in settings:
        if t.startswith("steps:"):
            steps = int(t.replace("steps:", ""))
            break

    subprompts = re_AND.split(prompt)
    if len(subprompts) > 1:
        settings.append("uses_multicond:true")

    # Reconstruct tags from parsed attention
    for parsed in prompt_parser.get_learned_conditioning_prompt_schedules(subprompts, steps):
        if len(parsed) > 1:
            settings.append("uses_prompt_editing:true")
        for t in parsed:
            step, prompt = t
            ts = prompt_parser.parse_prompt_attention(prompt)
            full_line = ""
            for token, weight in ts:
                if token == "BREAK":
                    continue
                full_line += token + ","
            all_tokens = get_tokens(full_line.lower())
            tokens.update(all_tokens)

    extra_networks = []
    for network_type, arglists in extra_network_params.items():
        for arglist in arglists:
            extra_networks.append(f"extra_networks_{network_type}:{arglist[0]}")

    all_tokens = list(tokens) + settings + extra_networks
    tags = [t for t in all_tokens if t]
    if negatives:
        tags += [negatives]

    tags = set(tags)
    for r in to_remove:
        tags.remove(r)

    return tags


def import_path(client, path, tags=(), recursive=True, service_name="stable-diffusion-webui"):
    default_tags = tags
    tag_sets = collections.defaultdict(set)
    parameters = {}

    def do_import(tag_sets, parameters):
        global cache
        for tags, paths in tqdm.tqdm(tag_sets.items()):
            results = client.add_and_tag_files(paths, tags, (service_name,))
            for path, result in zip(paths, results):
                status = result.get("status", 4)

                if status == 1 or status == 2:
                    cache.add(path)
                    if "hash" in result:
                        image = Image.open(path)
                        image.load()
                        params = parameters[path]
                        client.set_notes({"filename": path, "parameters": params}, hash_=result["hash"])
        tag_sets.clear()
        parameters.clear()

        with open("hydrus_import_cache.txt", "w", encoding="utf-8") as f:
            for line in cache:
                f.write(line + "\n")

    i = 0

    for path in tqdm.tqdm(list(yield_paths(path, valid_file_path, recursive))):
        if os.path.splitext(path)[1].lower() != ".png":
            continue

        realpath = os.path.realpath(path)
        if realpath in cache:
            continue

        directory_path, filename = os.path.split(path)
        try:
            image = Image.open(path)
            image.load()

            extrema = image.convert("L").getextrema()
            if extrema == (0, 0):
                print(f"!!! SKIPPING (all black): {path}")
                continue

        except Exception as ex:
            print(f"!!! FAILED to open: {path} ({ex})")
            continue

        if "parameters" not in image.info:
            continue


        params = image.info["parameters"]
        tags = parse_tags_from_pnginfo(params)
        tags.update(default_tags)
        tag_sets[tuple(sorted(tags))].add(realpath)
        parameters[realpath] = image.info["parameters"]

        i += 1
        if i >= 100:
            do_import(tag_sets, parameters)
            i = 0

    do_import(tag_sets, parameters)


def cmd_import(arguments, client):
    global cache

    if os.path.isfile("hydrus_import_cache.txt"):
        with open("hydrus_import_cache.txt", "r", encoding="utf-8") as f:
            for line in f:
                cache.add(line.strip())

    for path in arguments.paths:
        print(f"Importing {path}...")
        import_path(
            client,
            path,
            arguments.tags,
            arguments.recursive,
            arguments.service,
        )

    with open("hydrus_import_cache.txt", "w", encoding="utf-8") as f:
        for line in cache:
            f.write(line + "\n")


def cmd_retag(arguments, client):
    keep_tags = ["board", "site", "gen_type"]
    all_file_ids = client.search_files(["system:everything"])
    service_key = None
    for file_ids in hydrus_api.utils.yield_chunks(all_file_ids, 100):
        metas = client.get_file_metadata(file_ids=file_ids, include_notes=True)
        if service_key is None:
            service_key = next(filter(lambda k: metas[0]["tags"][k]["name"] == arguments.service, metas[0]["tags"].keys()))
            assert service_key

        for meta in metas:
            file_id = meta["file_id"]
            notes = meta["notes"]
            # pp(meta)

            if "parameters" not in notes:
                resp = client.get_file(file_id=file_id)
                with BytesIO() as b:
                    for chunk in resp:
                        b.write(chunk)
                    img = Image.open(b)
                    if not "parameters" in img.info:
                        continue
                    notes["parameters"] = img.info["parameters"]

            existing_tags = set(meta["tags"][service_key]["storage_tags"][str(hydrus_api.TagStatus.CURRENT)])
            new_tags = set(parse_tags_from_pnginfo(notes["parameters"]))

            for tag in existing_tags:
                if ":" in tag and not tag.startswith("negative:"):
                    new_tags.add(tag)

            # pp(existing_tags)
            # pp(new_tags)
            print(f"- {meta['hash']}")
            print("exist - new:")
            pp(existing_tags - new_tags)
            print("new - exist:")
            pp(new_tags - existing_tags)
            print("================")

            params_delete = {
                service_key: {
                    str(hydrus_api.TagAction.DELETE): list(existing_tags),
                }
            }
            params_add = {
                service_key: {
                    str(hydrus_api.TagAction.ADD): list(new_tags),
                }
            }
            client.add_tags(file_ids=[file_id], service_keys_to_actions_to_tags=params_delete)
            client.add_tags(file_ids=[file_id], service_keys_to_actions_to_tags=params_add)
            client.set_notes(notes=notes, file_id=file_id)


def main(arguments):
    api_key = arguments.api_key or os.getenv("HYDRUS_ACCESS_KEY")
    client = hydrus_api.Client(api_key, arguments.api_url)
    if not hydrus_api.utils.verify_permissions(client, REQUIRED_PERMISSIONS):
        print("The API key does not grant all required permissions:", REQUIRED_PERMISSIONS)
        return ERROR_EXIT_CODE

    if not arguments.protect_decompression:
        Image.MAX_IMAGE_PIXELS = None

    if arguments.command == "import":
        cmd_import(arguments, client)
    elif arguments.command == "retag":
        cmd_retag(arguments, client)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    dotenv.load_dotenv()
    arguments = parser.parse_args()
    parser.exit(main(arguments))
