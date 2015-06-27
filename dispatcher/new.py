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

"""
__author__ = 'arcidvi'

from dispatcher import Dispatcher


uff1 = Dispatcher(name='Pippo', description='caro amico ti scrivo 2')
uff1.add_data(data_id='a', description='ciao sono io')
uff1.add_function(function_id='fun', description='il sole è blu')


def bella_ciao(ciao={'fd':1, '4':3}, forse={'dd':2}):
    """
    bella ciao

    sono innamorato di te..
    """
    return


#: ehi
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