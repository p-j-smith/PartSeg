#!/usr/bin/env bash

if [ -d /tmp/PartSeg ]; then
    cd /tmp/PartSeg
    git pull
else
    git clone https://github.com/4DNucleome/PartSeg.git /tmp/PartSeg
    cd /tmp/PartSeg
fi

export PATH=/opt/python/bin:${PATH}
export LD_LIBRARY_PATH=/opt/python/lib:${LD_LIBRARY_PATH}

pip3 install numpy cython pyinstaller
pip3 install .

python3 /tmp/create_build.py /tmp/PartSeg