#!/usr/bin/env bash

cd "$(dirname "$0")"

rm -r ../static/schedula/js
mkdir "../static/schedula/js"
rm -r ../static/schedula/css
mkdir "../static/schedula/css"
rm -r ../static/schedula/media
mkdir "../static/schedula/media"
sudo n stable
echo "Installing dependencies..."
npm i --force
echo "Bundle index..."
npm run build
echo "Moving files $f..."
cp -r ./build/static/schedula/js ../static/schedula
cp -r ./build/static/schedula/css ../static/schedula
cp -r ./build/static/schedula/media ../static/schedula

find ../static/schedula/js/ -name "*.js" -exec gzip {} \;
git add ../static/schedula/js/*.js.gz --force
git add ../static/schedula/js/*.LICENSE.txt --force
find ../static/schedula/css/ -name "*.css" -exec gzip {} \;
git add ../static/schedula/css/*.css.gz --force
find ../static/schedula/media/ -name "*" -exec gzip {} \;
git add ../static/schedula/media/*.gz --force

echo "Done $f!"
