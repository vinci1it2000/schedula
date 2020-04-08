#!/bin/sh
cd "$(dirname "$0")" && cd ..
bash bin/clean.sh

echo 'Installing requirements ...'
bash bin/install_micropython.sh

export MICROPYPATH=py
micropython/ports/unix/micropython -m upip install -r requirements/micropython/base.pip
micropython/ports/unix/micropython -m upip install -r requirements/micropython/test.pip

if env EXTRA=micropython micropython/ports/unix/micropython -m tests.test_micropython; then
  wget https://raw.githubusercontent.com/micropython/micropython-lib/master/sdist_upip.py -O micropython/sdist_upip.py
  python usetup.py sdist
  rm -rf dist/*.tar.gz.orig
  mkdir "build"
  tar -xf dist/*.tar.gz -C build
  micropython/ports/unix/micropython -m upip install -p mpy -r requirements/micropython/base.pip
  cp -r build/micropython-*/schedula mpy/schedula
  rm -rf py
  cp -r mpy py
  for file in $(find mpy -type f -name "*.py"); do
    micropython/mpy-cross/mpy-cross "$file" -mcache-lookup-bc
    rm "$file"
  done

  export MICROPYPATH=mpy
  export MICROPY_MICROPYTHON=micropython/ports/unix/micropython
  if micropython/tests/run-tests -d tests/micropython --keep-path; then
    exit 0
  fi
fi
exit 1
