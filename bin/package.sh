#!/bin/bash
#
# Release checklist
# =================
# INFO: Moved to: https://github.com/JRCSTU/co2mpas/wiki/Developer-Guidelines#release-checklist
#

my_dir=`dirname "$0"`
cd $my_dir/..

## Generate Site:
rm -r ./doc/_build/
cmd /C python setup.py build_sphinx


rm -rf build/* dist/*
python setup.py build bdist_wheel sdist

## Build docs
#
gitver="`git describe --tags`"
gitver="${gitver:1}"
zipfolder="co2mpas-doc-$gitver"
docdir="build/doc/$zipfolder"
mkdir -p build/doc

## Pack docs
#
cp -lr doc/_build/html "$docdir"
pushd build/doc
#zip -r9 "../../dist/$zipfolder.zip" "$zipfolder"
7z a -r "../../dist/$zipfolder.7z" "$zipfolder"
popd


## Check if data-files exist.
#
src_list="`unzip -l ./dist/co2mpas-*.zip`"
whl_list="`unzip -l ./dist/co2mpas-*.whl`"
( echo "$src_list" | grep -q co2mpas_template; ) || echo "FAIL: No TEMPLATE-file in SOURCES!"
( echo "$src_list" | grep -q co2mpas_demo; ) || echo "FAIL: No DEMO in SOURCES!"
( echo "$src_list" | grep -q simVehicle.ipynb; ) || echo "FAIL: No IPYNBS in SOURCES!"

( echo "$whl_list" | grep -q co2mpas_template; ) || echo "FAIL: No TEMPLATE-file in WHEEL!"
( echo "$whl_list" | grep -q co2mpas_demo; ) || echo "FAIL: No DEMO in WHEEL!"
( echo "$whl_list" | grep -q simVehicle.ipynb; ) || echo "FAIL: No IPYNBS in WHEEL!"
