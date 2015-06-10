__author__ = 'Vincenzo Arcidiacono'

from dispatcher.utils import Token

__all__ = ['EMPTY', 'START', 'NONE', 'SINK']


#: Empty value.
EMPTY = Token('empty')

#: Starting node for the workflow.
START = Token('start')

#: None value.
NONE = Token('none')

#: Sink node of the dispatcher map.
SINK = Token('sink')