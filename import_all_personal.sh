#!/usr/bin/env sh

INPATH=/e/sd/outputs

python import_to_hydrus.py $INPATH/txt2img-images -tsite:personal -tgen_type:txt2img-images
python import_to_hydrus.py $INPATH/txt2img-grids  -tsite:personal -tgen_type:txt2img-grids
python import_to_hydrus.py $INPATH/img2img-images -tsite:personal -tgen_type:img2img-images
python import_to_hydrus.py $INPATH/img2img-grids  -tsite:personal -tgen_type:img2img-grids
python import_to_hydrus.py $INPATH/extras-images  -tsite:personal -tgen_type:extras-images
