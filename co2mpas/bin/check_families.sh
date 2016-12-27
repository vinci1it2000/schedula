#!/bin/bash
#
# Runs SETBELT ad-infinitum, unless error,
# to detect any "families" of solutions with each python run.
#

my_dir=`dirname "$0"`
cd $my_dir/..

r=0
while :
do
    echo "+++RUN no$r..."
     python -m unittest -v tests.test_datacheck || break
     r=$((r + 1))
done
echo "+++ERROR IN RUN no$r!"

