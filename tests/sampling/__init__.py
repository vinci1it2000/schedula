#! python
# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
import os.path as osp

mydir = osp.dirname(__file__)
_inp_fpath = osp.join(mydir, '..', '..', 'co2mpas', 'demos', 'co2mpas_demo-0.xlsx')
_out_fpath = osp.join(mydir, 'output.xlsx')
