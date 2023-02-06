#!/bin/bash

OUTPATH="/d/stable-diffusion/archives/"
python hdg_archive.py --board h $OUTPATH
python hdg_archive.py --board hdg $OUTPATH
python hdg_archive.py --board d $OUTPATH
python hdg_archive.py --board aco $OUTPATH
python hdg_archive.py --board e $OUTPATH
python hdg_archive.py --board vt $OUTPATH
python hdg_archive.py --board liveuranus $OUTPATH
