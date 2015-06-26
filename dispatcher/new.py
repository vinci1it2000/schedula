"""
Incrociamo le dita

.. autodispatcher:: dsp3

   >>> from dispatcher import Dispatcher
   >>> dsp3 = Dispatcher(name='P', description='daiiiii')
   >>> dsp3.add_data('a')

"""
__author__ = 'arcidvi'

from dispatcher import Dispatcher


uff = Dispatcher(name='Pippo', description='caro amico ti scrivo')
uff.add_data(data_id='a', description='ciao sono io')
uff.add_function(function_id='che bello è il mondo', description='il sole è blu')

ASS = Dispatcher(name='ciao', description='caro amico ti scrivo')
ASS.add_data(data_id='a', description='ciao sono io')
ASS.add_function(function_id='che bello è il mondo', description='il sole è blu')


class Piolo(object):
    """
    stupenda
    """
    def __init__(self):
        pass