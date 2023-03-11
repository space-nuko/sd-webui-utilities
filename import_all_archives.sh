#!/usr/bin/env sh

set -e

INPATH=/e/ar/

python import_to_hydrus.py import -tsite:4chan -tboard:h $INPATH/archiveofsins/h/**/{catbox,litterbox}
python import_to_hydrus.py import -tsite:8chan -tboard:hdg $INPATH/8chan/hdg/**/{catbox,litterbox}
python import_to_hydrus.py import -tsite:5chan -tboard:liveuranus $INPATH/fate.5ch/liveuranus/**/{catbox,litterbox,majinai}
python import_to_hydrus.py import -tsite:4chan -tboard:vt $INPATH/archive.palanq/vt/**/{catbox,litterbox}
python import_to_hydrus.py import -tsite:4chan -tboard:g $INPATH/desuarchive/g/**/{catbox,litterbox}
python import_to_hydrus.py import -tsite:4chan -tboard:d $INPATH/desuarchive/d/**/{catbox,litterbox}
