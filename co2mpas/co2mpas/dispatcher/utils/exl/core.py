from pycel.excelcompiler import *
import re

__all__ = ['extract_dsp_from_excel']

_re_indirect = re.compile(
    r"""(INDIRECT\([^"\(\)]*"([^"\(\)]*)"[^"\(\)]*\))""",
    re.IGNORECASE | re.X | re.DOTALL
)

_re_sheet = re.compile('(([^!]*)!)?(.*)')


def get_named_range(formula):
    return dict(m.groups()[::-1] for m in _re_indirect.finditer(formula))


def find_nr(excel, name, scope):
    for n in excel.workbook.defined_names.definedName:
        if n.name.upper() == name.upper() and n.localSheetId == scope:
            return n


def convert_formula(excel, formula):
    defined_names, wb = excel.workbook.defined_names.definedName, excel.workbook
    for k, v in get_named_range(formula).items():
        try:
            sn, k = _re_sheet.match(k).groups()[1:]
            sn = (wb.get_index(wb[sn]), None) if sn else (None,)
            nr = next((nr for nr in (find_nr(excel, k, s) for s in sn) if nr))
            rng = nr.value
            sh, start, end = split_range(rng)
            if start == end:
                rng = '%s!%s' % (sh, start)
            formula = formula.replace(v, rng)
        except Exception:
            continue
    return formula


def get_seeds(excel, sheets=None):
    get_range = excel.get_range
    if sheets:
        sheets = [excel.workbook[sn] for sn in sheets]
    else:
        sheets = excel.workbook.worksheets

    for ws in sheets:
        for row in ws.iter_rows():
            for cell in row:
                address = '%s!%s' % (cell.parent.title, cell.coordinate)
                formula = get_range(address).Formula
                if formula.startswith('='):
                    cell.value = convert_formula(excel, formula)
                    yield address, (cell, formula)


def get_range(rng, map_inputs, *args):
    cells, nrows, ncols = rng.celladdrs, rng.nrows, rng.ncols
    ind = map_inputs.index
    if nrows == 1 or ncols == 1:
        data = [args[ind(c)] for c in cells]
    else:
        data = [[args[ind(c)] for c in cells[i]] for i in range(len(cells))]

    return data


def evaluate_cell(cell, map_inputs, *args):
    ind = map_inputs.index

    def eval_cell(address):
        return args[ind(address)]
    eval_range = eval_cell

    try:
        return eval(cell.compiled_expression)
    except Exception as e:
        raise Exception("Problem evalling: %s for %s, %s" % (
        e, cell.address(), cell.python_expression))
