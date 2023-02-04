#!/usr/bin/env python

import os
import os.path
import argparse
from pprint import pp
import ffmpeg

parser = argparse.ArgumentParser(description='Extract frames')
parser.add_argument('files', type=str, nargs="*", help='Files to process')
parser.add_argument('--out', type=str, default=".", help='Output directory')
parser.add_argument('--extract-every-secs', type=float, default=0.5, help='Extract a frame every N seconds')

args = parser.parse_args()

OUTPATH = os.path.join(args.out, "extracted")

for file in args.files:
    try:
        data = ffmpeg.probe(file)
    except Exception as ex:
        print(f"!!! FAILED to probe: {file}")
        continue

    format = data["format"]
    duration = float(format["duration"])
    frames = duration / args.extract_every_secs
    fps = 1 / frames

    outpath = os.path.join(OUTPATH, os.path.splitext(os.path.basename(file))[0])
    os.makedirs(outpath, exist_ok=True)

    print(f"{file}:")
    print(f"   -> {outpath}")
    print(f"- {duration} secs, {frames} frames to extract")

    try:
        input = ffmpeg.input(file)
        input.filter('fps', fps=fps) \
             .output(os.path.join(outpath, "%d.png"),
                     #video_bitrate='5000k',
                     #s='64x64',
                     sws_flags='bilinear',
                     start_number=0) \
             .run(capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as e:
        print('stdout:', e.stdout.decode('utf8'))
        print('stderr:', e.stderr.decode('utf8'))
