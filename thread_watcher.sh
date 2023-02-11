#!/bin/bash

OUTPATH="/d/stable-diffusion/archives/"
while true; do
    python hdg_archive.py -n3 --board g $OUTPATH
    python hdg_archive.py -n3 --board h $OUTPATH
    python hdg_archive.py -n3 --board hdg $OUTPATH
    python hdg_archive.py -n3 --board d $OUTPATH
    python hdg_archive.py -n3 --board aco $OUTPATH
    python hdg_archive.py -n3 --board e $OUTPATH
    python hdg_archive.py -n3 --board vt $OUTPATH
    python hdg_archive.py -n3 --board liveuranus $OUTPATH
    echo "+++ Sleeping for 15 minutes..."
    sleep 900
done
