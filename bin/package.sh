#!/bin/bash
#
# Release checklist
# =================
# 1. Update ./CHANGES.rst
# 2. REMOVE pip install --pre!!!
# 3. Run TCs.
# 4. Tag & push
# 5. Gen docs (check diagrams OK!):
#       python setup.py build_sphinx
# 6. Build `wheel,` `sdist` , `doc` archives:
#       ./bin/package.sh
# 7. Upload to PyPi:
#    - DELETE any BETAS (but the last one?)!!
#       - twine upload -r wltp -su <user> dist/* # Ignore warn about doc-package.
#
# +++MANUAL+++
# 8. Generate README:
#       cygstart ./doc/_build/html/co2mpas_README.html ## & PrintAs 'CO2MPAS_README-v0.1.1.pdf'
# 9. Generate RELEASE_NOTES:
#       cygstart ./doc/_build/html/co2mpas_RelNotes.html ## & PrintAs 'CO2MPAS_RelNotes-v0.1.1.pdf'
# 10. Prepare email (and test).
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
#zip -r9 "../../dist/$zipfolder.zip" "$zipfolder"
7z a -r "../../dist/$zipfolder.7z" "$zipfolder"
popd

( unzip -l ./dist/co2mpas-*.zip | grep -q co2mpas_template; ) || echo "FAIL: No TEMPLATE-file in SOURCES!"
( unzip -l ./dist/co2mpas-*.zip | grep -q co2mpas_example; ) || echo "FAIL: No EXAMPLES in SOURCES!"
( unzip -l ./dist/co2mpas-*.whl | grep -q co2mpas_template; ) || echo "FAIL: No TEMPLATE-file in WHEEL!"
( unzip -l ./dist/co2mpas-*.whl | grep -q co2mpas_example; ) || echo "FAIL: No EXAMPLES in WHEEL!"
