#!/usr/bin/env bash

cd "$(dirname "$0")"

rm -r ../static/schedula/js
mkdir "../static/schedula/js"

echo "Installing dependences..."
npm i
echo "Bundle index..."
npm run build
echo "Moving files $f..."
cp -r ./build/static/schedula/js ../static/schedula
git add ../static/schedula/js/*.js --force
git add ../static/schedula/js/*.LICENSE.txt --force
echo "Done $f!"
