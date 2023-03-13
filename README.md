# sd-webui-utilities

This is a small repository of various Python scripts I've developed for automating things related to Stable Diffusion datasets and outputs, like scraping images and modifying caption files.

To run the scripts in this repository, you'll need to install the requirements with `pip install -r requirements.txt` first.

## tagtools.py

The big one, this is meant to be an all-in-one script for all things related to `.txt` caption sidecars next to images in your Stable Diffusion training datasets. Pass `-h` on the command line for more details like extra arguments related to each command.

**Note:** In most cases you'll want to pass `-r` for recursive so that the script looks at all the images in the folder you specify recursively. Also, when passing tags as arguments to a command, you should use the underscored Danbooru format and separate the tags with spaces, not commas (`python tagtools.py -r add /path/to/dataset some_tag another_tag`)

List of commands (to be run like `python tagtools.py -r <command> /path/to/dataset <args...>`):

- `fixup` - Renames `*.png.txt` and similar files downloaded by [gallery-dl](https://github.com/mikf/gallery-dl) to `*.txt` required by Stable Diffusion finetuners, converts newline-separated tag lists in gallery-dl format to comma-separated, normalizes Unicode characters like punctuation, escapes special characters, and removes extra spaces between tags
- `add` - Adds one or more tags to all caption files in a folder.
  + Can also pass `--if some_other_tag` to only add the tag if `some_other_tag` is already present in the caption.
- `remove` - Removes one or more tags from all caption files in a folder.
- `replace` - Replaces one tag with another tag in all caption files.
- `move_to_front` - Moves the specified tags to the front of all caption files, if present, for use with the `keep_tokens` feature of model finetuners. You can pass multiple tags and they will be ordered correctly at the front of each tag list.
- `move_categories_to_front` - Moves the tags with the specified Danbooru tag categories to the front of all caption files.
  + For example, you can run `move_categories_to_front /path/to/dataset artist character`, and you will find tags will be ordered to the front like `ke-ta, komeiji koishi, komeiji satori`.
  + Depends on the file [danbooru.csv](https://github.com/arenatemp/sd-tagging-helper/blob/master/danbooru.csv)
  + Valid categories: `general`, `artist`, `copyright`, `character`, `meta`
- `merge` - Merges two directories of captions where the subfolder hierarchy matches up between both folders.
  + Useful in the case where you have a set of manually curated captions in one folder, but accidentally flub the autotagging and want to merge in those tags separately from your painstakingly curated set
- `strip_suffix` - Strips a suffix from all tags. So if you pass `(neptune_series)`, then the tag `neptune (neptune series)` in a caption file will be changed to `neptune`.
  + Useful if the suffix clashes with a character name or other unrelated tag.
- `validate` - Validates a dataset, checking if the folder names have the correct format for LoRA training, making sure no image files are corrupted, and checking the presence/validity of all caption files
- `stats` - Prints some neatly-formatted stats for image count/repeats in a dataset.
- `organize` - A very useful command, this moves a subset of the images in your dataset that contain the specified tags into their own folder. Indespensible for getting rid of comic/traditional media images or separating out solo character images to bump up their repeats.
  + You can pass multiple tags, and the images will be moved only if all the tags are found in each caption.
- `organize_lowres` - Separates out low-resolution images from the dataset.
- `backup_tags` - Backs up the caption files in a dataset, preserving directory structure, such that you can just merge the backup folder into the original if you make a mistake later.
- `dedup` - A no-frills image deduplicator. Simply pass in the dataset folder and all your duplicates will be moved into a separate `duplicates` directory so you can delete them all or inspect each one by hand.
  + This is a light wrapper around the [imagededup](https://github.com/idealo/imagededup) library that also handles moving the caption `.txt` files along with the duplicates.
  
## autotagger.py

A standalone version of the [Waifu Diffusion 1.4 Tagger Extension](https://github.com/toriato/stable-diffusion-webui-wd14-tagger) for webui. I appropriated this because I found it somewhat annoying to have to wait a couple of minutes for the webui to start when I just wanted to autotag a dataset.

Here is an example of how to run it (pass `--help` for more details):

```
python autotagger.py batch -r /path/to/dataset -a "additional_tag" -t 0.35 -c append
```

This runs the autotagger at 0.35 threshold on all files in `/path/to/dataset` recursively, appending the found tags if the caption file exists already, and adds `additional_tag` to all captions output by the script.

## extract_frames.py

A simple ffmpeg-based frame extractor for a set of video files in a directory. Each set of extracted frames per video gets its own subdirectory. You'll want to run the output through `tagtools.py dedup` to prune any duplicates afterwards.

## import_to_hydrus.py

This is a smart [Hydrus Network](https://hydrusnetwork.github.io/hydrus/index.html) importer for your Stable Diffusion outputs that contain embedded infotext. It parses the settings list for each image in such a way that you can look up the models used by webui's built-in extra networks support or the [sd-webui-additional-networks](https://github.com/kohya-ss/sd-webui-additional-networks) extension using Hyrdus' tag search. All comma-separated tokens accounting for `(emphasis syntax:1.2)`, `[prompt:editing:0.5]` and `BREAK` are parsed out as well.

To set this up, you need to make sure your Hydrus installation has a tag service named `stable-diffusion-webui`, and put a Hydrus access key with the proper permissions into an `.env` file in this directory (or otherwise export a `HYDRUS_ACCESS_KEY` to your shell environment). Check [.env.example](./.env.example) for the format that should be followed for the `.env` file.

To tag your outputs neatly by which type of image generation routine was used (`txt2img`/`img2img`, single images/grids), check the [import_all_personal.sh](./import_all_personal.sh) script for an example.

**Note:** Only images with the `parameters` PNG infotext will be imported by this script, this is so your Hydrus inbox won't get spammed with untagged images. Also, images that are all black are skipped by the importer.

## hdg_archive.py

This script archives threads, images and catbox/litterbox files on various \*chan boards and archive sites. Useful for gathering some examples of gens to learn from later. Also scoops up `.safetensors` models that anons upload to catbox and the like.

For a quick and easy way to just archive everything from known boards, check out the [archive_all.sh](./archive_all.sh) script.

## latest_megas.py

If you have a bunch of saved threads from `hdg_archive.py`, point this script at the root directory of that script's output to get a list of the MEGA links found in the last N threads (5 by default). You can then dump them all into JDownloader if you're insane or something (like me).

## scrape_\*.py

A bunch of random scrapers I've hacked together for various websites of interest. Could be useful if you're trying to get outside the realm of scraping danbooru/pixiv/twitter and into unexplored higher-art fare.

## dump_danbooru_meta.py

Dumps all JSON metadata found on Danbooru for their various APIs. *Yes, all of it.* You'll probably need a Gold account key and many hours for this to work satisfactorily. Place your credentials in an `.env` file as `DANBOORU_LOGIN` and `DANBOORU_TOKEN`.

Although, if you want to save a good deal of time, you can just see the [danbooru-metadata](https://huggingface.co/datasets/stma/danbooru-metadata) dataset for a full metadata dump from Feburary 2023.

## build_model_db.py

Creates an SQLite database of all the LoRA models in the given directory. Useful for comparing training parameters between popular models, and also embeds preview images. I recommend [DB Browser for SQLite](https://github.com/sqlitebrowser/sqlitebrowser) for looking through the resulting database.

## convert_to_safe.py

Converts all `.ckpt` files in a directory into the `.safetensors` format.

## print_metadata.py

Prints the metadata of a `.safetensors` file. Useful if you want to verify this information in trained LoRA files, for example.

## rectangle_crop.py

A quick and dirty script for cropping out a single rectangular region from artbook-like images. Mostly useful for images scraped from yande.re and similar sites that have raw artbook scans, although it can't handle more than one image region on the page.
