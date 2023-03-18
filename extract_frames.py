#!/usr/bin/env python

import os
import os.path
import argparse
from pprint import pp
import ffmpeg

parser = argparse.ArgumentParser(description='Extract frames')
parser.add_argument('files', type=str, nargs="*", help='Files to process')
parser.add_argument('--out', '-o', type=str, default=".", help='Output directory')
parser.add_argument('--extract-every-secs', '-e', type=float, default=0.5, help='Extract a frame every N seconds')

args = parser.parse_args()

OUTPATH = os.path.join(args.out, "extracted")

if not args.files:
    parser.print_help()
    exit(1)

for file in args.files:
    try:
        data = ffmpeg.probe(file)
    except ffmpeg.Error as e:
        print(f"!!! FAILED to probe: {file}")
        print('stdout:', e.stdout.decode('utf8'))
        print('stderr:', e.stderr.decode('utf8'))
        continue

    format = data["format"]
    duration = float(format["duration"])
    frames = duration / args.extract_every_secs
    fps = eval(data["streams"][0]["r_frame_rate"])
    fps = 1 / args.extract_every_secs

    basename = os.path.splitext(os.path.basename(file))[0]
    outpath = os.path.join(OUTPATH, basename)
    os.makedirs(outpath, exist_ok=True)

    print(f"{file}:")
    print(f"   -> {outpath}")
    print(f"- {duration} secs, {fps} fps, {frames} frames to extract")

    try:
        input = ffmpeg.input(file)
        input.filter('fps', fps=fps) \
             .output(os.path.join(outpath, f"{basename}_%d.png"),
                     #video_bitrate='5000k',
                     #s='64x64',
                     sws_flags='bilinear',
                     start_number=0) \
             .run(capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as e:
        print('stdout:', e.stdout.decode('utf8'))
        print('stderr:', e.stderr.decode('utf8'))
