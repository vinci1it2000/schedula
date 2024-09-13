import glob
import os
import tqdm
import polib
import inspect
import subprocess
import flask_security
import os.path as osp
from datetime import datetime
import translators as ts


def _compile_po(folder, lang, default=None):
    po_fpath = osp.abspath(osp.join(
        cdir, '..', 'locale', 'translations', lang,
        'LC_MESSAGES', f'{folder}.po'
    ))
    if osp.isfile(po_fpath):
        po = polib.pofile(po_fpath)
    else:
        po = polib.POFile()
        po.metadata = {
            'Project-Id-Version': '1.0',
            'Report-Msgid-Bugs-To': 'vinci1it2000@gmail.com',
            'Last-Translator': 'Vincenzo Arcidiacono <vinci1it2000@gmail.com>',
            'Language-Team': 'English <vinci1it2000@gmail.com>',
            'MIME-Version': '1.0',
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Transfer-Encoding': '8bit',
        }
    if default is not None:
        for entry in default:
            if not po.find(entry.msgid):
                entry = polib.POEntry(
                    msgid=entry.msgid, msgstr=entry.msgstr, tcomment='default'
                )
                po.append(entry)

    po.metadata['PO-Revision-Date'] = datetime.utcnow().strftime(
        '%Y-%m-%d %H:%M+0000'
    )
    cache = {}

    def t(text):
        if text not in cache:
            to_language = lang[:2]
            from_language = 'auto'
            if from_language == to_language:
                cache[text] = text
            else:
                cache[text] = ts.translate_text(
                    text, to_language=to_language, from_language=from_language,
                    translator='alibaba' if to_language == 'zn' else 'bing'
                )
        return cache[text]

    for entry in tqdm.tqdm(po):
        if not default.find(entry.msgid):
            po.remove(entry)
        if 'default' == entry.tcomment and entry.msgstr not in (
                '§true', '§false', '§undefined'
        ):
            try:
                if entry.msgstr.startswith('§'):
                    v = [i and t(i) or i for i in eval(entry.msgstr[1:])]
                    v = '","'.join(v)
                    v = f'§["{v}"]'
                    eval(v[1:])
                elif entry.msgstr:
                    v = t(entry.msgstr)
                entry.msgstr = v
                entry.tcomment = 'traslated'
            except Exception as ex:
                print('skip', entry.msgstr)
                pass

    os.makedirs(osp.dirname(po_fpath), exist_ok=True)
    po.save(po_fpath)
    return po


languages = {'en_US'}
for fpath in glob.glob(osp.join(
        osp.dirname(inspect.getfile(flask_security)), 'translations', '*'
)):
    if osp.isdir(fpath):
        languages.add(osp.basename(fpath))

cdir = osp.dirname(__file__)
for folder in ('credits', 'contact'):
    subprocess.check_call([
        'pybabel', 'extract', '-F', './babel.cfg', '-k', 'lazy_gettext',
        '-o', f'../locale/translations/{folder}.pot', f'../{folder}.py'
    ], cwd=cdir)
    pot_fpath = osp.abspath(osp.join(
        cdir, '..', 'locale', 'translations', f'{folder}.pot'
    ))
    pot = polib.pofile(pot_fpath)
    for entry in pot:
        entry.msgstr = entry.msgid
    default_po = _compile_po(folder, 'en_US', pot)

    for lang in sorted(languages):
        print(lang)
        _compile_po(folder, lang, default_po)
    subprocess.check_call([
        'pybabel', 'compile', '-d', f'../locale/translations', '-D', folder
    ], cwd=cdir)

subprocess.check_call([
    'pybabel', 'compile', '-d', f'../security/translations', '-D', folder
], cwd=cdir)
