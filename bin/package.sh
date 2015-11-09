#!/bin/bash
#
# Release checklist
# =================
# 1. Bump-ver & Update Date+Title in ./CHANGES.rst.
# 2. REMOVE pip install --pre!!!
# 3. Run TCs.
# 4. Gen docs & check OK (i.e. diagrams??):
#       rm -r ./doc/{co2mpas/,_build/}
#       python setup.py build_sphinx
# 5. commit & TAG & push
# 6. Build `wheel,` `sdist` , `doc` archives:
#       ./bin/package.sh
# 7. Upload to PyPi:
#    - DELETE any BETAS (but the last one?)!!
#       - twine upload -r co2mpas -su <user> dist/* # Ignore warn about doc-package.
#
# +++MANUAL+++
# 8. Generate RELEASE_NOTES:
#    - open ./doc/_build/html/co2mpas_RelNotes.html ## & PrintAs 'co2mpas_RelNotes-v0.1.1.pdf'
# 9. Prepare site at http://co2mpas.io/
#    - Copy docs-archive & rename sources package!
#    - Expand docs, link STABLE ad LATEST
# 10. Prepare email (and test)
#    - Use email-body to draft a new "Release" in github (https://github.com/JRCSTU/co2mpas/releases).
#

my_dir=`dirname "$0"`
cd $my_dir/..

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
