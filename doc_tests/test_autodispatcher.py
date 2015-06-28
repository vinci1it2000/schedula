
from doc_tests.util import TestApp, Struct, raises
from nose.tools import with_setup

from six import StringIO
from docutils.statemachine import ViewList

from doc._ext.dsp_directive import DispatcherDirective, add_documenter, \
    DispatcherDocumenter, PLOT
from dispatcher import Dispatcher
from dispatcher.draw import dsp2dot
app = None


def setup_module():
    global app
    app = TestApp()
    app.builder.env.app = app
    app.builder.env.temp_data['docname'] = 'dummy'
    app.connect('autodoc-process-docstring', process_docstring)
    app.connect('autodoc-process-signature', process_signature)
    app.connect('autodoc-skip-member', skip_member)


def teardown_module():
    app.cleanup()


directive = options = None


def setup_test():
    global options, directive
    global processed_docstrings, processed_signatures, _warnings

    options = Struct(
        des = True,
        opt = PLOT,
        data = True,
        func = True,
        code = True,
        inherited_members = False,
        undoc_members = False,
        private_members = False,
        special_members = False,
        imported_members = False,
        show_inheritance = False,
        noindex = False,
        annotation = None,
        synopsis = '',
        platform = '',
        deprecated = False,
        members = [],
        member_order = 'alphabetic',
        exclude_members = set(),
    )

    directive = Struct(
        env = app.builder.env,
        genopt = options,
        result = ViewList(),
        warn = warnfunc,
        filename_set = set(),
    )

    processed_docstrings = []
    processed_signatures = []
    _warnings = []


_warnings = []

def warnfunc(msg):
    _warnings.append(msg)


processed_docstrings = []

def process_docstring(app, what, name, obj, options, lines):
    processed_docstrings.append((what, name))
    if name == 'bar':
        lines.extend(['42', ''])

processed_signatures = []

def process_signature(app, what, name, obj, options, args, retann):
    processed_signatures.append((what, name))
    if name == 'bar':
        return '42', None


def skip_member(app, what, name, obj, skip, options):
    if name in ('__special1__', '__special2__'):
        return skip
    if name.startswith('_'):
        return True
    if name == 'skipmeth':
        return True


@with_setup(setup_test)
def test_format_signature():
    def formatsig(objtype, name, obj, args, retann):
        inst = DispatcherDirective._registry[objtype](directive, name)
        inst.fullname = name
        inst.doc_as_attr = False  # for class objtype
        inst.object = obj
        inst.objpath = [name]
        inst.args = args
        inst.retann = retann
        res = inst.format_signature()
        print(res)
        return res

    # no signatures for dispatchers
    dsp = Dispatcher()
    assert formatsig('dispatcher', 'dsp', dsp, None, None) == ''

@with_setup(setup_test)
def test_get_doc():
    def getdocl(objtype, obj, name, encoding=None):
        inst = DispatcherDirective._registry[objtype](directive, 'tmp')

        inst.objpath = [name]
        inst.object = obj
        ds = inst.get_doc(encoding)
        # for testing purposes, concat them and strip the empty line at the end
        res = sum(ds, [])[:-1]
        print(res)
        return res

    # objects without docstring
    dsp_local = Dispatcher()
    assert getdocl('dispatcher', dsp_local, 'dsp_local') == []

    # standard function, diverse docstring styles...
    dsp_local = Dispatcher(description='Description')
    assert getdocl('dispatcher', dsp_local, 'dsp_local') == ['Description']

    # standard function, diverse docstring styles...
    dsp_local = Dispatcher(description='First line\n\nOther\n  lines')
    assert getdocl('dispatcher', dsp_local, 'dsp_local') == ['First line', '', 'Other', '  lines']


@with_setup(setup_test)
def test_docstring_property_processing():
    def genarate_docstring(objtype, name, **kw):
        del processed_docstrings[:]
        del processed_signatures[:]
        inst = DispatcherDirective._registry[objtype](directive, name)
        inst.generate(**kw)
        results = list(directive.result)
        del directive.result[:]
        return results

    results = genarate_docstring('dispatcher', dsp.__module__ + '.dsp')
    assert '.. py:data:: dsp' in results
    assert '   :module: %s' % dsp.__module__ in results
    assert '   :annotation:  = Pippo' in results


@with_setup(setup_test)
def test_generate():

    def assert_result(items, objtype, name, **kw):
        inst = DispatcherDirective._registry[objtype](directive, name)
        inst.generate(**kw)
        assert len(_warnings) == 0, _warnings
        items = list(reversed(items))
        lineiter = iter(directive.result)
        #for line in directive.result:
        #    if line.strip():
        #        print repr(line)
        while items:
            item = items.pop()
            if item == next(lineiter):
                continue
            else:  # ran out of items!
                assert False, 'item %r not found in result or not in the ' \
                       ' correct order' % item
        del directive.result[:]

    # test auto and given content mixing
    directive.env.ref_context['py:module'] = dsp.__module__
    res = [
        '',
        '.. py:data:: dsp',
        '   :module: %s' % dsp.__module__,
        '   :annotation:  = Pippo',
        '',
        '   Docstring 1',
        '   ',
        '   good',
        '   ',
        '   .. graphviz::',
        '   ',
        '      %s' % dsp2dot(dsp).source,
        '   ',
        "   .. csv-table:: **Pippo's data**",
        '   ',
        '      :obj:`a <>`, Description of a',
        '      :obj:`sink <>`, ',
        '      :obj:`start <>`, ',
        '   ',
        "   .. csv-table:: **Pippo's functions**",
        '   ',
        '      :func:`fun1 <>`, Description of fun1',
        '      :func:`fun2 <%s.fun2>`, Description of fun2' % dsp.__module__,
        '      :func:`fun3 <%s.fun2>`, Description of fun3' % dsp.__module__,
        '   ']


    assert_result(res, 'dispatcher', 'dsp')
    res[1] = '.. py:data:: dsp_1'
    res[5] = '   Docstring 2'

    assert_result(res, 'dispatcher', 'dsp_1')

str = """
Incrociamo le dita

.. testsetup::
   >>> from dispatcher import Dispatcher
   >>> uff1 = Dispatcher(name='P', description='daiiiii')
   >>> def pazzo():
   ...     '''
   ...     vero
   ...     '''
   ...     pass
   >>> uff1.add_function(function=bella_ciao)
   >>> uff1.add_function(function=pazzo)
   >>> uff1.add_data('a')

.. autodispatcher:: uff1
   :opt: function_module=False
   :code:
   :func:

   >>> uff1

"""

def fun2():
    """
    Description of fun2

    error
    """
    return

#: Docstring 1
#:
#: good
dsp = Dispatcher(name='Pippo', description='Docstring 2\n\ngood')
dsp.add_data(data_id='a', description='Description of a\n\nerror')
dsp.add_function(function_id='fun1', description='Description of fun1\n\nerror')
dsp.add_function('fun2', fun2)
dsp.add_function('fun3', fun2, description='Description of fun3\n\nerror')


dsp_1 = dsp


"""
Incrociamo le dita

.. testsetup::
   >>> from dispatcher import Dispatcher
   >>> uff1 = Dispatcher(name='P', description='daiiiii')
   >>> def pazzo():
   ...     '''
   ...     vero
   ...     '''
   ...     pass
   >>> uff1.add_function(function=bella_ciao)
   >>> uff1.add_function(function=pazzo)
   >>> uff1.add_data('a')

.. autodispatcher:: uff1
   :opt: function_module=False
   :code:
   :func:

   >>> uff1
   <...>
"""


uff1 = Dispatcher(name='Pippo', description='caro amico ti scrivo 2')
uff1.add_data(data_id='a', description='ciao sono io')
uff1.add_function(function_id='fun', description='il sole è blu')


def bella_ciao(ciao={'fd':1, '4':3}, forse={'dd':2}):
    """
    bella ciao

    sono innamorato di te..
    """
    return


#: eh
#: questa è meglio
ASS = Dispatcher(name='ciao', description='caro amico ti scrivo')
ASS.add_data(data_id='a', description='ciao sono io')
ASS.add_function(function=bella_ciao)


class Piolo(object):
    """
    stupenda
    """
    def __init__(self):
        pass

#: cosa vuoi
CIAO = Piolo()