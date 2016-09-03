#! python
# -*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
import contextlib
import os
import pathlib
import unittest


##############
#  Compatibility
#
try:  # pragma: no cover
    assertRaisesRegex = unittest.TestCase.assertRaisesRegex
except:  # pragma: no cover
    assertRaisesRegex = unittest.TestCase.assertRaisesRegexp

def _check_VERSION_in_folder(data_folder, ver_validator):
    """
    Check first non-comment line of `VERSION.txt` in TC-data folder matches my version.

    :param callable ver_validator:
            A func accepting 2 args and returning any non `None` msg
            to indicate invalid-version::

                def is_ver_ok(found_version, version_fpath):
                    if found_version != '1'
                    return "Version %s invalid!" % version_str

            The `found_version` is always the first non-comment line found
            in the `version_fpath` file.
    :return:
            `True` if VERSION found and valid, `False` if no ``VERSION.txt``
            file found, and raises if version found, but invalid.
    """

    vfile = data_folder.joinpath('VERSION.txt')
    if not vfile.exists():
        return False
    with vfile.open('rt') as vf:
        for line in vf:
            if line.startswith('#'):
                continue
            ver = line.strip()
            break
        else:
            raise AssertionError("Cannot find 'version-line' in: %s!" % vfile)

    ver_msg = ver_validator(ver, vfile)
    assert not ver_msg, ver_msg

    return True

def default_ver_validator(exp_version, found_version, version_fpath):
    """Use a partial of it, by currying `exp_version`."""

    if found_version != exp_version:
        return "Expected v%s, found v%s in: %s" % (
                exp_version, found_version, version_fpath)

def get_tc_data_fpath(ver_validator, subfolder=None):
    """
        :param callable ver_validator:
                Read :func:`_check_VERSION_in_folder()` may use partial of
                :func:`default_ver_validator()`

        :param str,Path subfolder:
                where to start checking VERSION and descend
    """
    data_folder = os.environ.get('CO2MPAS_DATA_FOLDER', None)
    if data_folder:
        data_folder = pathlib.Path(data_folder)
    else:
        data_folder = pathlib.Path(__file__).parent.joinpath('data')


    ## Check 1st `VERSION.txt` found while scanning
    ##  parents till `tc_data_folder`.
    #
    subfolder = pathlib.Path(subfolder)
    ver_folder = data_folder = data_folder.joinpath(subfolder).absolute()
    for _ in subfolder.parts:
        if _check_VERSION_in_folder(ver_folder, ver_validator):
            break
        ver_folder = ver_folder.parent
    else:
        raise AssertionError("Cannot find 'VERSION.txt` in: %s!" % data_folder)

    return pathlib.Path(data_folder)

@contextlib.contextmanager
def chdir(path):
    opath = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(opath)

