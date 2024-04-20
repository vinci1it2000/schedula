# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

r"""
Define the command line interface for web forms.

.. click:: schedula.utils.form.cli:cli
   :prog: schedula form
   :show-nested:

"""
import os
import click
import logging
import click_log
import os.path as osp

log = logging.getLogger('schedula.utils.form.cli')


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
    'form', context_settings=dict(help_option_names=['-h', '--help'])
)
def cli():
    """
    schedula forms command line tool.
    """


@cli.command(
    'sample', short_help='Generates sample folder for a web form.'
)
@click.option(
    '--folder', '-f', default='.', required=False,
    help="Main folder where app and src are contained.",
    type=click.Path(writable=True, file_okay=False)
)
@click_log.simple_verbosity_option(logger)
def sample(folder='.'):
    """
    Writes a sample folder OUTPUT_FOLDER.

    OUTPUT_FOLDER: schedula WebForm folder template. [default: .]
    """
    import glob
    import shutil
    base_dir = osp.dirname(__file__)
    sample_dir = osp.join(base_dir, 'sample')
    root_dir = osp.join(folder, 'root')

    for k in ('static', 'templates', 'translations'):
        shutil.copytree(
            osp.join(base_dir, k), osp.join(root_dir, k), dirs_exist_ok=True
        )

    for fp in glob.glob(osp.join(sample_dir, '*'), include_hidden=True):
        if osp.relpath(fp, sample_dir) in ('package-lock.json', 'node_modules'):
            continue
        it = glob.glob(
            osp.join(fp, '**', '*.*'), include_hidden=True, recursive=True
        ) if osp.isdir(fp) else [fp]
        for f in it:
            dst = osp.join(folder, osp.relpath(f, sample_dir))
            if osp.isfile(f) and not osp.isfile(dst):
                os.makedirs(osp.dirname(dst), exist_ok=True)
                shutil.copy(f, dst)


@cli.command('build', short_help='Build main folder `src` files.')
@click.option(
    '--folder', '-f', default='.', required=False,
    help="Main folder where app and src are contained.",
    type=click.Path(writable=True, file_okay=False)
)
@click_log.simple_verbosity_option(logger)
def build(folder='.'):
    """
    Build main folder `src` files.
    """
    import subprocess
    subprocess.run('npm i; npm run build', cwd=folder, shell=True)


@cli.command(
    'watch',
    short_help='Run server in debug with continuous build of main folder `src` '
               'files.',
    context_settings=dict(
        ignore_unknown_options=True, allow_extra_args=True,
    )
)
@click.option(
    '--folder', '-f', default='.', required=False,
    help="Main folder where app and src are contained.",
    type=click.Path(writable=True, file_okay=False)
)
@click.option(
    '--app', '-a',
    help="The Flask application or factory function to load, in the form "
         "'module:name'.",
    default='app:app',
    required=False
)
@click.option(
    '--only-flask',
    help="The Flask application or factory function to load, in the form "
         "'module:name'.",
    is_flag=True,
    required=False
)
@click_log.simple_verbosity_option(logger)
@click.pass_context
def watch(ctx, folder='.', app='app:app', only_flask=False):
    """
    Run server in debug with continuous build of main folder `src` files.

    MAIN_FOLDER: Folder path. [default: .]
    """
    if only_flask:
        from livereload import Server
        from schedula.utils.form.gapp import get_module
        module, code = app.split(':')
        app = eval(code, get_module(module, (folder,)))
        app.debug = True
        options = {
            ctx.args[i][2:].replace('-', '_'): ctx.args[i + 1]
            for i in range(0, len(ctx.args), 2)
        }
        server = Server(app.wsgi_app)
        server.watch(osp.join(folder, 'root', '**', '*.*'))
        server.serve(**options)
    else:
        import subprocess
        subprocess.run(
            f'(npm i; npm run watch) & '
            f'(python {__file__} watch --app {app} --only-flask '
            f'{" ".join(ctx.args)})',
            cwd=folder, shell=True
        )


@cli.command('run', short_help='Run server.', context_settings=dict(
    ignore_unknown_options=True, allow_extra_args=True,
))
@click.option(
    '--folder', '-f', default='.', required=False,
    help="Main folder where app and src are contained.",
    type=click.Path(writable=True, file_okay=False)
)
@click.option(
    '--app', '-a',
    help="The Flask application or factory function to load, in the form "
         "'module:name'.",
    default='app:app',
    required=False
)
@click_log.simple_verbosity_option(logger)
@click.pass_context
def run(ctx, folder='.', app='app:app'):
    """
    Building of src files within MAIN_FOLDER.

    MAIN_FOLDER: Folder path. [default: .]
    """
    from .gapp import Application, get_module
    module, code = app.split(':')
    options = {
        ctx.args[i][2:].replace('-', '_'): ctx.args[i + 1]
        for i in range(0, len(ctx.args), 2)
    }
    if 'SECRET_KEY' not in os.environ:
        import secrets
        os.environ['SECRET_KEY'] = secrets.token_hex(32)
    if 'SECURITY_PASSWORD_SALT' not in os.environ:
        import secrets
        salt = f'{secrets.SystemRandom().getrandbits(128)}'
        os.environ['SECURITY_PASSWORD_SALT'] = salt

    Application(
        app=eval(code, get_module(module, (folder,))),
        **options
    ).run()


if __name__ == '__main__':
    cli()
