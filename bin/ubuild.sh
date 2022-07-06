#!/bin/sh
cd "$(dirname "$0")" && cd ..
bash bin/clean.sh

echo 'Installing requirements ...'
bash bin/install_micropython.sh
echo 'Micropython installed!'

micropython/ports/unix/micropython -m upip install -p py micropython-upip
export MICROPYPATH=py
micropython/ports/unix/micropython -m upip install -r requirements/micropython/base.pip
micropython/ports/unix/micropython -m upip install -r requirements/micropython/test.pip
echo 'Requirements installed!'
if env EXTRA=micropython micropython/ports/unix/micropython -m tests.test_micropython; then
  echo 'Building dist..'
  pip uninstall setuptools-git
  wget https://raw.githubusercontent.com/micropython/micropython-lib/35e3c9e4ffc1c5fbd92fa159aa9dfa504f14c495/sdist_upip.py -O micropython/sdist_upip.py
  python usetup.py sdist
  rm -rf dist/*.tar.gz.orig
  echo 'Dist built!'
  echo 'Compiling mpy...'
  mkdir "build"
  tar -xf dist/*.tar.gz -C build
  micropython/ports/unix/micropython -m upip install -p mpy -r requirements/micropython/base.pip
  cp -r build/micropython-*/schedula mpy/schedula
  rm -rf py
  cp -r mpy py
  for file in $(find mpy -type f -name "*.py"); do
    micropython/mpy-cross/mpy-cross "$file"
    rm "$file"
  done
  echo 'Mpy compiled!'
  echo 'Run test for mpy...'
  export MICROPYPATH=mpy
  export MICROPY_MICROPYTHON=micropython/ports/unix/micropython
  if python micropython/tests/run-tests.py -d tests/micropython --keep-path; then
    echo 'Success!'
    exit 0
  fi
fi
exit 1
