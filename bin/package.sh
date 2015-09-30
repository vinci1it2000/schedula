#!/bin/bash
#
# Release checklist
# =================
# 0. Run TCs.
# 1. Tag & push
# 2. Gen docs:
#       python setup.py build_sphinx
# 3. Build `wheel,` `sdist` , `doc` archives:
#       ./bin/package.sh
# 4. Upload to PyPi:
#       twine upload -r wltp -su <user> dist/* # Ignore warn about doc-package.
# 5. Generate README instructions:
#       cygstart ./doc/_build/html/readme.html ## & SaveAs 'CO2MPAS-v0.1.1.pdf'
#
my_dir=`dirname "$0"`
cd $my_dir/..

rm -rf build/* dist/*
python setup.py build bdist_wheel sdist

## Build docs
gitver="$(git describe --tags)"
zipfolder="co2mpas-doc-$gitver"
docdir="build/doc/$zipfolder"
mkdir -p build/doc

cp -lr doc/_build/html "$docdir"
pushd build/doc
zip -r "../../dist/$zipfolder.zip" "$zipfolder"

