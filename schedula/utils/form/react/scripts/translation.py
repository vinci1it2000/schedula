import functools
import glob
import json
import os
import tqdm
import polib
import inspect
import subprocess
import flask_security
import os.path as osp
import schedula as sh
from datetime import datetime
import translators as ts

data = {'en_US', 'it_IT'}
for fpath in glob.glob(osp.join(
        osp.dirname(inspect.getfile(flask_security)), 'translations', '*'
)):
    if osp.isdir(fpath):
        data.add(osp.basename(fpath))
data = {lng: json.loads(subprocess.check_output([
    'node', '--es-module-specifier-resolution=node', './scripts/translate.js',
    {'zh_Hans_CN': 'zh_CN'}.get(lng, lng)
])) for lng in data}

cdir = osp.dirname(__file__)

data = {i: {
    '.'.join(k): v for k, v in sh.stack_nested_keys(d)
} for i, d in data.items()}
pot_fpath = osp.abspath(osp.join(cdir, '..', '..', 'server', 'locale', 'translations', 'antd.pot'))
if osp.isfile(pot_fpath):
    pot = polib.pofile(pot_fpath)
else:
    pot = polib.POFile()
    pot.metadata = {
        'Project-Id-Version': '1.0',
        'Report-Msgid-Bugs-To': 'vinci1it2000@gmail.com',
        'Last-Translator': 'Vincenzo Arcidiacono <vinci1it2000@gmail.com>',
        'Language-Team': 'English <vinci1it2000@gmail.com>',
        'MIME-Version': '1.0',
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Transfer-Encoding': '8bit',
    }
for k in functools.reduce(set.union, map(set, data.values()), set()):
    entry = pot.find(k)
    if not entry:
        pot.append(polib.POEntry(msgid=k))

os.makedirs(osp.dirname(pot_fpath), exist_ok=True)
pot.save(pot_fpath)


def _compile_po(lang, d, default=None):
    po_fpath = osp.abspath(osp.join(
        cdir, '..', '..', 'server', 'locale', 'translations', lang, 'LC_MESSAGES', 'antd.po'
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
    for k, v in d.items():
        if isinstance(v, bool):
            v = v and '§true' or '§false'
        elif isinstance(v, list):
            v = '","'.join(v)
            v = f'§["{v}"]'
            eval(v[1:])
        elif v is None:
            v = f"§undefined"
        entry = po.find(k)
        if entry:
            entry.msgstr = v
            if 'default' == entry.tcomment:
                entry.tcomment = None
        else:
            po.append(polib.POEntry(msgid=k, msgstr=v))
    cache = {}

    def t(text):
        if text not in cache:
            cache[text] = ts.translate_text(
                text, to_language=lang[:2], from_language='en'
                # , translator='alibaba'
            )
        return cache[text]

    for entry in tqdm.tqdm(po):
        if 'default' == entry.tcomment and entry.msgstr not in (
                '§true', '§false', '§undefined'):
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
            except:
                print('skip', entry.msgstr)
                pass

    os.makedirs(osp.dirname(po_fpath), exist_ok=True)
    po.save(po_fpath)
    return po


default_po = _compile_po('en_US', data['en_US'], pot)
for lang, d in sorted(data.items()):
    print(lang)
    _compile_po(lang, d, default_po)
