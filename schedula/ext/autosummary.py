#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2025, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It is a patch to sphinx.ext.autosummary.
"""
import warnings
import logging
from pathlib import Path
from typing import Any
from sphinx.util.inspect import getall
from sphinx.util.osutil import ensuredir
from sphinx.ext.autosummary import (
    import_by_name, _get_documenter, get_rst_suffix, mock, import_ivar_by_name,
    ImportExceptionGroup
)
from sphinx.ext.autosummary.generate import (
    find_autosummary_in_files, AutosummaryRenderer, ModuleScanner, _get_members,
    _get_module_attrs, _get_modules, _split_full_qualified_name
)
from sphinx.locale import __

logger = logging.getLogger(__name__)
warnings.filterwarnings(
    'ignore', category=DeprecationWarning, module='docutils'
)


def generate_autosummary_content(
        name,
        obj,
        parent,
        template,
        template_name,
        imported_members,
        recursive,
        context,
        modname,
        qualname=None,
        *,
        config,
        events,
        registry,
):
    doc = _get_documenter(obj, parent, registry=registry)

    ns = {}
    ns.update(context)

    if doc.objtype == 'module':
        scanner = ModuleScanner(obj, config=config, events=events,
                                registry=registry)
        ns['members'] = scanner.scan(imported_members)

        respect_module_all = not config.autosummary_ignore_module_all
        imported_members = imported_members or (
                '__all__' in dir(obj) and respect_module_all
        )

        ns['functions'], ns['all_functions'] = _get_members(
            doc,
            obj,
            {'function'},
            config=config,
            events=events,
            registry=registry,
            imported=imported_members,
        )
        ns['classes'], ns['all_classes'] = _get_members(
            doc,
            obj,
            {'class'},
            config=config,
            events=events,
            registry=registry,
            imported=imported_members,
        )
        ns['exceptions'], ns['all_exceptions'] = _get_members(
            doc,
            obj,
            {'exception'},
            config=config,
            events=events,
            registry=registry,
            imported=imported_members,
        )
        ns['attributes'], ns['all_attributes'] = _get_module_attrs(name, ns[
            'members'])
        ns['dispatchers'], ns['all_dispatchers'] = _get_members(
            doc,
            obj,
            {'dispatcher'},
            config=config,
            events=events,
            registry=registry,
            imported=imported_members,
        )

        ispackage = hasattr(obj, '__path__')
        if ispackage and recursive:
            # Use members that are not modules as skip list, because it would then mean
            # that module was overwritten in the package namespace
            skip = (
                    ns['all_functions']
                    + ns['all_classes']
                    + ns['all_exceptions']
                    + ns['all_attributes']
            )

            # If respect_module_all and module has a __all__ attribute, first get
            # modules that were explicitly imported. Next, find the rest with the
            # get_modules method, but only put in "public" modules that are in the
            # __all__ list
            #
            # Otherwise, use get_modules method normally
            if respect_module_all and '__all__' in dir(obj):
                imported_modules, all_imported_modules = _get_members(
                    doc,
                    obj,
                    {'module'},
                    config=config,
                    events=events,
                    registry=registry,
                    imported=True,
                )
                skip += all_imported_modules
                public_members = getall(obj)
            else:
                imported_modules, all_imported_modules = [], []
                public_members = None

            modules, all_modules = _get_modules(
                obj, skip=skip, name=name, public_members=public_members
            )
            ns['modules'] = imported_modules + modules
            ns['all_modules'] = all_imported_modules + all_modules
    elif doc.objtype == 'class':
        ns['members'] = dir(obj)
        ns['inherited_members'] = set(dir(obj)) - set(obj.__dict__.keys())
        ns['methods'], ns['all_methods'] = _get_members(
            doc,
            obj,
            {'method'},
            config=config,
            events=events,
            registry=registry,
            include_public={'__init__'},
        )
        ns['attributes'], ns['all_attributes'] = _get_members(
            doc,
            obj,
            {'attribute', 'property'},
            config=config,
            events=events,
            registry=registry,
        )

    if modname is None or qualname is None:
        modname, qualname = _split_full_qualified_name(name)

    if doc.objtype in {'method', 'attribute', 'property'}:
        ns['class'] = qualname.rsplit('.', 1)[0]

    if doc.objtype == 'class':
        shortname = qualname
    else:
        shortname = qualname.rsplit('.', 1)[-1]

    ns['fullname'] = name
    ns['module'] = modname
    ns['objname'] = qualname
    ns['name'] = shortname

    ns['objtype'] = doc.objtype
    ns['underline'] = len(name) * '='

    if template_name:
        return template.render(template_name, ns)
    else:
        return template.render(doc.objtype, ns)


def generate_autosummary_docs(
        sources,
        output_dir=None,
        suffix='.rst',
        base_path=None,
        imported_members=False,
        app=None,
        overwrite=True,
        encoding='utf-8',
):
    """Generate autosummary documentation for the given sources.

    :returns: list of generated files (both new and existing ones)
    """
    assert app is not None, 'app is required'

    showed_sources = sorted(sources)
    if len(showed_sources) > 20:
        showed_sources = showed_sources[:10] + ['...'] + showed_sources[-10:]
    logger.info(
        __('[autosummary] generating autosummary for: %s'),
        ', '.join(showed_sources)
    )

    if output_dir:
        logger.info(__('[autosummary] writing to %s'), output_dir)

    if base_path is not None:
        base_path = Path(base_path)
        source_paths = [base_path / filename for filename in sources]
    else:
        source_paths = list(map(Path, sources))

    template = AutosummaryRenderer(app)

    # read
    items = find_autosummary_in_files(source_paths)

    # keep track of new files
    new_files = []
    all_files = []

    filename_map = app.config.autosummary_filename_map

    # write
    for entry in sorted(set(items), key=str):
        if entry.path is None:
            # The corresponding autosummary:: directive did not have
            # a :toctree: option
            continue

        path = output_dir or Path(entry.path).resolve()
        ensuredir(path)

        try:
            name, obj, parent, modname = import_by_name(entry.name)
            qualname = name.replace(modname + '.', '')
        except ImportExceptionGroup as exc:
            try:
                # try to import as an instance attribute
                name, obj, parent, modname = import_ivar_by_name(entry.name)
                qualname = name.replace(modname + '.', '')
            except ImportError as exc2:
                if exc2.__cause__:
                    exceptions: list[BaseException] = [*exc.exceptions,
                                                       exc2.__cause__]
                else:
                    exceptions = [*exc.exceptions, exc2]

                errors = list(
                    {f'* {type(e).__name__}: {e}' for e in exceptions}
                )
                logger.warning(
                    __('[autosummary] failed to import %s.\nPossible hints:\n%s'),
                    entry.name,
                    '\n'.join(errors),
                )
                continue

        context: dict[str, Any] = {**app.config.autosummary_context}

        content = generate_autosummary_content(
            name,
            obj,
            parent,
            template,
            entry.template,
            imported_members,
            entry.recursive,
            context,
            modname,
            qualname,
            config=app.config,
            events=app.events,
            registry=app.registry,
        )

        file_path = Path(path, filename_map.get(name, name) + suffix)
        all_files.append(file_path)
        if file_path.is_file():
            with file_path.open(encoding=encoding) as f:
                old_content = f.read()

            if content == old_content:
                continue
            if overwrite:  # content has changed
                with file_path.open('w', encoding=encoding) as f:
                    f.write(content)
                new_files.append(file_path)
        else:
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)
            new_files.append(file_path)

    # descend recursively to new files
    if new_files:
        all_files.extend(
            generate_autosummary_docs(
                [str(f) for f in new_files],
                output_dir=output_dir,
                suffix=suffix,
                base_path=base_path,
                imported_members=imported_members,
                app=app,
                overwrite=overwrite,
            )
        )

    return all_files


def process_generate_options(app):
    genfiles = app.config.autosummary_generate

    if genfiles is True:
        env = app.env
        genfiles = [
            str(env.doc2path(x, base=False))
            for x in env.found_docs
            if env.doc2path(x).is_file()
        ]
    elif genfiles is False:
        pass
    else:
        ext = list(app.config.source_suffix)
        genfiles = [
            genfile + (ext[0] if not genfile.endswith(tuple(ext)) else '')
            for genfile in genfiles
        ]

        for entry in genfiles[:]:
            if not (app.srcdir / entry).is_file():
                logger.warning(__('autosummary_generate: file not found: %s'),
                               entry)
                genfiles.remove(entry)

    if not genfiles:
        return

    suffix = get_rst_suffix(app)
    if suffix is None:
        logger.warning(
            __(
                'autosummary generates .rst files internally. '
                'But your source_suffix does not contain .rst. Skipped.'
            )
        )
        return

    imported_members = app.config.autosummary_imported_members
    with mock(app.config.autosummary_mock_imports):
        generate_autosummary_docs(
            genfiles,
            suffix=suffix,
            base_path=app.srcdir,
            app=app,
            imported_members=imported_members,
            overwrite=app.config.autosummary_generate_overwrite,
            encoding=app.config.source_encoding,
        )


def setup(app):
    app.setup_extension('sphinx.ext.autosummary')
    app.add_config_value('autosummary_skip_members', [], 'html')

    # replace callback process_generate_options of 'builder-inited' event.
    import sphinx.ext.autosummary as mdl
    pgo = mdl.process_generate_options
    event = 'builder-inited'
    listeners = app.events.listeners[event]
    from sphinx.events import EventListener
    for i, event in enumerate(listeners):
        if pgo in event:
            listeners[i] = EventListener(*(
                process_generate_options if e is pgo else e for e in event
            ))
