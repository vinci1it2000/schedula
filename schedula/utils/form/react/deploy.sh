#!/usr/bin/env bash

cd "$(dirname "$0")"
npm i
rm -r ../static/schedula/js
rm ../static/asset-manifest.json
mkdir "../static/schedula/js"

echo "Bundle index..."
npm run build
echo "Moving files $f..."
cp -r ./build/static/js ../static/schedula
cp ./build/asset-manifest.json ../static/asset-manifest.json
git add ../static/schedula/js --force
git add ../static/asset-manifest.json --force
echo "Done $f!"
