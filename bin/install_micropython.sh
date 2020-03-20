#!/bin/sh
cd "$(dirname "$0")" && cd ..
set -e
[ -e micropython/py/py.mk ] || (git clone https://github.com/micropython/micropython && cd micropython && git checkout tags/v1.12)
[ -e micropython/lib/libffi/autogen.sh ] || (cd micropython && git submodule update --init lib/libffi )
export PKG_CONFIG_PATH="${PKG_CONFIG_PATH}:/usr/local/opt/libffi/lib/pkgconfig"

make -C micropython/mpy-cross -j$(nproc)
make -C micropython/ports/unix -j$(nproc) deplibs
make -C micropython/ports/unix -j2 USER_C_MODULES=$(readlink -f .)
