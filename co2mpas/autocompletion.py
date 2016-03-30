#!/usr/bin/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
Bash-completion for *docopt* cmd-line utilities.

The `fun:`autocomplete_bash_cmd()` has to be invoked from bash whenever
auto-completion is required for some docopt-based script.
Turn that function into an executable (use `setup.py` *entry-points*)
and add a line in `.bashrc` like that::

    complete -o bashdefault -C <this-executable>-bash-completion <docopt-cmd>
"""

import glob
import sys

import docopt

import itertools as itt


def _parse_docopt(doc):
    options = docopt.parse_defaults(doc)
    pure_doc = docopt.formal_usage(docopt.printable_usage(doc))
    pattern = docopt.parse_pattern(pure_doc, options)
    return pattern


def _gen_docopt_options(pattern):
    for o in pattern.flat(docopt.Option):
        if o.short:
            yield o.short
        if o.long:
            yield o.long


def _gen_docopt_subcmds(pattern):
    return (p.name for p in pattern.flat(docopt.Command))


# noinspection PyIncorrectDocstring
def get_wordlist_from_docopt(doc):
    """Parses docopt-string into a wordlist."""
    pattern = _parse_docopt(doc)
    opts_list = _gen_docopt_options(pattern)
    cmds_list = _gen_docopt_subcmds(pattern)
    return sorted(set(itt.chain(opts_list, cmds_list)))


def _print_words(words):
    if words:
        ## Avoid '^M' under Windows, or else, bash ignores command.
        print(' '.join(s for s in words), end='')


# noinspection PyIncorrectDocstring
def print_wordlist_from_docopt(doc):
    """
    Use the output of this function with bash's `complete -W` option.

    Example::

        complete -fd -W "`python -m <this-function-as-main>`" <cmd-to-complete>
    """
    _print_words(get_wordlist_from_docopt(doc))


# noinspection PyIncorrectDocstring
def do_autocomplete(doc, *args):
    """Auto-complete based on docopt-string - not to be invoke directly.

    :param list args: if missing `sys.argv` assumed

    Bash example::

        complete -o bashdefault -W "python -m <this-function-as-main>" <cmd-to-complete>
    """
    if not args:
        args = sys.argv
    if len(args) < 3:
        sys.exit(do_autocomplete.__doc__)
    py, cmd_name, prefix, prev_arg = args  # @UnusedVariable

    words_gen = []
    options, pattern = _parse_docopt(doc)
    if prefix.startswith("-"):
        opts_list = _gen_docopt_options(options)
        words_gen.append(opt
                         for opt in opts_list
                         if opt and opt.startswith(prefix))
    else:
        words_gen.append(subcmd
                for subcmd in _gen_docopt_subcmds(pattern)
                if subcmd and subcmd.startswith(prefix))
        files = glob.glob("{}*".format(prefix))
        words_gen.append(files)

    if words_gen:
        words_gen = sorted(set(itt.chain(*words_gen)))
        _print_words(words_gen)


