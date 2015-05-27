"""
.. module:: dispatcher

.. moduleauthor:: Vincenzo Arcidiacono <vinci1it2000@gmail.com>

"""

__author__ = 'Vincenzo Arcidiacono'

import logging
import networkx as nx
from heapq import heappush, heappop
from itertools import count
from collections import OrderedDict
from .utils import rename_function, AttrDict
from .graph_utils import add_edge_fun, remove_cycles_iteration
from .constants import EMPTY, START

log = logging.getLogger(__name__)

class Dispatcher(object):
    """
    It provides a data structure to process a complex system of functions.

    The scope of this data structure is to compute the shortest workflow between
    input and output data nodes.

    A workflow is a sequence of function calls.

    :param dmap:
        A directed graph that stores data & functions parameters.
    :type dmap: nx.DiGraph

    \***************************************************************************

    **Example**:

    As an example, here is a system of equations:

    :math:`b - a = c`

    :math:`log(c) = d_{from-log}`

    :math:`d = (d_{from-log} + d_{initial-guess}) / 2`

    that will be solved assuming that :math:`a = 0`, :math:`b = 1`, and
    :math:`d_{initial-guess} = 4`.

    **Steps**

    Create an empty dispatcher::

        >>> dsp = Dispatcher()

    Add data nodes to the dispatcher map::

        >>> dsp.add_data(data_id='/a')
        '/a'
        >>> dsp.add_data(data_id='/c')
        '/c'

    Add a data node with a default value to the dispatcher map::

        >>> dsp.add_data(data_id='/b', default_value=1)
        '/b'

    Create a function node::

        >>> def diff_function(a, b):
        ...     return b - a

        >>> dsp.add_function(function=diff_function, inputs=['/a', '/b'],
        ...                  outputs=['/c'])
        '...dispatcher:diff_function'

    Create a function node with domain::

        >>> from math import log

        >>> def log_domain(x):
        ...     return x > 0

        >>> dsp.add_function(function=log, inputs=['/c'], outputs=['/d'],
        ...                  input_domain=log_domain)
        'math:log'

    Create a data node with function estimation and callback function.

        - function estimation: estimate one unique output from multiple
          estimations.
        - callback function: is invoked after computing the output.

        >>> def average_fun(kwargs):
        ...     x = kwargs.values()
        ...     return sum(x) / len(x)

        >>> def callback_fun(x):
        ...     print('(log(1) + 4) / 2 = %.1f' % x)

        >>> dsp.add_data(data_id='/d', default_value=4, wait_inputs=True,
        ...              function=average_fun, callback=callback_fun)
        '/d'

    Dispatch the function calls to achieve the desired output data node '/d'::

        >>> workflow, outputs = dsp.dispatch(inputs={'/a': 0}, outputs=['/d'])
        (log(1) + 4) / 2 = 2.0
        >>> sorted(outputs.items())
        [('/a', 0), ('/b', 1), ('/c', 1), ('/d', 2.0)]
    """

    def __init__(self, dmap=None):
        self.dmap = dmap if dmap else nx.DiGraph()
        self.dmap.node = AttrDict(self.dmap.node)
        self.nodes = self.dmap.node
        self.default_values = {}
        self._workflow = nx.DiGraph()  # graph output
        self._data_output = {}
        self._dist = {}
        self._visited = set()
        self._targets = set()
        self._cutoff = None
        self._weight = 'weight'
        self._wildcards = set()
        self._pred = self.dmap.pred
        self._node = self.dmap.node
        self._succ = self.dmap.succ
        self._wf_add_edge = add_edge_fun(self._workflow)
        self._wf_pred = self._workflow.pred

    def add_data(self, data_id=None, default_value=EMPTY, wait_inputs=False,
                 wildcard=None, function=None, callback=None, **kwargs):
        """
        Add a single data node to the dispatcher map (dmap).

        :param data_id:
            Data node id. If None will be assigned the next 'int' not in dmap.
        :type data_id: any hashable Python object except None, optional

        :param default_value:
            Data node default value. This will be used as input if it is not
            specified as input_value in the ArciDispatch algorithm.
        :type default_value: object, optional

        :param wait_inputs:
            If True ArciDispatch algorithm stops on the node until it gets all
            input estimations.
        :type wait_inputs: bool, optional

        :param wildcard:
            If True, when the data node is used as input and target in the
            ArciDispatch algorithm, the input value will be used as input for
            the connected functions, but not as output.
        :type wildcard: bool, optional

        :param function:
            Data node estimation function (requires wait_inputs=True).
            This can be any function that takes only one dictionary
            (key=function node id, value=estimation of data node) as input and
            return one value that is the estimation of the data node.
        :type function: function, optional

        :param callback:
            Callback function to be called after node estimation.
            This can be any function that takes only one argument that is the
            data node estimation output. It does not return anything.
        :type callback: function, optional

        :param kwargs:
            Set additional node attributes using key=value.
        :type kwargs: keyword arguments, optional

        :return:
            Data node id.
        :rtype: object

        .. seealso:: add_function, load_dmap_from_lists

        .. note::
            A hashable object is one that can be used as a key in a Python
            dictionary. This includes strings, numbers, tuples of strings
            and numbers, etc.

            On many platforms hashable items also include mutable objects such
            as NetworkX Graphs, though one should be careful that the hash
            doesn't change on mutable objects.

        \***********************************************************************

        **Example**::

            >>> dmap = Dispatcher()

            # data to be estimated (i.e., result data node)
            >>> dmap.add_data(data_id='/a')
            '/a'

            # data with a default value (i.e., input data node)
            >>> dmap.add_data(data_id='/b', default_value=1)
            '/b'

            >>> def average_fun(*x):
            ...     return sum(x) / len(x)

            # data node that is estimated as the average of all function node
            # estimations
            >>> dmap.add_data('/c', wait_inputs=True, function=average_fun)
            '/c'

            # initial data that is estimated as the average of all estimations
            >>> dmap.add_data(data_id='/d', default_value=2, wait_inputs=True,
            ...               function=average_fun)
            '/d'

            # create an internal data and return the generated id
            >>> dmap.add_data()
            'unknown<0>'
        """

        # base data node attributes
        attr_dict = {'type': 'data', 'wait_inputs': wait_inputs}

        if function is not None:  # add function as node attribute
            attr_dict['function'] = function

        if callback is not None:  # add callback as node attribute
            attr_dict['callback'] = callback

        if wildcard is not None:  # add wildcard as node attribute
            attr_dict['wildcard'] = wildcard

        # additional attributes
        attr_dict.update(kwargs)

        has_node = self.dmap.has_node  # namespace shortcut for speed

        if data_id is None:  # search for a unused node id
            n = count(0).__next__  # counter
            data_id = 'unknown<%d>' % n()  # initial guess
            while has_node(data_id):  # check if node id is used
                data_id = 'unknown<%d>' % n()  # guess

        # check if the node id exists as function
        elif has_node(data_id) and self.dmap.node[data_id]['type'] != 'data':
            raise ValueError('Invalid data id: '
                             'override function {}'.format(data_id))

        if default_value != EMPTY:  # add default value
            self.default_values[data_id] = default_value

        elif data_id in self.default_values:  # remove default value
            self.default_values.pop(data_id)

        # add node to the dispatcher map
        self.dmap.add_node(data_id, attr_dict=attr_dict)

        # return data node id
        return data_id

    def add_function(self, function_id=None, function=None, inputs=None,
                     outputs=None, input_domain=None, weight=None,
                     weight_from=None, weight_to=None, **kwargs):
        """
        Add a single function node to dispatcher map.

        :param function_id:
            Function node id.
            If None will be assigned as <fun.__module__>:<fun.__name__>.
        :type function_id: any hashable Python object except None, optional

        :param function:
            Data node estimation function.
        :type function: function, optional

        :param inputs:
            Ordered arguments (i.e., data node ids) needed by the function.
        :type inputs: list, optional

        :param outputs:
            Ordered results (i.e., data node ids) returned by the function.
        :type outputs: list, optional

        :param input_domain:
            A function that checks if input values satisfy the function domain.
            This can be any function that takes the same inputs of the function
            and returns True if input values satisfy the domain, otherwise
            False. In this case the dispatch algorithm doesn't pass on the node.
        :type input_domain: function, optional

        :param weight:
            Node weight. It is a weight coefficient that is used by the dispatch
            algorithm to estimate the minimum workflow.
        :type weight: float, int, optional

        :param weight_from:
            Edge weights from data nodes to the function node.
            It is a dictionary (key=data node id) with the weight coefficients
            used by the dispatch algorithm to estimate the minimum workflow.
        :type weight_from: dict , optional

        :param weight_to:
            Edge weights from the function node to data nodes.
            It is a dictionary (key=data node id) with the weight coefficients
            used by the dispatch algorithm to estimate the minimum workflow.
        :type weight_to: dict, optional

        :param kwargs:
            Set additional node attributes using key=value.
        :type kwargs: keyword arguments, optional

        :return:
            Function node id.
        :rtype: object

        .. seealso:: add_node, load_dmap_from_lists

        \***********************************************************************

        **Example**::

            >>> dmap = Dispatcher()

            >>> def my_function(a, b):
            ...     c = a + b
            ...     d = a - b
            ...     return c, d

            >>> dmap.add_function(function=my_function, inputs=['/a', '/b'],
            ...                   outputs=['/c', '/d'])
            '...dispatcher:my_function'

            >>> from math import log
            >>> def my_log(a, b):
            ...     log(b - a)

            >>> def my_domain(a, b):
            ...     return a < b

            >>> dmap.add_function(function=my_log, inputs=['/a', '/b'],
            ...                   outputs=['/e'], input_domain=my_domain)
            '...dispatcher:my_log'
        """

        if inputs is None:  # set a dummy input
            inputs = [self.add_data(default_value=EMPTY)]
            if outputs is None:
                raise ValueError('Invalid input:'
                                 ' missing inputs and outputs attributes.')
        if outputs is None:  # set a dummy output
            outputs = [self.add_data()]

        # base function node attributes
        attr_dict = {'type': 'function',
                     'inputs': inputs,
                     'outputs': outputs,
                     'function': function,
                     'wait_inputs': True}

        if input_domain:  # add domain as node attribute
            attr_dict['input_domain'] = input_domain

        if function_id is None:  # set function name
            try:
                # noinspection PyUnresolvedReferences
                function_name = '%s:%s' % (function.__module__,
                                           function.__name__)
            except Exception as ex:
                raise ValueError('Invalid function name due to: {}'.format(ex))
        else:
            function_name = function_id

        fun_id = function_name  # initial function id guess

        n = count(0).__next__  # counter

        has_node = self.dmap.has_node  # namespace shortcut for speed

        while has_node(fun_id):  # search for a unused node id
            fun_id = '%s<%d>' % (function_name, n())  # guess

        if weight is not None:  # add weight as node attribute
            attr_dict['weight'] = weight

        # additional attributes
        attr_dict.update(kwargs)

        # add node to the dispatcher map
        self.dmap.add_node(fun_id, attr_dict=attr_dict)

        def add_edge(i, o, edge_weight, w):
            # Adds edge to the dispatcher map.

            if edge_weight is not None and w in edge_weight:
                self.dmap.add_edge(i, o, weight=edge_weight[w])  # weighted edge
            else:
                self.dmap.add_edge(i, o)  # normal edge

        for u in inputs:
            try:
                # check if the node id exists as data
                if self.dmap.node[u]['type'] != 'data':
                    self.dmap.remove_node(fun_id)
                    raise ValueError('Invalid input id:'
                                     ' {} is not a data node'.format(u))
            except KeyError:
                self.add_data(data_id=u)  # add data node

            add_edge(u, fun_id, weight_from, u)

        for v in outputs:
            try:
                # check if the node id exists as data
                if self.dmap.node[v]['type'] != 'data':
                    self.dmap.remove_node(fun_id)
                    raise ValueError('Invalid output id:'
                                     ' {} is not a data node'.format(v))
            except KeyError:
                self.add_data(data_id=v)  # add data node

            add_edge(fun_id, v, weight_to, v)

        # return function node id
        return fun_id

    def load_from_lists(self, data_list=None, fun_list=None):
        """
        Add multiple function and data nodes to dispatcher map.

        :param data_list:
            It is a list of data node kwargs to be loaded.
        :type data_list: list, optional

        :param fun_list:
            It is a list of function node kwargs to be loaded.
        :type fun_list: list, optional

        :returns:
            - Data node ids.
            - Function node ids.

        .. seealso:: add_node, add_function

        \***********************************************************************

        **Example**::

            >>> dmap = Dispatcher()
            >>> data_list = [
            ...     {'data_id': '/a'},
            ...     {'data_id': '/b'},
            ...     {'data_id': '/c'},
            ... ]

            >>> def f(a, b):
            ...     return a + b

            >>> fun_list = [
            ...     {'function': f, 'inputs': ['/a', '/b'], 'outputs': ['/c']},
            ...     {'function': f, 'inputs': ['/c', '/d'], 'outputs': ['/a']}
            ... ]
            >>> dmap.load_from_lists(data_list, fun_list)
            (['/a', '/b', '/c'], ['...dispatcher:f', '...dispatcher:f<0>'])
        """

        if data_list:  # add data nodes
            data_ids = [self.add_data(**v) for v in data_list]  # data ids
        else:
            data_ids = []

        if fun_list:  # add function nodes
            fun_ids = [self.add_function(**v) for v in fun_list]  # function ids
        else:
            fun_ids = []

        # return data and function node ids
        return data_ids, fun_ids

    def set_default_value(self, data_id, value=EMPTY):
        """
        Set the default value of a data node in the dispatcher map.

        :param data_id:
            Data node id.
        :type data_id: any hashable Python object except None

        :param value:
            Data node default value.
        :type value: object, optional

        \***********************************************************************

        **Example**::

            >>> dmap = Dispatcher()
            >>> dmap.add_data(data_id='/a')
            '/a'

            # add default value
            >>> dmap.set_default_value('/a', value='value of the data')
            >>> dmap.default_values
            {'/a': 'value of the data'}

            # remove default value
            >>> dmap.set_default_value('/a', value=EMPTY)
            >>> dmap.default_values
            {}
        """
        try:
            if self.dmap.node[data_id]['type'] == 'data':  # check if data node
                if value == EMPTY:
                    self.default_values.pop(data_id, None)  # remove default
                else:
                    self.default_values[data_id] = value  # add default
                return
            raise ValueError
        except:
            raise ValueError('Input error: %s is not a data node' % data_id)

    def get_sub_dmap(self, nodes_bunch, edges_bunch=None):
        """
        Returns the sub-dispatcher map induced by given node and edge bunches.

        The induced sub-dispatcher map of the dmap contains the available nodes
        in nodes_bunch and edges between those nodes, excluding those that are
        in edges_bunch.

        The available nodes are non isolated nodes and function nodes that have
        all inputs and at least one output.

        :param nodes_bunch:
            A container of node ids which will be iterated through once.
        :type nodes_bunch: list, iterable

        :param edges_bunch:
            A container of edge ids that will be removed.
        :type edges_bunch: list, iterable, optional

        :return:
            A sub-dispatcher map.
        :rtype: Dispatcher

        .. note::

            The sub-dispatcher map, edge or node attributes just point to the
            original dispatcher map. So changes to the node or edge structure
            will not be reflected in the original dispatcher map while changes
            to the attributes will.

        \***********************************************************************

        **Example**::

            >>> dmap = Dispatcher()
            >>> dmap.add_function(function_id='fun1', inputs=['/a', '/b'],
            ...                   outputs=['/c', '/d'])
            'fun1'
            >>> dmap.add_function(function_id='fun2', inputs=['/a', '/d'],
            ...                   outputs=['/c', '/e'])
            'fun2'
            >>> sub_dmap = dmap.get_sub_dmap(['/a', '/c', '/d', '/e', 'fun2'])
            >>> sorted(sub_dmap.dmap.node)
            ['/a', '/c', '/d', '/e', 'fun2']
            >>> res = {'/a': {'fun2': {}},
            ...        '/c': {},
            ...        '/d': {'fun2': {}},
            ...        '/e': {},
            ...        'fun2': {'/e': {}, '/c': {}}}
            >>> sub_dmap.dmap.edge ==  res
            True
        """

        # define an empty dispatcher map
        sub_dmap = self.__class__(dmap=self.dmap.subgraph(nodes_bunch))

        # namespace shortcuts for speed
        nodes = sub_dmap.dmap.node
        dmap_out_degree = sub_dmap.dmap.out_degree
        dmap_remove_node = sub_dmap.dmap.remove_node
        dmap_remove_edge = sub_dmap.dmap.remove_edge
        dmap_dv = self.default_values

        # remove function nodes that has not whole inputs available
        for u in nodes_bunch:
            n = nodes[u].get('inputs', None)  # function inputs
            # no all inputs
            if n is not None and not set(n).issubset(nodes_bunch):
                dmap_remove_node(u)  # remove function node

        # remove edges that are not in edges_bunch
        if edges_bunch is not None:
            # iterate sub-graph edges
            for e in edges_bunch:
                dmap_remove_edge(*e)  # remove edge

        # remove function node with no outputs
        for u in [u for u, n in sub_dmap.dmap.nodes_iter(True)
                  if n['type'] == 'function']:

            if not dmap_out_degree(u):  # no outputs
                dmap_remove_node(u)  # remove function node

        # remove isolate nodes from sub-graph
        sub_dmap.dmap.remove_nodes_from(nx.isolates(sub_dmap.dmap))

        # set default values
        sub_dmap.default_values = {k: dmap_dv[k] for k in dmap_dv if k in nodes}

        # return the sub-dispatcher map
        return sub_dmap

    def remove_cycles(self, sources):
        """
        Returns a new dispatcher map removing unresolved cycles.

        An unresolved cycle is a cycle that cannot be removed by the
        ArciDispatch algorithm.

        :param sources:
            Input data nodes.
        :type sources: iterable

        :return:
            A new dmap without the unresolved dmap cycles.
        :rtype: Dispatcher

        \***********************************************************************

        **Example**::

            >>> dsp = Dispatcher()
            >>> def average(kwargs):
            ...     return sum(kwargs.values()) / len(kwargs)
            >>> dsp.add_data(data_id='/b', default_value=3)
            '/b'
            >>> dsp.add_data(data_id='/c', wait_inputs=True, function=average)
            '/c'
            >>> dsp.add_function(function=max, inputs=['/a', '/b'],
            ...                  outputs=['/c'])
            'builtins:max'
            >>> dsp.add_function(function=min, inputs=['/a', '/c'],
            ...                  outputs=['/d'])
            'builtins:min'
            >>> dsp.add_function(function=min, inputs=['/b', '/d'],
            ...                  outputs=['/c'])
            'builtins:min<0>'
            >>> dsp.add_function(function=max, inputs=['/b', '/d'],
            ...                  outputs=['/a'])
            'builtins:max<0>'
            >>> res = dsp.dispatch(inputs={'/a': 1})[1]
            >>> sorted(res.items())
            [('/a', 1), ('/b', 3)]
            >>> dsp_rm_cycles = dsp.remove_cycles(['/a', '/b'])
            >>> dsp_rm_cycles.add_function(function=min, inputs=['/a', '/e'],
            ...                            outputs=['/f'])
            'builtins:min<0>'
            >>> res = dsp_rm_cycles.dispatch(inputs={'/a': 1, '/e': 0})[1]
            >>> sorted(res.items())
            [('/a', 1), ('/b', 3), ('/c', 3.0), ('/d', 1), ('/e', 0), ('/f', 0)]
        """

        # Reachable nodes from sources
        reached_nodes = set()

        # List of edges to be removed
        edge_to_remove = []

        # updates the reachable nodes and list of edges to be removed
        remove_cycles_iteration(self.dmap, iter(sources), reached_nodes,
                                edge_to_remove)

        for v in self.dmap.node.values():
            if v.pop('undo', False):
                v['wait_inputs'] = True

        # sub-dispatcher map induced by the reachable nodes
        new_dmap = self.get_sub_dmap(reached_nodes, edge_to_remove)

        # return a new dmap without the unresolved dmap cycles
        return new_dmap

    def get_sub_dsp_from_workflow(self, sources, graph=None, reverse=False):
        """
        Returns the sub-dispatcher induced by the workflow from sources.

        The induced sub-dispatcher of the dsp contains the reachable nodes and
        edges evaluated with breadth-first-search on the workflow graph from
        source nodes.

        :param sources:
            Source nodes for the breadth-first-search.
            A container of nodes which will be iterated through once.
        :type sources: iterable

        :param graph:
            A directed graph where evaluate the breadth-first-search.
        :type graph: nx.DiGraph

        :param reverse:
            If True the workflow graph is assumed as reversed.
        :type reverse: bool, optional

        :return:
            A sub-dispatcher
        :rtype: Dispatcher

        .. note::

            The sub-dispatcher map, edge or node attributes just point to the
            original dispatcher map. So changes to the node or edge structure
            will not be reflected in the original dispatcher map while changes
            to the attributes will.

        \***********************************************************************

        **Example**::

            >>> dsp = Dispatcher()
            >>> dsp.add_data(data_id='/a', default_value=1)
            '/a'
            >>> dsp.add_function(function_id='fun1', inputs=['/a', '/b'],
            ...                  outputs=['/c', '/d'])
            'fun1'

            >>> wf = dsp.dispatch(inputs=['/a', '/b'], empty_fun=True)[0]

            >>> sub_dsp = dsp.get_sub_dsp_from_workflow(['/a', '/b'])
            >>> sub_dsp.default_values
            {'/a': 1}
            >>> sorted(sub_dsp.dmap.node)
            ['/a', '/b', '/c', '/d', 'fun1']
            >>> res = {'/a': {'fun1': {}},
            ...        '/b': {'fun1': {}},
            ...        '/c': {},
            ...        '/d': {},
            ...        'fun1': {'/c': {}, '/d': {}}}
            >>> sub_dsp.dmap.edge ==  res
            True
            >>> sub_dsp = dsp.get_sub_dsp_from_workflow(['/c'], reverse=True)
            >>> sorted(sub_dsp.dmap.node)
            ['/a', '/b', '/c', 'fun1']
            >>> res = {'/a': {'fun1': {}},
            ...        '/b': {'fun1': {}},
            ...        '/c': {},
            ...        'fun1': {'/c': {}}}
            >>> sub_dsp.dmap.edge ==  res
            True
        """

        # define an empty dispatcher map
        sub_dsp = self.__class__()

        if not graph:  # set default graph
            graph = self._workflow

        if not reverse:
            # namespace shortcuts for speed
            neighbors = graph.neighbors_iter
            dmap_succ = self.dmap.succ
            succ, pred = (sub_dsp.dmap.succ, sub_dsp.dmap.pred)
        else:
            # namespace shortcuts for speed
            neighbors = graph.predecessors_iter
            dmap_succ = self.dmap.pred
            pred, succ = (sub_dsp.dmap.succ, sub_dsp.dmap.pred)

        # namespace shortcuts for speed
        nodes, dmap_nodes = (sub_dsp.dmap.node, self.dmap.node)
        dlt_val, dsp_dlt_val = (sub_dsp.default_values, self.default_values)

        # visited nodes used as queue
        family = OrderedDict()

        # function to set node attributes
        def set_node_attr(n):
            # set node attributes
            nodes[n] = dmap_nodes[n]

            # add node in the adjacency matrix
            succ[n], pred[n] = ({}, {})

            if n in dsp_dlt_val:
                dlt_val[n] = dsp_dlt_val[n]  # set the default value

            family[n] = neighbors(n)  # append a new parent to the family

        # set initial node attributes
        for s in sources:
            set_node_attr(s)

        # start breadth-first-search
        for parent, children in iter(family.items()):

            # namespace shortcuts for speed
            nbrs, dmap_nbrs = (succ[parent], dmap_succ[parent])

            # iterate parent's children
            for child in children:

                if child == START:
                    continue

                if child not in family:
                    set_node_attr(child)  # set node attributes

                # add attributes to both representations of edge: u-v and v-u
                nbrs[child] = pred[child][parent] = dmap_nbrs[child]

        # return the sub-dispatcher map
        return sub_dsp

    def dispatch(self, inputs=None, outputs=None, cutoff=None,
                 wildcard=False, empty_fun=False, shrink=False):
        """
        Evaluates the minimum workflow and data outputs of the dispatcher map
        model from given inputs.

        :param inputs:
            Input data values.
        :type inputs: dict, iterable, optional

        :param outputs:
            Ending data nodes.
        :type outputs: iterable, optional

        :param cutoff:
            Depth to stop the search.
        :type cutoff: float, int, optional

        :param wildcard:
            If True, when the data node is used as input and target in the
            ArciDispatch algorithm, the input value will be used as input for
            the connected functions, but not as output.
        :type wildcard: bool, optional

        :param empty_fun:
            If True data node estimation function is not used.
        :type empty_fun: bool, optional

        :param shrink:
            If True the dispatcher is shrink before the dispatch.
        :type shrink: bool, optional

        :return:
            - workflow: A directed graph with data node estimations.
            - data_output: Dictionary of estimated data node outputs.
        :rtype: (NetworkX DiGraph, dict)

        \***********************************************************************

        **Example**::

            >>> dsp = Dispatcher()
            >>> from math import log
            >>> dsp.add_data(data_id='/a', default_value=0)
            '/a'
            >>> dsp.add_data(data_id='/b', default_value=1)
            '/b'

            >>> def my_log(a, b):
            ...     return log(b - a)

            >>> def my_domain(a, b):
            ...     return a < b

            >>> dsp.add_function(function=my_log, inputs=['/a', '/b'],
            ...                  outputs=['/c'], input_domain=my_domain)
            '...dispatcher:my_log'
            >>> workflow, outputs = dsp.dispatch(outputs=['/c'])
            >>> sorted(outputs.items())
            [('/a', 0), ('/b', 1), ('/c', 0.0)]
            >>> sorted(workflow.nodes())
            ['/a', '/b', '/c', '...dispatcher:my_log', start]
            >>> sorted(workflow.edges())
            [('/a', '...dispatcher:my_log'), ('/b', '...dispatcher:my_log'),
             ('...dispatcher:my_log', '/c'), (start, '/a'), (start, '/b')]

            >>> workflow, outputs = dsp.dispatch(inputs={'/b': 0},
            ...                                  outputs=['/c'])
            >>> sorted(outputs.items())
            [('/a', 0), ('/b', 0)]
            >>> sorted(workflow.nodes())
            ['/a', '/b', '...dispatcher:my_log', start]
            >>> sorted(workflow.edges())
            [('/a', '...dispatcher:my_log'),
             ('/b', '...dispatcher:my_log'),
             (start, '/a'),
             (start, '/b')]
        """

        # pre shrink
        if not empty_fun and shrink:
            dsp = self.shrink_dsp(inputs, outputs, cutoff, wildcard)
        else:
            dsp = self

        # initialize
        args = dsp._init_run(inputs, outputs, wildcard, cutoff, empty_fun)

        # return the evaluated workflow graph and data outputs
        workflow, data_outputs = dsp._run(*args[1:])

        # nodes that are out of the dispatcher nodes
        out_dsp_nodes = set(args[0]).difference(dsp.nodes)

        # add nodes that are out of the dispatcher nodes
        data_outputs.update({k: inputs[k] for k in out_dsp_nodes})

        # return the evaluated workflow graph and data outputs
        return workflow, data_outputs

    # TODO: Extend minimum dmap when using function domains
    def shrink_dsp(self, inputs=None, outputs=None, cutoff=None,
                   wildcard=False):
        """
        Returns a reduced dispatcher built using the empty function workflow.

        :param inputs:
            Input data nodes.
        :type inputs: iterable, optional

        :param outputs:
            Ending data nodes.
        :type outputs: iterable, optional

        :param cutoff:
            Depth to stop the search.
        :type cutoff: float, int, optional

        :param wildcard:
            If True, when the data node is used as input and target in the
            ArciDispatch algorithm, the input value will be used as input for
            the connected functions, but not as output.
        :type wildcard: bool, optional

        :return:
            A sub-dispatcher.
        :rtype: Dispatcher

        \***********************************************************************

        **Example**::

            >>> dsp = Dispatcher()
            >>> dsp.add_function(function=max, inputs=['/a', '/b'],
            ...                  outputs=['/c'])
            'builtins:max'
            >>> dsp.add_function(function=max, inputs=['/b', '/d'],
            ...                  outputs=['/e'])
            'builtins:max<0>'
            >>> dsp.add_function(function=max, inputs=['/d', '/e'],
            ...                  outputs=['/c','/f'])
            'builtins:max<1>'
            >>> dsp.add_function(function=max, inputs=['/d', '/f'],
            ...                  outputs=['/g'])
            'builtins:max<2>'
            >>> dsp.add_function(function=max, inputs=['/a', '/b'],
            ...                  outputs=['/g'])
            'builtins:max<3>'

            >>> shrink_dsp = dsp.shrink_dsp(inputs=['/a', '/b', '/d'],
            ...                             outputs=['/c', '/e', '/f'])
            >>> sorted(shrink_dsp.dmap.nodes())
            ['/a', '/b', '/c', '/d', '/e', '/f',
             'builtins:max', 'builtins:max<0>', 'builtins:max<1>']
            >>> sorted(shrink_dsp.dmap.edges())
            [('/a', 'builtins:max'), ('/b', 'builtins:max'),
             ('/b', 'builtins:max<0>'), ('/d', 'builtins:max<0>'),
             ('/d', 'builtins:max<1>'), ('/e', 'builtins:max<1>'),
             ('builtins:max', '/c'), ('builtins:max<0>', '/e'),
             ('builtins:max<1>', '/f')]
        """
        if inputs:
            # evaluate the workflow graph without invoking functions
            workflow, data_visited = self.dispatch(inputs, outputs, cutoff,
                                                   wildcard, True)

            # remove the starting node from the workflow graph
            workflow.remove_node(START)

            # set the graph for the breadth-first-search
            bfs_graph = workflow

            # reached outputs
            outputs = set(outputs) & set(data_visited)

        elif outputs:
            # set the graph for the breadth-first-search
            bfs_graph = self.dmap

            # outputs in the dispatcher
            outputs = set(outputs) & set(self.dmap.node)
        else:
            return self.__class__()  # return an empty dispatcher

        # return the sub dispatcher
        return self.get_sub_dsp_from_workflow(outputs, bfs_graph, True)

    def extract_function_node(self, function_id, inputs, outputs, cutoff=None):
        """
        Returns a function node that uses the dispatcher map as function.

        :param function_id:
            Function node id.
            If None will be assigned as <fun.__module__>:<fun.__name__>.
        :type function_id: any hashable Python object except None

        :param inputs:
            Input data nodes.
        :type inputs: iterable

        :param outputs:
            Ending data nodes.
        :type outputs: iterable

        :param cutoff:
            Depth to stop the search.
        :type cutoff: float, int, optional

        :return:
            Function attributes.
        :rtype: dict

        \***********************************************************************

        **Example**::

            >>> dsp = Dispatcher()
            >>> dsp.add_function(function=max, inputs=['/a', '/b'],
            ...                  outputs=['/c'])
            'builtins:max'
            >>> dsp.add_function(function=min, inputs=['/c', '/b'],
            ...                  outputs=['/a'],
            ...                  input_domain=lambda c, b: c * b > 0)
            'builtins:min'
            >>> res = dsp.extract_function_node('myF', ['/a', '/b'], ['/a'])
            >>> res['inputs'] == ['/a', '/b']
            True
            >>> res['outputs'] == ['/a']
            True
            >>> res['function'].__name__
            'myF'
            >>> res['function'](2, 1)
            1
        """

        # new shrink dispatcher
        dsp = self.shrink_dsp(inputs, outputs, cutoff, True)

        # outputs not reached
        missed = set(outputs).difference(dsp.nodes)

        if missed:  # if outputs are missing raise error
            raise ValueError('Unreachable output-targets:{}'.format(missed))

        # get initial default values
        input_values = dsp._get_initial_values(None, False)

        # set wildcards
        dsp._set_wildcards(inputs, outputs)

        # define the function to populate the workflow
        def input_value(k):
            return {'value': input_values[k]}

        # define the function to return outputs sorted
        if len(outputs) > 1:
            def return_output(o):
                return [o[k] for k in outputs]
        else:
            def return_output(o):
                return o[outputs[0]]

        # define function
        @rename_function(function_id)
        def dsp_fun(*args):
            # update inputs
            input_values.update(dict(zip(inputs, args)))

            # dispatch outputs
            o = dsp._run(*dsp._init_workflow(input_values, input_value))[1]

            try:
                # return outputs sorted
                return return_output(o)

            except KeyError:  # unreached outputs
                # raise error
                raise ValueError('Unreachable output-targets:'
                                 '{}'.format(set(outputs).difference(o)))

        # return function attributes
        return {'function': dsp_fun, 'inputs': inputs, 'outputs': outputs}

    def _check_targets(self):
        """
        Returns a function to terminate the ArciDispatch algorithm when all
        targets have been visited.

        :return:
            A function to terminate the ArciDispatch algorithm.
        :rtype: function
        """

        if self._targets:

            targets = self._targets

            def check_targets(node_id):
                """
                Terminates ArciDispatch algorithm when all targets have been
                visited.

                :param node_id:
                    Data or function node id.
                :type node_id: any hashable Python object except None

                :return:
                    True if all targets have been visited, otherwise False
                :rtype: bool
                """
                try:
                    targets.remove(node_id)  # remove visited node
                    return not targets  # if no targets terminate the algorithm
                except KeyError:  # the node is not in the targets set
                    return False
        else:
            def check_targets(node_id):
                return False

        return check_targets

    def _check_cutoff(self):
        """
        Returns a function to stop the search of the investigated node of the
        ArciDispatch algorithm.

        :return:
            A function to stop the search
        :rtype: function
        """

        if self._cutoff is not None:

            cutoff = self._cutoff

            def check_cutoff(distance):
                """
                Stops the search of the investigated node of the ArciDispatch
                algorithm.

                :param distance:
                    Distance from the starting node.
                :type distance: float, int

                :return:
                    True if distance > cutoff, otherwise False
                :rtype: bool
                """
                return distance > cutoff  # check cutoff distance

        else:  # cutoff is None.
            def check_cutoff(distance):
                return False

        return check_cutoff

    def _edge_length(self, edge, node_out):
        """
        Returns the edge length.

        The edge length is edge weight + destination node weight.

        :param edge:
            Edge attributes.
        :type edge: dict

        :param node_out:
            Node attributes.
        :type node_out: dict

        :return:
            Edge length.
        :rtype: float, int
        """

        weight = self._weight

        return edge.get(weight, 1) + node_out.get(weight, 0)

    def _check_wait_input_flag(self, wait_in, node_id):
        """
        Stops the search of the investigated node of the ArciDispatch algorithm,
        until all inputs are satisfied.

        :param wait_in:
            If True the node is waiting input estimations.
        :type wait_in: bool

        :param node_id:
            Data or function node id.
        :type node_id: any hashable Python object except None

        :return:
            True if all node inputs are satisfied, otherwise False
        :rtype: bool
        """

        # return true if the node is waiting inputs and inputs are satisfied
        return wait_in and (self._pred[node_id].keys() - self._visited)

    def _set_wildcards(self, inputs=None, output_targets=None):
        """
        Update wildcards set with the input data nodes that are also outputs.

        :param inputs:
            Input data nodes.
        :type inputs: iterable

        :param output_targets:
            Ending data nodes.
        :type output_targets: iterable
        """

        self._wildcards.clear()

        if output_targets:
            node = self._node

            # input data nodes that are in output_targets
            wildcards = {u: node[u] for u in inputs if u in output_targets}

            # data nodes without the wildcard
            self._wildcards.update([k
                                    for k, v in wildcards.items()
                                    if v.get('wildcard', True)])

    def _get_initial_values(self, input_values, empty_function):
        """
        Returns inputs' initial values for the ArciDispatcher algorithm.

        Initial values are the default values merged with the input values.

        :param input_values:
            Input data nodes values.
        :type input_values: iterable, None

        :param empty_function:
            If True data node value is not None.
        :type empty_function: bool

        :return:
            Inputs' initial values.
        :rtype: dict
        """

        if empty_function:
            # set initial values
            initial_values = dict.fromkeys(self.default_values, None)

            # update initial values with input values
            if input_values is not None:
                initial_values.update(dict.fromkeys(input_values, None))
        else:
            # set initial values
            initial_values = self.default_values.copy()

            # update initial values with input values
            if input_values is not None:
                initial_values.update(input_values)

        return initial_values

    def _init_workflow(self, inputs, input_value):
        """
        Initializes workflow, visited nodes, data output, and distance.

        :param inputs:
            Input data nodes.
        :type inputs: iterable

        :param input_value:
            A function that return the input value of a given data node.
            If input_values = {'/a': 'value'} then 'value' == input_value('/a')
        :type input_value: function

        :return:
            - fringe: Nodes not visited, but seen.
            - seen: Distance to seen nodes.
        """

        # namespace shortcuts for speed
        node_attr = self._node
        graph = self.dmap
        add_visited = self._visited.add
        edge_weight = self._edge_length
        check_cutoff = self._check_cutoff()
        check_wait_in = self._check_wait_input_flag
        wf_add_edge = self._wf_add_edge
        wf_add_node = self._workflow.add_node
        wildcards = self._wildcards

        self._workflow.clear()

        self._data_output.clear()  # estimated data node output

        self._visited.clear()

        add_visited(START)  # nodes visited by the algorithm

        # dicts of distances
        self._dist, seen = ({START: -1}, {START: -1})

        # use heapq with (distance, wait, label)
        fringe = []

        # add the starting node to the workflow graph
        wf_add_node(START, type='start')

        # add initial values to fringe and seen
        for v in inputs:

            if v not in node_attr:
                continue

            wait_in = node_attr[v]['wait_inputs']  # store wait inputs flag

            # input value
            value = input_value(v)

            if v in wildcards:  # check if the data node is in wildcards

                # update visited nodes
                add_visited(v)

                # add node to workflow
                wf_add_node(v)

                for w, edge_data in graph[v].items():  # see function data node
                    # set workflow
                    wf_add_edge(v, w, **value)

                    # evaluate distance
                    vw_dist = edge_weight(edge_data, node_attr[w])

                    # check the cutoff limit and if all inputs are satisfied
                    if check_cutoff(vw_dist) or check_wait_in(True, w):
                        continue  # pass the node

                    # update distance
                    seen[w] = vw_dist

                    # add node to heapq
                    heappush(fringe, (vw_dist, True, w))

                continue

            # add edge
            wf_add_edge(START, v, **value)

            # check if all node inputs are satisfied
            if not check_wait_in(wait_in, v):
                # update distance
                seen[v] = 0

                # add node to heapq
                heappush(fringe, (0, wait_in, v))

        return fringe, seen

    def _set_node_output(self, node_id, empty_fun):
        """
        Set the node outputs from node inputs.

        :param node_id:
            Data or function node id.
        :type node_id: any hashable Python object except None

        :param empty_fun:
            If True data node estimation function is not used.
        :type empty_fun: bool

        :return status:
            If the output have been evaluated correctly.
        :rtype: bool

        \***********************************************************************

        **Example**::

            >>> dsp = Dispatcher()
            >>> dsp.add_data('/a', default_value=[1, 2])
            '/a'
            >>> fun_id = dsp.add_function(function=max, inputs=['/a'],
            ...                           outputs=['/b'])
            >>> dsp._workflow.add_node(START, attr_dict={'type': 'start'})
            >>> dsp._workflow.add_edge(START, '/a', attr_dict={'value': [1, 2]})
            >>> dsp._set_node_output('/a', False)
            True

            >>> dsp._set_node_output(fun_id, False)
            True
            >>> dsp._set_node_output('/b', False)
            True
            >>> sorted(dsp._data_output.items())
            [('/a', [1, 2]),
             ('/b', 2)]
            >>> sorted(dsp._workflow.edge.items())
            [('/a', {'builtins:max': {'value': [1, 2]}}),
             ('/b', {}),
             ('builtins:max', {'/b': {'value': 2}}),
             (start, {'/a': {'value': [1, 2]}})]
        """

        node_attr = self._node[node_id]

        node_type = node_attr['type']

        if node_type == 'data':
            return self._set_data_node_output(node_id, node_attr, empty_fun)
        elif node_type == 'function':
            return self._set_function_node_output(node_id, node_attr, empty_fun)

    def _set_data_node_output(self, node_id, node_attr, empty_fun):
        """
        Set the data node output from node estimations.

        :param node_id:
            Data node id.
        :type node_id: any hashable Python object except None

        :param node_attr:
            Dictionary of node attributes.
        :type node_attr: dict

        :param empty_fun:
            If True data node estimations are not used.
        :type empty_fun: bool

        :return status:
            If the output have been evaluated correctly.
        :rtype: bool
        """

        # get data node estimations
        estimations = self._wf_pred[node_id]

        if not empty_fun:

            # final estimation of the node and node status
            if not node_attr['wait_inputs']:

                # data node that has just one estimation value
                value = list(estimations.values())[0]['value']

            else:  # use the estimation function of node
                try:
                    # dict of all data node estimations
                    kwargs = {k: v['value'] for k, v in estimations.items()}

                    # noinspection PyCallingNonCallable
                    value = node_attr['function'](kwargs)  # evaluate output
                except Exception as ex:
                    # is missing estimation function of data node
                    msg = 'Estimation error at data node ({}) ' \
                          'due to: {}'.format(node_id, ex)
                    log.warning(msg, exc_info=1)  # raise a Warning
                    return False

            if 'callback' in node_attr:  # invoke callback function of data node
                # noinspection PyCallingNonCallable
                node_attr['callback'](value)

            # set data output
            self._data_output[node_id] = value

            # output value
            value = {'value': value}
            log.info('Estimated data node: %s' % node_id)
        else:
            # set data output
            self._data_output[node_id] = None

            # output value
            value = {}

        # list of functions
        succ_fun = [u for u in self._succ[node_id]]

        # check if it has functions as outputs and wildcard condition
        if succ_fun and succ_fun[0] not in self._visited:
            # namespace shortcuts for speed
            wf_add_edge = self._wf_add_edge

            # set workflow
            for u in succ_fun:
                wf_add_edge(node_id, u, **value)

        # return True, i.e. that the output have been evaluated correctly
        return True

    def _set_function_node_output(self, node_id, node_attr, empty_fun):
        """
        Set the function node output from node inputs.

        :param node_id:
            Function node id.
        :type node_id: any hashable Python object except None

        :param node_attr:
            Dictionary of node attributes.
        :type node_attr: dict

        :param empty_fun:
            If True data node estimation function is not used.
        :type empty_fun: bool

        :return status:
            If the output have been evaluated correctly.
        :rtype: bool
        """

        # list of nodes that can still be estimated by the function node
        output_nodes = [u for u in node_attr['outputs']
                        if (not u in self._dist) and (u in self._node)]

        if not output_nodes:  # this function is not needed
            self._workflow.remove_node(node_id)  # remove function node
            return False

        # namespace shortcuts for speed
        wf_add_edge = self._wf_add_edge

        if empty_fun:
            # set workflow out
            for u in output_nodes:
                wf_add_edge(node_id, u)
            return True

        args = self._wf_pred[node_id]  # list of the function's arguments
        args = [args[k]['value'] for k in node_attr['inputs']]
        try:
            # noinspection PyCallingNonCallable
            if 'input_domain' in node_attr and \
                    not node_attr['input_domain'](*args):
                # args are not respecting the domain
                return False
            else:  # use the estimation function of node
                log.info('Function call: %s' % node_id)
                # noinspection PyCallingNonCallable
                res = node_attr['function'](*args)
                # list of function results
                res = res if len(node_attr['outputs']) > 1 else [res]
        except Exception as ex:
            # is missing function of the node or args are not in the domain
            msg = 'Estimation error at function node ({}) ' \
                  'due to: {}'.format(node_id, ex)
            log.warning(msg, exc_info=1)  # raise a Warning
            return False

        # set workflow
        for k, v in zip(node_attr['outputs'], res):
            if k in output_nodes:
                wf_add_edge(node_id, k, value=v)

        # return True, i.e. that the output have been evaluated correctly
        return True

    def _init_run(self, input_values, output_targets, wildcard, cutoff,
                  empty_fun):
        """
        Initializes workflow, visited nodes, data output, and distance.

        :param input_values:
            Input data values.
        :type input_values: dict

        :param output_targets:
            Ending data nodes.
        :type output_targets: iterable

        :param wildcard:
            If True, when the data node is used as input and target in the
            ArciDispatch algorithm, the input value will be used as input for
            the connected functions, but not as output.
        :type wildcard: bool, optional

        :param cutoff:
            Depth to stop the search.
        :type cutoff: float, int

        :param empty_fun:
            If True data node estimation function is not used.
        :type empty_fun: bool

        :return:
            Inputs for _run:
                - fringe: Nodes not visited, but seen.
                - seen: Distance to seen nodes.
                - empty_fun.
        """

        # get inputs
        input_values = self._get_initial_values(input_values, empty_fun)

        # clear old targets
        self._targets.clear()

        # update new targets
        if output_targets is not None:
            self._targets.update(output_targets)

        if cutoff is not None:
            self._cutoff = cutoff  # set cutoff parameter
        else:
            self._cutoff = None  # clear cutoff parameter

        if wildcard:
            self._set_wildcards(input_values, output_targets)  # set wildcards
        else:
            self._set_wildcards()  # clear wildcards

        # define f function that return the input value of a given data node
        if empty_fun:
            def input_value(*k):
                return {}
        else:
            def input_value(k):
                return {'value': input_values[k]}

        # initialize workflow params
        fringe, seen = self._init_workflow(input_values, input_value)

        # return inputs for _run
        return input_values, fringe, seen, empty_fun

    def _run(self, fringe, seen, empty_fun=False):
        """
        Evaluates the minimum workflow and data outputs of the dispatcher map.

        Uses a modified (ArciDispatch) Dijkstra's algorithm for evaluating the
        workflow.

        :param empty_fun:
            If True data node estimation function is not used.
        :type empty_fun: bool, optional

        :return:
            - workflow: A directed graph with data node estimations.
            - data_output: Dictionary of estimated data node outputs.
        :rtype: (NetworkX DiGraph, dict)
        """

        # namespace shortcuts for speed
        node_attr = self._node
        graph = self.dmap
        dist = self._dist
        add_visited = self._visited.add
        set_node_output = self._set_node_output
        check_targets = self._check_targets()
        edge_weight = self._edge_length
        check_cutoff = self._check_cutoff()
        check_wait_in = self._check_wait_input_flag

        while fringe:
            (d, _, v) = heappop(fringe)  # visit the closest available node

            # set minimum distance
            dist[v] = d

            # update visited nodes
            add_visited(v)

            # set node output
            if not set_node_output(v, empty_fun):
                # some error occurs or inputs are not in the function domain
                continue

            # check wildcard option and if the targets are satisfied
            if check_targets(v):
                break  # stop loop

            for w, e_data in graph[v].items():
                node = node_attr[w]  # get node attributes

                vw_d = d + edge_weight(e_data, node)  # evaluate distance

                wait_in = node['wait_inputs']  # store wait inputs flag

                # check the cutoff limit and if all node inputs are satisfied
                if check_cutoff(vw_d) or check_wait_in(wait_in, w):
                    continue  # pass the node

                if w in dist:  # the node w already estimated
                    if vw_d < dist[w]:  # error for negative paths
                        raise ValueError('Contradictory paths found: '
                                         'negative weights?')
                elif w not in seen or vw_d < seen[w]:  # check min distance to w
                    # update distance
                    seen[w] = vw_d

                    # add node to heapq
                    heappush(fringe, (vw_d, wait_in, w))

        # remove unused functions
        for n in (set(self._wf_pred) - set(self._visited)):
            self._workflow.remove_node(n)

        # return the workflow and data outputs
        return self._workflow, self._data_output
