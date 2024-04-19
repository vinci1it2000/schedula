# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

r"""
Define the command line interface.

.. click:: schedula.cli:cli
   :prog: schedula
   :show-nested:

"""
import click
import logging
import click_log
from schedula import __version__
from schedula.utils.form.cli import cli as form

log = logging.getLogger('schedula.cli')


class _Logger(logging.Logger):
    def setLevel(self, level):
        super(_Logger, self).setLevel(level)
        frmt = "%(asctime)-15s:%(levelname)5.5s:%(name)s:%(message)s"
        logging.basicConfig(level=level, format=frmt)
        rlog = logging.getLogger()
        # because `basicConfig()` does not reconfig root-logger when re-invoked.
        rlog.level = level
        logging.captureWarnings(True)


logger = _Logger('cli')
click_log.basic_config(logger)


@click.group(
    'schedula', context_settings=dict(help_option_names=['-h', '--help'])
)
@click.version_option(__version__)
def cli():
    """
    schedula command line tool.
    """


cli.add_command(form)

if __name__ == '__main__':
    cli()
