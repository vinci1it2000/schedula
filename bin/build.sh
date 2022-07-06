#!/usr/bin/env bash
cd "$(dirname "$0")" && cd ..
bash bin/clean.sh
export ENABLE_SETUP_LONG_DESCRIPTION="TRUE"
pip uninstall setuptools-git
python setup.py sdist bdist_wheel -v
