import logging
log = logging.getLogger(__name__)

import dill
from networkx.utils.decorators import open_file

__all__ = ['load_from_dill', 'save_dill']

@open_file(0, mode='rb')
def load_from_dill(fpath):
    """
    Load inputs from .dill file.

    :param fpath:
        File path.
    :type fpath: str

    :return:
        Input data.
    :rtype: dict
    """
    log.debug('Reading dill-file: %s', fpath)
    return dill.load(fpath)


@open_file(1, mode='wb')
def save_dill(data, fpath, *args, **kwargs):
    log.debug('Writing dill-file: %s', fpath)
    dill.dump(data, fpath)
