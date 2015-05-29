__author__ = 'Vincenzo Arcidiacono'

from .utils import Token

#: Empty value.
EMPTY = Token('empty')

#: Starting node for the workflow.
START = Token('start')

#: None value.
NONE = Token('none')

#: Sink node of the dispatcher map.
SINK = Token('sink')