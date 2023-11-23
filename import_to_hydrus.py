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
from dataclasses import dataclass
from io import BytesIO
import os
import re
import dotenv
import tqdm
import signal
import json
from PIL import Image
from pprint import pp
import prompt_parser
from typing import Tuple, Any
from pprint import pp
import gzip

import hydrus_api
import hydrus_api.utils


def null_handler(signum, frame):
    pass

MAX_IMPORT_SIZE = 100

ERROR_EXIT_CODE = 1
REQUIRED_PERMISSIONS = {
    hydrus_api.Permission.IMPORT_FILES,
    hydrus_api.Permission.ADD_TAGS,
    hydrus_api.Permission.SEARCH_FILES,
}
addnet_re = re.compile(r"^addnet_.+_\d+")
addnet_model_re = re.compile(r"(.*)\(([a-f0-9]+)\)$")
re_AND = re.compile(r"\bAND\b")


parser = argparse.ArgumentParser()
parser.add_argument("--service", "-s", default="stable-diffusion-webui")
parser.add_argument("--api-url", "-a", default=hydrus_api.DEFAULT_API_URL)
parser.add_argument("--api_key", "-k", default=None)
parser.add_argument(
    "--no-protect-decompression",
    "-d",
    action="store_false",
    dest="protect_decompression",
)
subparsers = parser.add_subparsers(dest="command", help="sub-command help")

parser_import = subparsers.add_parser("import", help="Import new files")
parser_import.add_argument("paths", nargs="+")
parser_import.add_argument("--tag", "-t", action="append", dest="tags", default=[])
parser_import.add_argument(
    "--no-recursive", "-n", action="store_false", dest="recursive"
)
parser_import.add_argument(
    "--no-protect-decompression",
    "-d",
    action="store_false",
    dest="protect_decompression",
)
# parser_import.add_argument("--no-read-metadata", "-m", action="store_false", dest="read_metadata")

parser_retag = subparsers.add_parser("retag", help="Retag existing files")
parser_retag.add_argument("query", nargs="+")
# parser_import.add_argument("--no-read-metadata", "-m", action="store_false", dest="read_metadata")


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
    return (
        realpath not in cache
        and os.path.isfile(path)
        or os.path.islink(path)
        and os.path.isfile(realpath)
        and realpath.endswith(".png")
    )


re_whitespace = re.compile(r"  +")


def get_negatives(line):
    negatives = line.replace("Negative prompt: ", "negative:", 1).strip()
    negatives = re.sub(re_whitespace, " ", negatives)
    return negatives


def get_settings(line):
    setup = line.replace(": ", ":")  # Removes the space between the namespace and tag
    settings = setup.split(",")
    settings = [setting.strip().replace(" ", "_") for setting in settings]
    return settings


def get_tokens(line):
    prompt = line.replace(":", ";")  # Replace : to avoid unwanted namespaces
    tokens = prompt.split(",")
    tokens = [token.strip().replace(" ", "_") for token in tokens]
    tokens = list(filter(lambda t: t, tokens))
    return tokens


annoying_infotext_fields = ["Wildcard prompt", "X Values", "Y Values", "Z Values"]
re_annoying_infotext_fields = re.compile(
    rf'({"|".join(annoying_infotext_fields)}): "[^"]*?"(?:, |$)'
)
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
        settings = settings.split(split_by)[0].strip()
    return settings


def parse_comfyui_prompt(prompt):
    graph = json.loads(prompt)

    prompts = {
        id: n
        for id, n in graph.items()
        if n["class_type"] == "CLIPTextEncode" and "text" in n["inputs"]
    }
    ksamplers = [
        (id, n)
        for id, n in graph.items()
        if "KSampler" in n["class_type"] and "positive" in n["inputs"]
    ]

    positive = None
    negative = None

    for id, ks in ksamplers:
        pos = ks["inputs"]["positive"]
        neg = ks["inputs"]["negative"]

        if isinstance(pos, list):
            id_pos = pos[0]
            if id_pos in prompts:
                positive = prompts[id_pos]["inputs"]["text"]
        elif isinstance(pos, str):
            positive = pos

        if isinstance(neg, list):
            id_neg = neg[0]
            if id_neg in prompts:
                negative = prompts[id_neg]["inputs"]["text"]
        elif isinstance(neg, str):
            negative = neg

    if positive is None:
        return None, None, None

    tokens = set()
    settings = []  # TODO

    ts = prompt_parser.parse_prompt_attention(positive)
    full_line = ""
    for token, weight in ts:
        full_line += token + ","
    all_tokens = get_tokens(full_line.lower())
    tokens.update(all_tokens)

    all_tokens = list(tokens) + settings
    tags = [t for t in all_tokens if t]
    if negative:
        tags += ["negative:" + negative]

    tags = set(tags)
    # for r in to_remove:
    #     tags.remove(r)

    return tags, positive.strip(), negative.strip()


def convert_nai_to_a1111(prompt):
    prompt = prompt.replace("(", "\\(")
    prompt = prompt.replace(")", "\\)")
    prompt = prompt.replace("{", "(")
    prompt = prompt.replace("}", ")")
    return prompt


def format_setting(v):
    if isinstance(v, str):
        return v
    return json.dumps(v)


def get_naiv3_settings(data):
    settings = data["Comment"]
    del settings["prompt"]
    del settings["uc"]

    # remove dimension tags since they're redundant
    if "width" in settings:
        del settings["width"]
    if "height" in settings:
        del settings["height"]

    result = [f"{k}:{format_setting(v)}" for k, v in settings.items()]
    result.append(f'nai_software:{data["Software"]}')
    result.append(f'nai_source:{data["Source"]}')
    # result.append(f'naiv3_gen_time:{data["Generation time"]}')
    return result


def parse_nai_prompt(data):
    data["Comment"] = json.loads(data["Comment"])

    orig_positive = data["Description"]
    positive = convert_nai_to_a1111(orig_positive)
    negative = data["Comment"]["uc"]

    tokens = set()
    settings = get_naiv3_settings(data)

    ts = prompt_parser.parse_prompt_attention(positive)
    full_line = ""
    for token, weight in ts:
        full_line += token + ","
    all_tokens = get_tokens(full_line.lower())
    tokens.update(all_tokens)

    all_tokens = list(tokens) + settings
    tags = [t for t in all_tokens if t]
    if negative:
        tags += ["negative:" + negative]

    tags = set(tags)

    return tags, orig_positive.strip(), negative.strip()


# NAIv3
#
def is_naiv3_metadata(result):
    return "Software" in result \
        and result["Software"] == "NovelAI" \
        and "Source" in result \
        and result["Source"].startswith("Stable Diffusion XL")

def read_info_from_image_stealth(image):
    # geninfo, items = original_read_info_from_image(image)
    # possible_sigs = {'stealth_pnginfo', 'stealth_pngcomp', 'stealth_rgbinfo', 'stealth_rgbcomp'}

    # respecting original pnginfo
    # if geninfo is not None:
    #     return geninfo, items

    geninfo = None

    # trying to read stealth pnginfo
    width, height = image.size
    pixels = image.load()

    has_alpha = True if image.mode == 'RGBA' else False
    mode = None
    compressed = False
    binary_data = ''
    buffer_a = ''
    buffer_rgb = ''
    index_a = 0
    index_rgb = 0
    sig_confirmed = False
    confirming_signature = True
    reading_param_len = False
    reading_param = False
    read_end = False
    for x in range(width):
        for y in range(height):
            if has_alpha:
                r, g, b, a = pixels[x, y]
                buffer_a += str(a & 1)
                index_a += 1
            else:
                r, g, b = pixels[x, y]
            buffer_rgb += str(r & 1)
            buffer_rgb += str(g & 1)
            buffer_rgb += str(b & 1)
            index_rgb += 3
            if confirming_signature:
                if index_a == len('stealth_pnginfo') * 8:
                    decoded_sig = bytearray(int(buffer_a[i:i + 8], 2) for i in
                                            range(0, len(buffer_a), 8)).decode('utf-8', errors='ignore')
                    if decoded_sig in {'stealth_pnginfo', 'stealth_pngcomp'}:
                        confirming_signature = False
                        sig_confirmed = True
                        reading_param_len = True
                        mode = 'alpha'
                        if decoded_sig == 'stealth_pngcomp':
                            compressed = True
                        buffer_a = ''
                        index_a = 0
                    else:
                        read_end = True
                        break
                elif index_rgb == len('stealth_pnginfo') * 8:
                    decoded_sig = bytearray(int(buffer_rgb[i:i + 8], 2) for i in
                                            range(0, len(buffer_rgb), 8)).decode('utf-8', errors='ignore')
                    if decoded_sig in {'stealth_rgbinfo', 'stealth_rgbcomp'}:
                        confirming_signature = False
                        sig_confirmed = True
                        reading_param_len = True
                        mode = 'rgb'
                        if decoded_sig == 'stealth_rgbcomp':
                            compressed = True
                        buffer_rgb = ''
                        index_rgb = 0
            elif reading_param_len:
                if mode == 'alpha':
                    if index_a == 32:
                        param_len = int(buffer_a, 2)
                        reading_param_len = False
                        reading_param = True
                        buffer_a = ''
                        index_a = 0
                else:
                    if index_rgb == 33:
                        pop = buffer_rgb[-1]
                        buffer_rgb = buffer_rgb[:-1]
                        param_len = int(buffer_rgb, 2)
                        reading_param_len = False
                        reading_param = True
                        buffer_rgb = pop
                        index_rgb = 1
            elif reading_param:
                if mode == 'alpha':
                    if index_a == param_len:
                        binary_data = buffer_a
                        read_end = True
                        break
                else:
                    if index_rgb >= param_len:
                        diff = param_len - index_rgb
                        if diff < 0:
                            buffer_rgb = buffer_rgb[:diff]
                        binary_data = buffer_rgb
                        read_end = True
                        break
            else:
                # impossible
                read_end = True
                break
        if read_end:
            break
    if sig_confirmed and binary_data != '':
        # Convert binary string to UTF-8 encoded text
        byte_data = bytearray(int(binary_data[i:i + 8], 2) for i in range(0, len(binary_data), 8))
        try:
            if compressed:
                decoded_data = gzip.decompress(bytes(byte_data)).decode('utf-8')
            else:
                decoded_data = byte_data.decode('utf-8', errors='ignore')
            geninfo = decoded_data
        except:
            pass

    return geninfo


def parse_a1111_prompt(params):
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

    orig_prompt = ""
    for line in params.split("\n"):
        stripped_line = line.strip()
        if stripped_line.startswith("Negative prompt: ") or stripped_line.startswith("Steps: "):
            break
        else:
            orig_prompt += line + "\n"

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
    for parsed in prompt_parser.get_learned_conditioning_prompt_schedules(
        subprompts, steps
    ):
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

    return tags, orig_prompt.strip(), negatives.removeprefix("negative:").strip()



@dataclass
class PromptParseResult:
    realpath: str
    parameters: any
    tags: set[str]
    positive: str
    negative: str


def do_import(client, service_key, tag_sets):
    global cache

    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, null_handler)

    for tags, parse_results in tqdm.tqdm(tag_sets.items()):
        paths = [pr.realpath for pr in parse_results]
        results = hydrus_api.utils.add_and_tag_files(
            client, paths, tags, tag_service_keys=[service_key]
        )
        for parse_result, result in zip(parse_results, results):
            path = parse_result.realpath
            status = result.get("status", 4)

            if status == 1 or status == 2:
                cache.add(path)
                if "hash" in result:
                    image = Image.open(path)
                    image.load()
                    client.set_notes(
                        {"filename": parse_result.realpath,
                            "parameters": parse_result.parameters,
                            "positive": parse_result.positive,
                            "negative": parse_result.negative
                            },
                        hash_=result["hash"],
                    )
    tag_sets.clear()

    with open("hydrus_import_cache.txt", "w", encoding="utf-8") as f:
        for line in cache:
            f.write(line + "\n")

    signal.signal(signal.SIGINT, original_sigint)


def parse_image(path, default_tags):
    global cache

    try:
        image = Image.open(path)
        image.load()

        extrema = image.convert("L").getextrema()
        if extrema == (0, 0):
            print(f"!!! SKIPPING (all black): {path}")
            cache.add(path)
            return None

    except Exception as ex:
        print(f"!!! FAILED to open: {path} ({ex})")
        return None

    params = ""
    tags = []
    positive = ""
    negative = ""

    if "parameters" in image.info:  # A1111
        prompt_type = "a1111"
        params = image.info["parameters"]
        tags, positive, negative = parse_a1111_prompt(params)
    elif "prompt" in image.info:  # ComfyUI
        prompt_type = "comfyui"
        params = image.info["prompt"]
        tags, positive, negative = parse_comfyui_prompt(params)
        if tags is None:
            return None
    elif is_naiv3_metadata(image.info): # NAI
        result = {}
        for key in ["Title", "Description", "Software", "Source", "Generation time", "Comment"]:
            result[key] = image.info[key]
        prompt_type = "nai_v3"
        params = json.dumps(result)
        tags, positive, negative = parse_nai_prompt(result)
    else:
        try:
            result_str = read_info_from_image_stealth(image)
            if result_str is not None:
                try:
                    # NAIv3
                    result = json.loads(result_str)
                    if is_naiv3_metadata(result):
                        prompt_type = "nai_v3"
                        params = result_str
                        tags, positive, negative = parse_nai_prompt(result)
                    else:
                        return None
                except Exception:
                    return None
            else:
                return None
        except Exception as ex:
            print(ex)
            return None

    tags.update(default_tags)
    tags.add(f"prompt_type:{prompt_type}")

    return PromptParseResult(path, params, tags, positive, negative)


def import_path(client, target_path, service_key, tags=(), recursive=True):
    default_tags = tags
    tag_sets = collections.defaultdict(list)

    i = 0

    for path in tqdm.tqdm(list(yield_paths(target_path, valid_file_path, recursive))):
        print(path)
        if os.path.splitext(path)[1].lower() != ".png":
            continue

        realpath = os.path.realpath(path)
        if realpath in cache:
            # print(f"!!! SKIPPING (in cache): {path}")
            continue

        result = parse_image(realpath, default_tags)
        if result is None:
            continue

        tag_sets[tuple(sorted(result.tags))].append(result)

        i += 1
        if i >= MAX_IMPORT_SIZE:
            do_import(client, service_key, tag_sets)
            i = 0

    do_import(client, service_key, tag_sets)


def cmd_import(arguments, client):
    global cache

    if os.path.isfile("hydrus_import_cache.txt"):
        with open("hydrus_import_cache.txt", "r", encoding="utf-8") as f:
            for line in f:
                cache.add(line.strip())

    service_key = (
        client.get_service(service_name=arguments.service)
        .get("service", {})
        .get("service_key", None)
    )
    if not service_key:
        print(f"Unknown hydrus service: {arguments.service}")
        exit(1)

    for path in arguments.paths:
        print(path)
        if os.path.isdir(path):
            print(f"Importing {path}...")
            import_path(
                client,
                path,
                service_key,
                arguments.tags,
                arguments.recursive,
            )
        else:
            print(f"Skipping (not a directory): {path}")

    with open("hydrus_import_cache.txt", "w", encoding="utf-8") as f:
        for line in cache:
            f.write(line + "\n")


def cmd_retag(arguments, client):
    keep_tags = ["board", "site", "gen_type"]
    all_file_ids = client.search_files(arguments.query)
    service_key = None
    for file_ids in hydrus_api.utils.yield_chunks(all_file_ids, 100):
        metas = client.get_file_metadata(file_ids=file_ids, include_notes=True)
        if service_key is None:
            service_key = next(
                filter(
                    lambda k: metas[0]["tags"][k]["name"] == arguments.service,
                    metas[0]["tags"].keys(),
                )
            )
            assert service_key

        for meta in metas:
            print(f"- {meta['hash']}")
            needs_update = False
            file_id = meta["file_id"]
            notes = meta["notes"]
            # pp(meta)

            if "parameters" not in notes:
                needs_update = True
                resp = client.get_file(file_id=file_id)
                with BytesIO() as b:
                    for chunk in resp:
                        b.write(chunk)
                    img = Image.open(b)
                    if not "parameters" in img.info:
                        continue
                    notes["parameters"] = img.info["parameters"]

            existing_tags = set(
                meta["tags"][service_key]["storage_tags"].get(
                    str(hydrus_api.TagStatus.CURRENT), {}
                )
            )
            new_tags = set(parse_a1111_prompt(notes["parameters"]))

            for tag in existing_tags:
                if ":" in tag and not tag.startswith("negative:"):
                    new_tags.add(tag)

            # pp(existing_tags)
            # pp(new_tags)

            needs_update = (
                needs_update or (existing_tags - new_tags) or (new_tags - existing_tags)
            )

            if needs_update:
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

                original_sigint = signal.getsignal(signal.SIGINT)
                signal.signal(signal.SIGINT, null_handler)

                client.add_tags(
                    file_ids=[file_id], service_keys_to_actions_to_tags=params_delete
                )
                client.add_tags(
                    file_ids=[file_id], service_keys_to_actions_to_tags=params_add
                )
                client.set_notes(notes=notes, file_id=file_id)

                signal.signal(signal.SIGINT, original_sigint)


def main(arguments):
    api_key = arguments.api_key or os.getenv("HYDRUS_ACCESS_KEY")
    client = hydrus_api.Client(api_key, arguments.api_url)
    if not hydrus_api.utils.verify_permissions(client, REQUIRED_PERMISSIONS):
        print(
            "The API key does not grant all required permissions:", REQUIRED_PERMISSIONS
        )
        return ERROR_EXIT_CODE

    # if not arguments.protect_decompression:
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
