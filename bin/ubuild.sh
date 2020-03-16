#!/bin/sh
cd "$(dirname "$0")" && cd ..
rm -vrf ./build/* ./dist/* ./*.pyc ./*.tgz ./*.egg-info ./py/* MANIFEST

bash bin/install_micropython.sh

export MICROPYPATH=py
micropython/ports/unix/micropython -m upip install -r requirements/micropython/base.pip
micropython/ports/unix/micropython -m upip install -r requirements/micropython/test.pip

if env EXTRA=micropython micropython/ports/unix/micropython -m tests.test_micropython; then
  wget https://raw.githubusercontent.com/micropython/micropython-lib/master/sdist_upip.py -O micropython/sdist_upip.py
  python usetup.py sdist
  rm -f dist/*.tar.gz.orig
  exit 0
fi
exit 1
