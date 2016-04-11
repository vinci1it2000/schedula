#!/bin/bash
#-*- coding: utf-8 -*-
#
# Copyright 2013-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl


## Checks that README has no RsT-syntactic errors.
# Since it is used by `setup.py`'s `description` if it has any errors, 
# PyPi would fail parsing them, ending up with an ugly landing page,
# when uploaded.

set +x ## Enable for debug

my_dir=`dirname "$0"`
cd $my_dir/..

py=""
rst="rst2html"
if [ ! -x "`which $rst 2>/dev/null`" ]; then
    ## In WinPython, only a python-script exist in PATH,
    #   so execute it with python-interpreter.
    #
    exe="`which rst2html.py 2> /dev/null`" 
    if [ $? -eq 0 ]; then
        py=python
        rst="$exe"
    else
        echo -e "Cannot find 'rst2html'! \n Sphinx installed? `pip show sphinx`" && 
        exit 1
    fi
    
    if [ -x "`which cygpath`" ]; then
        rst="`cygpath -w $rst`"
    fi
fi

export PYTHONPATH='$my_dir/..'
python setup.py --long-description | $py "$rst"  --halt=warning > /dev/null && echo OK
