#!/usr/bin/env python

# Standalone version of the WD 1.4 autotagger extension because I don't like
# having to start the entire webui just to use it

import argparse
import os
import json

from collections import OrderedDict
from pathlib import Path
from glob import glob
from PIL import Image, UnidentifiedImageError
from dataclasses import dataclass
from typing import Optional
import pandas as pd
import requests
import tqdm
import multiprocessing as mp
from multiprocessing.pool import ThreadPool as Pool

from tagger import format, utils, dbimutils
from tagger.utils import split_str
from tagger.interrogator import Interrogator


DEFAULT_THRESHOLD = 0.35
DEFAULT_FILENAME_FORMAT = "[name].[output_extension]"

# kaomoji from WD 1.4 tagger csv. thanks, Meow-San#5400!
DEFAULT_REPLACE_UNDERSCORE_EXCLUDES = "0_0, (o)_(o), +_+, +_-, ._., <o>_<o>, <|>_<|>, =_=, >_<, 3_3, 6_9, >_o, @_@, ^_^, o_o, u_u, x_x, |_|, ||_||"


parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest="command", help='sub-command help')

parser_single = subparsers.add_parser('single', help='Interrogate single image')
parser_single.add_argument('path', type=str, help='Path to image')
parser_single.add_argument('--interrogator', '-i', default="wd14-swinv2-v2-git", type=str)
parser_single.add_argument('--threshold', '-t', default=DEFAULT_THRESHOLD, type=float)
parser_single.add_argument('--additional-tags', '-a', default="", type=str)
parser_single.add_argument('--exclude-tags', '-e', default="", type=str)
parser_single.add_argument('--sort-alpha', '-s', default="", action="store_true")
parser_single.add_argument('--add-confident-as-weight', '-w', action="store_true")
parser_single.add_argument('--no-replace-underscore', action="store_false", dest="replace_underscore")
parser_single.add_argument('--replace_underscore_excludes', default=DEFAULT_REPLACE_UNDERSCORE_EXCLUDES, type=str)
parser_single.add_argument('--no-escape-tag', action="store_false", dest="escape_tag")

parser_batch = subparsers.add_parser('batch', help='Batch autotag images')
parser_batch.add_argument('input_path', type=str, help='Path to images')
parser_batch.add_argument('--process-count', '-p', default=8, type=int, help="Number of threads for batch tagging")
parser_batch.add_argument('--interrogator', '-i', default="wd14-swinv2-v2-git", type=str)
parser_batch.add_argument('--recursive', '-r', action="store_true")
parser_batch.add_argument('--output-path', '-o', type=str, default="")
parser_batch.add_argument('--filename-format', '-f', type=str, default=DEFAULT_FILENAME_FORMAT)
parser_batch.add_argument('--on-conflict', '-c', choices=["ignore", "copy", "append", "prepend"], type=str.lower, default="ignore")
parser_batch.add_argument('--no-remove-duplicated-tag', action="store_false", dest="remove_duplicated_tag")
parser_batch.add_argument('--save-json', '-j', action="store_true")
parser_batch.add_argument('--threshold', '-t', default=DEFAULT_THRESHOLD, type=float)
parser_batch.add_argument('--additional-tags', '-a', default="", type=str)
parser_batch.add_argument('--exclude-tags', '-e', default="", type=str)
parser_batch.add_argument('--sort-alpha', '-s', default="", action="store_true")
parser_batch.add_argument('--add-confident-as-weight', '-w', action="store_true")
parser_batch.add_argument('--no-replace-underscore', action="store_false", dest="replace_underscore")
parser_batch.add_argument('--replace_underscore_excludes', default=DEFAULT_REPLACE_UNDERSCORE_EXCLUDES, type=str)
parser_batch.add_argument('--no-escape-tag', action="store_false", dest="escape_tag")


@dataclass
class InterrogateBatchOptions:
    input_glob: str
    input_recursive: bool
    output_dir: str
    output_filename_format: str
    output_action_on_conflict: str
    remove_duplicated_tag: bool
    output_save_json: bool


def unload_interrogators():
    unloaded_models = 0

    for i in utils.interrogators.values():
        if i.unload():
            unloaded_models = unloaded_models + 1

    return [f'Successfully unload {unloaded_models} model(s)']


def interrogate_single(
    image: Image,

    interrogator: str,
    threshold: float=DEFAULT_THRESHOLD,
    additional_tags: str="",
    exclude_tags: str="",
    sort_by_alphabetical_order: bool=False,
    add_confident_as_weight: bool=False,
    replace_underscore: bool=True,
    replace_underscore_excludes: str=DEFAULT_REPLACE_UNDERSCORE_EXCLUDES,
    escape_tag: bool=True,

    unload_model_after_running: bool=True
):
    if interrogator not in utils.interrogators:
        raise Exception(f"'{interrogator}' is not a valid interrogator")

    interrogator: Interrogator = utils.interrogators[interrogator]

    postprocess_opts = (
        threshold,
        split_str(additional_tags),
        split_str(exclude_tags),
        sort_by_alphabetical_order,
        add_confident_as_weight,
        replace_underscore,
        split_str(replace_underscore_excludes),
        escape_tag
    )

    ratings, tags = interrogator.interrogate(image)
    processed_tags = Interrogator.postprocess_tags(
        tags,
        *postprocess_opts
    )

    if unload_model_after_running:
        interrogator.unload()

    return (', '.join(processed_tags), ratings, tags)


def interrogate_batch(
    batch_options: InterrogateBatchOptions,
    interrogator: str,
    threshold: float=DEFAULT_THRESHOLD,
    additional_tags: str="",
    exclude_tags: str="",
    sort_by_alphabetical_order: bool=False,
    add_confident_as_weight: bool=False,
    replace_underscore: bool=True,
    replace_underscore_excludes: str=DEFAULT_REPLACE_UNDERSCORE_EXCLUDES,
    escape_tag: bool=True,
    unload_model_after_running: bool=True):

    if interrogator not in utils.interrogators:
        raise Exception(f"'{interrogator}' is not a valid interrogator")

    interrogator: Interrogator = utils.interrogators[interrogator]

    postprocess_opts = (
        threshold,
        split_str(additional_tags),
        split_str(exclude_tags),
        sort_by_alphabetical_order,
        add_confident_as_weight,
        replace_underscore,
        split_str(replace_underscore_excludes),
        escape_tag
    )

    # batch process
    batch_options.input_glob = batch_options.input_glob.strip()
    batch_options.output_dir = batch_options.output_dir.strip()
    batch_options.output_filename_format = batch_options.output_filename_format.strip()

    assert batch_options.input_glob != ''

    # if there is no glob pattern, insert it automatically
    if not batch_options.input_glob.endswith('*'):
        if not batch_options.input_glob.endswith(os.sep):
            batch_options.input_glob += os.sep
        if batch_options.input_recursive:
            batch_options.input_glob += '**'
        else:
            batch_options.input_glob += '*'

    # get root directory of input glob pattern
    base_dir = batch_options.input_glob.replace('?', '*')
    base_dir = base_dir.split(os.sep + '*').pop(0)

    # check the input directory path
    if not os.path.isdir(base_dir):
        return ['', None, None, 'input path is not a directory']

    # this line is moved here because some reason
    # PIL.Image.registered_extensions() returns only PNG if you call too early
    supported_extensions = [
        e
        for e, f in Image.registered_extensions().items()
        if f in Image.OPEN
    ]

    paths = [
        Path(p)
        for p in glob(batch_options.input_glob, recursive=batch_options.input_recursive)
        if '.' + p.split('.').pop().lower() in supported_extensions
    ]

    print(f'found {len(paths)} image(s)')

    def worker(path):
        try:
            image = Image.open(path)
        except UnidentifiedImageError:
            # just in case, user has mysterious file...
            print(f'${path} is not supported image type')
            return

        # guess the output path
        base_dir_last = Path(base_dir).parts[-1]
        base_dir_last_idx = path.parts.index(base_dir_last)
        output_dir = Path(
            batch_options.output_dir) if batch_options.output_dir else Path(base_dir)
        output_dir = output_dir.joinpath(
            *path.parts[base_dir_last_idx + 1:]).parent

        output_dir.mkdir(0o777, True, True)

        # format output filename
        format_info = format.Info(path, 'txt')

        try:
            formatted_output_filename = format.pattern.sub(
                lambda m: format.format(m, format_info),
                batch_options.output_filename_format
            )
        except (TypeError, ValueError) as error:
            return ['', None, None, str(error)]

        output_path = output_dir.joinpath(
            formatted_output_filename
        )

        output = []

        if output_path.is_file():
            output.append(output_path.read_text(errors='ignore').strip())

            if batch_options.output_action_on_conflict == 'ignore':
                print(f'skipping {path}')
                return

        ratings, tags = interrogator.interrogate(image)
        processed_tags = Interrogator.postprocess_tags(
            tags,
            *postprocess_opts
        )

        # TODO: switch for less print
        print(
            f'found {len(processed_tags)} tags out of {len(tags)} from {path}'
        )

        plain_tags = ', '.join(processed_tags)

        if batch_options.output_action_on_conflict == 'copy':
            output = [plain_tags]
        elif batch_options.output_action_on_conflict == 'prepend':
            output.insert(0, plain_tags)
        else:
            output.append(plain_tags)

        if batch_options.remove_duplicated_tag:
            output_path.write_text(
                ', '.join(
                    OrderedDict.fromkeys(
                        map(str.strip, ','.join(output).split(','))
                    )
                ),
                encoding='utf-8'
            )
        else:
            output_path.write_text(
                ', '.join(output),
                encoding='utf-8'
            )

        if batch_options.output_save_json:
            output_path.with_suffix('.json').write_text(
                json.dumps([ratings, tags])
            )

    p = Pool(processes=args.process_count)
    pb = tqdm.tqdm(paths)
    for res in p.imap_unordered(worker, pb):
        pb.update()
        pass
    p.close()
    p.join()

    print('all done :)')

    if unload_model_after_running:
        interrogator.unload()


def main(args):
    if args.command == "single":
        image = Image.open(args.path)
        tag_string, ratings, tags = interrogate_single(
            image,
            args.interrogator,
            args.threshold,
            args.additional_tags,
            args.exclude_tags,
            args.sort_alpha,
            args.add_confident_as_weight,
            args.replace_underscore,
            args.replace_underscore_excludes,
            args.escape_tag)
        print(tag_string)
        return 0
    elif args.command == "batch":
        batch_options = InterrogateBatchOptions(
            args.input_path,
            args.recursive,
            args.output_path,
            args.filename_format,
            args.on_conflict,
            args.remove_duplicated_tag,
            args.save_json
        )
        interrogate_batch(
            batch_options,
            args.interrogator,
            args.threshold,
            args.additional_tags,
            args.exclude_tags,
            args.sort_alpha,
            args.add_confident_as_weight,
            args.replace_underscore,
            args.replace_underscore_excludes,
            args.escape_tag)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    mp.set_start_method("spawn")
    utils.refresh_interrogators()
    dbimutils.load_danbooru_tags()
    args = parser.parse_args()
    parser.exit(main(args))
