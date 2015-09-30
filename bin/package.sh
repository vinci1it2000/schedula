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

