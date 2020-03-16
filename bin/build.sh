#!/usr/bin/env bash
cd "$(dirname "$0")" && cd ..
rm -vrf ./build/* ./dist/* ./*.pyc ./*.tgz ./*.egg-info MANIFEST
export ENABLE_SETUP_LONG_DESCRIPTION="TRUE"
python setup.py sdist bdist_wheel -v
