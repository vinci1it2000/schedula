#!/usr/bin/env bash

cd "$(dirname "$0")"

rm -r ../static/schedula/js
mkdir "../static/schedula/js"
rm -r ../static/schedula/css
mkdir "../static/schedula/css"

echo "Installing dependences..."
npm i
echo "Bundle index..."
npm run build
echo "Moving files $f..."
cp -r ./build/static/schedula/js ../static/schedula
cp -r ./build/static/schedula/css ../static/schedula
git add ../static/schedula/js/*.js --force
git add ../static/schedula/js/*.LICENSE.txt --force
git add ../static/schedula/css/*.css --force
echo "Done $f!"
