#!/usr/bin/env sh

set -e

INPATH=/e/sd/outputs

python import_to_hydrus.py import $INPATH/txt2img-images -tsite:personal -tgen_type:txt2img-images
python import_to_hydrus.py import $INPATH/txt2img-grids  -tsite:personal -tgen_type:txt2img-grids
python import_to_hydrus.py import $INPATH/img2img-images -tsite:personal -tgen_type:img2img-images
python import_to_hydrus.py import $INPATH/img2img-grids  -tsite:personal -tgen_type:img2img-grids
python import_to_hydrus.py import $INPATH/extras-images  -tsite:personal -tgen_type:extras-images
python import_to_hydrus.py import $INPATH/gimped         -tsite:personal -tgen_type:gimped
