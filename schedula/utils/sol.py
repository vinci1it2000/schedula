#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides a solution class for dispatch result.
"""
import time
import logging
import collections
from .base import Base
from .imp import finalize, Future
from .cst import START, NONE, PLOT
from heapq import heappop, heappush
from .dsp import stlp, get_nested_dicts, inf
from .alg import get_full_pipe, _sort_sk_wait_in
from .exc import DispatcherError, DispatcherAbort, SkipNode, ExecutorShutdown
from .asy import async_thread, await_result, async_process, AsyncList, EXECUTORS

log = logging.getLogger(__name__)


# noinspection PyTypeChecker
class Solution(Base, collections.OrderedDict):
    """Solution class for dispatch result."""

    def __hash__(self):
        return id(self)

    def __init__(self, dsp=None, inputs=None, outputs=None, wildcard=False,
                 cutoff=None, inputs_dist=None, no_call=False,
                 rm_unused_nds=False, wait_in=None, no_domain=False,
                 _empty=False, index=(-1,), full_name=(), verbose=False,
                 excluded_defaults=()):
        super(Solution, self).__init__()
        self.index = index
        self.rm_unused_nds = rm_unused_nds
        self.no_call = no_call
        self.no_domain = no_domain
        self.cutoff = cutoff
        self._wait_in = wait_in or {}
        self.outputs = set(outputs or ())
        self.full_name = full_name
        self._pipe = []
        self.parent = dsp
        self.verbose = verbose

        finalize(self, EXECUTORS.pop_active, id(self))
        from ..dispatcher import Dispatcher
        self._set_dsp_features(dsp or Dispatcher())

        if not _empty:
            self._set_inputs(inputs, inputs_dist, excluded_defaults)

            # Set wildcards.
            self._set_wildcards(*((inputs, outputs) if wildcard else ()))

            # Initialize workflow params.
            self._init_workflow()

    def _set_dsp_features(self, dsp):
        self.dsp = dsp
        self.name = dsp.name
        self.nodes = dsp.nodes
        self.dmap = dsp.dmap
        self.raises = dsp.raises
        self._pred = dsp.dmap.pred
        self._succ = dsp.dmap.succ
        self._edge_length = dsp._edge_length

    def _set_inputs(self, inputs, initial_dist, excluded_defaults=()):
        if self.no_call:
            # Set initial values.
            initial_values = dict.fromkeys(self.dsp.default_values, NONE)
            initial_values = {
                k: v for k, v in self.dsp.default_values.items()
                if k not in excluded_defaults
            }
            if inputs is not None:  # Update initial values with input values.
                initial_values.update(dict.fromkeys(inputs, NONE))
        else:
            # Set initial values.
            initial_values = {
                k: v['value'] for k, v in self.dsp.default_values.items()
                if k not in excluded_defaults
            }

            if inputs is not None:  # Update initial values with input values.
                initial_values.update(inputs)

        # Set initial values.
        initial_distances = {
            k: v['initial_dist']
            for k, v in self.dsp.default_values.items()
            if k not in excluded_defaults and (not inputs or k not in inputs)
        }

        if initial_dist is not None:  # Update initial distances.
            initial_distances.update(initial_dist)

        self.inputs, self.inputs_dist = initial_values, initial_distances

    def _set_wildcards(self, inputs=None, outputs=None):
        """
        Update wildcards set with the input data nodes that are also outputs.

        :param inputs:
            Input data nodes.
        :type inputs: list[str], iterable, optional

        :param outputs:
            Ending data nodes.
        :type outputs: list[str], iterable, optional
        """

        w = self._wildcards = set()  # Clean wildcards.

        if outputs and inputs:
            node, wi = self.nodes, self._wait_in.get  # Namespace shortcut.

            # Input data nodes that are in output_targets.
            w_crd = {u: node[u] for u in inputs if u in outputs or wi(u, False)}

            # Data nodes without the wildcard.
            w.update([k for k, v in w_crd.items() if v.get('wildcard', True)])

    def _update_methods(self):
        self._targets = self.outputs.copy() if self.outputs else None

    def wf_remove_edge(self, u, v):
        graph = self.workflow
        graph.remove_edge(u, v)  # Remove the edge.
        if not (graph.succ[v] or graph.pred[v]):  # Check if v is isolate.
            graph.remove_node(v)  # Remove the isolate out node.

    def wf_add_edge(self, u, v, **attr):
        graph = self.workflow
        succ, pred = graph.succ, graph.pred
        if v not in succ:  # Add nodes.
            succ[v], pred[v], graph.nodes[v] = {}, {}, {}

        succ[u][v] = pred[v][u] = attr  # Add the edge.

    def check_cutoff(self, distance):
        """
        Stops the search of the investigated node of the ArciDispatch
        algorithm.

        :param distance:
            Distance from the starting node.
        :type distance: float, int

        :return:
            True if distance > cutoff, otherwise False.
        :rtype: bool
        """
        if self.cutoff is None:
            return False
        return distance > self.cutoff  # Check cutoff distance.

    def check_wait_in(self, wait_in, n_id):
        """
        Stops the search of the investigated node of the ArciDispatch
        algorithm, until all inputs are satisfied.

        :param wait_in:
            If True the node is waiting input estimations.
        :type wait_in: bool

        :param n_id:
            Data or function node id.
        :type n_id: str

        :return:
            True if all node inputs are satisfied, otherwise False.
        :rtype: bool
        """
        if self._wait_in:
            wait_in = self._wait_in.get(n_id, wait_in)
        if wait_in:
            wf = self.workflow.pred[n_id]
            return not all(k in wf for k in self._pred[n_id])
        return False

    def _clean_set(self):
        self.clear()
        from .graph import DiGraph
        self.workflow = DiGraph()
        self._visited = set()
        self._errors = collections.OrderedDict()
        self.sub_sol = {self.index: self}
        self.fringe = []  # Use heapq with (distance, wait, label).
        self.dist = {START: inf(0, -1)}
        self.seen = {START: inf(0, -1)}
        self._meet = {START: inf(0, -1)}
        self._pipe = []
        self._update_methods()

    def _init_workflow(self, inputs=None, inputs_dist=None, initial_dist=0.0,
                       clean=True):
        # Clean previous outputs.
        if clean:
            self._clean_set()

        self._visited.add(START)  # Nodes visited by the algorithm.

        # Add the starting node to the workflow graph.
        self.workflow.add_node(START, type='start')

        if inputs_dist is None:  # Update inp dist.
            inputs_dist = self.inputs_dist or {}

        if inputs is None:
            inputs = self.inputs

        initial_dist = inf.format(initial_dist)

        # Namespace shortcuts for speed.
        add_value = self._add_initial_value

        # Add initial values to fringe and seen.
        it = sorted(((
            initial_dist + inputs_dist.get(k, 0.0), str(k), k
        ) for k in inputs))
        if self.no_call:
            for d, _, k in it:
                add_value(k, {}, d)
        else:
            for d, _, k in it:
                add_value(k, {'value': inputs[k]}, d)

        self._add_out_dsp_inputs()

    def _close(self, cached_ids):
        p = self.index[:-1]
        if p:
            p = self.sub_sol[p]
            if self.index in cached_ids:
                k = cached_ids[self.index]
            else:
                i = self.index[-1:]
                k = next(k for k, v in p.nodes.items() if v['index'] == i)
                cached_ids[self.index] = k
            return all(i in p.dist for i in p.dmap[k])
        return False

    @staticmethod
    def _update_fut_results(futs, fut, data, key):
        if isinstance(fut, Future):
            get_nested_dicts(futs, fut, default=list).append((data, key))
        elif isinstance(fut, AsyncList):
            for i, j in enumerate(fut):
                if isinstance(j, Future):
                    get_nested_dicts(futs, j, default=list).append((fut, i))

    def result(self, timeout=None):
        """
        Set all asynchronous results.

        :param timeout:
            The number of seconds to wait for the result if the futures aren't
            done. If None, then there is no limit on the wait time.
        :type timeout: float

        :return:
            Update Solution.
        :rtype: Solution
        """
        futs, ex = collections.OrderedDict(), False
        _update = self._update_fut_results
        for p in self._pipe:
            n, s = p[-1]
            if n in s:
                _update(futs, s[n], s, n)

        for sol in self.sub_sol.values():
            for k, f in sol.items():
                _update(futs, f, sol, k)

            for attr in sol.workflow.nodes.values():
                if 'results' in attr:
                    _update(futs, attr['results'], attr, 'results')

            for attr in sol.workflow.edges.values():
                if 'value' in attr:
                    _update(futs, attr['value'], attr, 'value')
        if futs:
            from concurrent.futures import wait as wait_fut
            wait_fut(futs, timeout)
        EXECUTORS.set_active(id(self), False)
        exceptions = Exception, ExecutorShutdown, DispatcherAbort, SkipNode
        for f, it in futs.items():
            try:
                r = await_result(f, 0)
                for d, k in it:
                    d[k] = r
            except exceptions as e:
                for d, k in it:
                    if k in d:
                        del d[k]
                if not ex:
                    ex = isinstance(e, SkipNode) and e.ex or e
        if ex:
            raise ex
        return self

    @staticmethod
    def _dsp_closed_add(dsp_closed, s):
        dsp_closed.add(s.index)
        for val in s.dsp.sub_dsp_nodes.values():
            _s = s.sub_sol.get(s.index + val['index'], None)
            if _s:
                Solution._dsp_closed_add(dsp_closed, _s)

    def _run(self, stopper=None, executor=False):
        # Initialized and terminated dispatcher sets.
        dsp_closed, dsp_init, cached_ids = set(), {self.index}, {}

        # Reset function pipe.
        pipe = self._pipe = []

        # A function to check if a dispatcher has been initialized.
        check_dsp = dsp_init.__contains__

        # Namespaces shortcuts
        dsp_init_add, pipe_append = dsp_init.add, pipe.append
        fringe, check_cutoff = self.fringe, self.check_cutoff
        ctx = {
            'no_call': self.no_call, 'stopper': stopper, 'executor': executor
        }

        while fringe:
            # Visit the closest available node.
            n = (d, _, (v, sol)) = heappop(fringe)

            # Skip terminated sub-dispatcher or visited nodes.
            if sol.index in dsp_closed or (v is not START and v in sol.dist):
                continue

            # Close sub-dispatcher solution when all outputs are satisfied.
            if sol._close(cached_ids):
                self._dsp_closed_add(dsp_closed, sol)
                cached_ids.pop(sol.index)
                continue

            dsp_init_add(sol.index)  # Update initialized dispatcher sets.

            pipe_append(n)  # Add node to the pipe.

            # Set and visit nodes.
            if not sol._visit_nodes(v, d, fringe, check_cutoff, **ctx):
                if self is sol:
                    break  # Reach all targets.
                else:  # Terminated sub-dispatcher.
                    self._dsp_closed_add(dsp_closed, sol)

            # See remote link node.
            sol._see_remote_link_node(v, fringe, d, check_dsp)

        if self.rm_unused_nds:  # Remove unused func and sub-dsp nodes.
            self._remove_unused_nodes()
        self.fringe = None
        return self  # Data outputs.

    def get_sub_dsp_from_workflow(self, sources, reverse=False,
                                  add_missing=False, check_inputs=True):
        """
        Returns the sub-dispatcher induced by the workflow from sources.

        The induced sub-dispatcher of the dsp contains the reachable nodes and
        edges evaluated with breadth-first-search on the workflow graph from
        source nodes.

        :param sources:
           Source nodes for the breadth-first-search.
           A container of nodes which will be iterated through once.
        :type sources: list[str], iterable

        :param reverse:
           If True the workflow graph is assumed as reversed.
        :type reverse: bool, optional

        :param add_missing:
           If True, missing function' inputs are added to the sub-dispatcher.
        :type add_missing: bool, optional

        :param check_inputs:
           If True the missing function' inputs are not checked.
        :type check_inputs: bool, optional

        :return:
           A sub-dispatcher.
        :rtype: schedula.dispatcher.Dispatcher
        """
        sub_dsp = self.dsp.get_sub_dsp_from_workflow(
            sources, self.workflow, reverse=reverse, add_missing=add_missing,
            check_inputs=check_inputs
        )

        return sub_dsp  # Return the sub-dispatcher map.

    @property
    def pipe(self):
        """Returns the full pipe of a dispatch run."""
        return get_full_pipe(self)

    def _copy_structure(self, **kwargs):
        sol = self.__class__(
            self.dsp, self.inputs, self.outputs, False, self.cutoff,
            self.inputs_dist, self.no_call, self.rm_unused_nds, self._wait_in,
            self.no_domain, True, self.index, self.full_name, self.verbose
        )
        sol._clean_set()
        it = ['_wildcards', 'inputs', 'inputs_dist']
        it += [k for k, v in kwargs.items() if v]
        for k in it:
            setattr(sol, k, getattr(self, k))
        return sol

    def __deepcopy__(self, memo):
        y = super(Solution, self).__deepcopy__(memo)
        y._update_methods()
        return y

    def _add_out_dsp_inputs(self):
        # Nodes that are out of the dispatcher nodes.
        o = sorted((k for k in self.inputs if k not in self.nodes), key=str)

        # Add nodes that are out of the dispatcher nodes.
        if self.no_call:
            self.update(collections.OrderedDict.fromkeys(o, None))
        else:
            self.update(collections.OrderedDict((k, self.inputs[k]) for k in o))

    def check_targets(self, node_id):
        """
        Terminates ArciDispatch algorithm when all targets have been
        visited.

        :param node_id:
            Data or function node id.
        :type node_id: str

        :return:
            True if all targets have been visited, otherwise False.
        :rtype: bool
        """
        try:
            self._targets.remove(node_id)  # Remove visited node.
            return not self._targets  # If no targets terminate the algorithm.
        except (AttributeError, KeyError):
            return False  # The node is not in the targets set.

    def _get_node_estimations(self, node_attr, node_id):
        """
        Returns the data nodes estimations and `wait_inputs` flag.

        :param node_attr:
            Dictionary of node attributes.
        :type node_attr: dict

        :param node_id:
            Data node's id.
        :type node_id: str

        :returns:

            - node estimations with minimum distance from the starting node, and
            - `wait_inputs` flag
        :rtype: (dict[str, T], bool)
        """

        # Get data node estimations.
        estimations = self.workflow.pred[node_id]

        wait_in = node_attr['wait_inputs']  # Namespace shortcut.

        # Check if node has multiple estimations and it is not waiting inputs.
        if len(estimations) > 1 and not self._wait_in.get(node_id, wait_in):
            # Namespace shortcuts.
            dist, edg_length = self.dist, self._edge_length
            succ = self.dmap.succ

            est = []  # Estimations' heap.

            for k, v in estimations.items():  # Calculate length.
                if k is not START:
                    d = dist[k] + edg_length(succ[k][node_id], node_attr)
                    heappush(est, (d, k, v))

            # The estimation with minimum distance from the starting node.
            estimations = {est[0][1]: est[0][2]}

            # Remove unused workflow edges.
            self.workflow.remove_edges_from([(v[1], node_id) for v in est[1:]])

        return estimations, wait_in  # Return estimations and wait_inputs flag.

    def _remove_wait_in(self):

        ll = _sort_sk_wait_in(self)
        n_d = set()

        for d, _, _, w, k in ll:
            if d == ll[0][0]:
                w[k] = False
                if w is self._wait_in:
                    n_d.add(k)
        return n_d, ll

    def _set_node_output(self, node_id, no_call, next_nds=None, **kw):
        """
        Set the node outputs from node inputs.

        :param node_id:
            Data or function node id.
        :type node_id: str

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool

        :return:
            If the output have been evaluated correctly.
        :rtype: bool
        """

        # Namespace shortcuts.
        node_attr = self.nodes[node_id]
        node_type = node_attr['type']

        if node_type == 'data':  # Set data node.
            return self._set_data_node_output(
                node_id, node_attr, no_call, next_nds, **kw
            )

        elif node_type == 'function':  # Set function node.
            return self._set_function_node_output(
                node_id, node_attr, no_call, next_nds, **kw
            )

    def _evaluate_function(self, args, node_id, node_attr, attr, stopper=None,
                           executor=False):
        self._started(attr, node_id)

        def _callback(is_sol, sol):
            if is_sol:
                attr['solution'] = sol

        res = async_process(
            [node_attr['function']], *args, stopper=stopper, executor=executor,
            sol=self, callback=_callback, sol_name=self.full_name + (node_id,),
            verbose=self.verbose
        )

        return res

    def _check_function_domain(self, args, node_attr, node_id):
        # noinspection PyUnresolvedReferences
        attr = self.workflow.nodes[node_id]
        if not self.no_domain and 'input_domain' in node_attr:
            if node_attr.get('await_domain', True):
                args = map(await_result, args)
            args = [v for v in args if v is not NONE]
            # noinspection PyCallingNonCallable
            attr['solution_domain'] = bool(node_attr['input_domain'](*args))
            if not attr['solution_domain']:
                raise SkipNode

    def _evaluate_node(self, args, node_attr, node_id, skip_func=False, **kw):
        # noinspection PyUnresolvedReferences
        attr = self.workflow.nodes[node_id]
        try:
            if skip_func:
                value = args[0]
            else:
                args = [v for v in args if v is not NONE]
                value = self._evaluate_function(args, node_id, node_attr, attr,
                                                **kw)
            value = self._apply_filters(value, node_id, node_attr, attr, **kw)
            self._ended(attr, node_id)

            if 'callback' in node_attr:  # Invoke callback func of data node.
                try:
                    # noinspection PyCallingNonCallable
                    node_attr['callback'](value)
                except Exception as ex:
                    msg = "Failed CALLBACK '%s' due to:\n  %s"
                    self._warning(msg, node_id, ex)

            return value
        except Exception as ex:
            self._ended(attr, node_id)
            # Some error occurs.
            msg = "Failed DISPATCHING '%s' due to:\n  %r"
            self._warning(msg, node_id, ex)
            raise SkipNode(ex=ex)

    def _set_data_node_output(self, node_id, node_attr, no_call, next_nds=None,
                              **kw):
        """
        Set the data node output from node estimations.

        :param node_id:
            Data node id.
        :type node_id: str

        :param node_attr:
            Dictionary of node attributes.
        :type node_attr: dict[str, T]

        :param no_call:
            If True data node estimations are not used.
        :type no_call: bool

        :return:
            If the output have been evaluated correctly.
        :rtype: bool
        """

        # Get data node estimations.
        est, wait_in = self._get_node_estimations(node_attr, node_id)

        if no_call:
            self[node_id] = NONE  # Set data output.

            value = {}  # Output value.
        else:
            if node_id is PLOT:
                est = est.copy()
                est[PLOT] = {'value': {'obj': self}}

            sf = not (wait_in or 'function' in node_attr)

            if sf:
                # Data node that has just one estimation value.
                args = tuple(v['value'] for v in est.values())
            else:
                args = ({k: v['value'] for k, v in est.items()},)
            try:
                # Final estimation of the node and node status.
                value = async_thread(self, args, node_attr, node_id, sf, **kw)
            except SkipNode:
                return False

            if value is not NONE:  # Set data output.
                self[node_id] = value

            value = {'value': value}  # Output value.

        if next_nds:
            # namespace shortcuts for speed.
            wf_add_edge = self.wf_add_edge

            for u in next_nds:  # Set workflow.
                wf_add_edge(node_id, u, **value)

        else:
            # List of functions.
            succ_fun = []

            # namespace shortcuts for speed.
            n, has, sub_sol = self.nodes, self.workflow.has_edge, self.sub_sol
            index, add_succ_fun = self.index, succ_fun.append

            for u in self._succ[node_id]:  # no_visited_in_sub_dsp.
                node = n[u]
                if node['type'] == 'dispatcher' and has(u, node_id):
                    visited = sub_sol[index + node['index']]._visited
                    node['inputs'][node_id] not in visited and add_succ_fun(u)
                else:
                    add_succ_fun(u)

            # Check if it has functions as outputs and wildcard condition.
            if succ_fun and succ_fun[0] not in self._visited:
                # namespace shortcuts for speed.
                wf_add_edge = self.wf_add_edge

                for u in succ_fun:  # Set workflow.
                    wf_add_edge(node_id, u, **value)

        return True  # Return that the output have been evaluated correctly.

    def _apply_filters(self, res, node_id, node_attr, attr, stopper=None,
                       executor=False):
        funcs = node_attr.get('filters')

        if funcs:
            self._started(attr, node_id)
            attr['solution_filters'] = filters = [res]

            # noinspection PyUnusedLocal
            def _callback(is_sol, sol):
                filters.append(sol)

            res = async_process(
                funcs, res, stopper=stopper, executor=executor, sol=self,
                callback=_callback, sol_name=self.full_name + (node_id,)
            )

        return res

    def _started(self, attr, node_id):
        if 'started' not in attr:
            attr['started'] = time.time()
            self._verbose(node_id, attr)

    def _ended(self, attr, node_id):
        if 'started' in attr:
            attr['duration'] = time.time() - attr['started']
            self._verbose(node_id, attr, end=True)

    def _verbose(self, node_id, attr, end=False):
        if self.verbose:
            if end:
                msg = 'Done `%s` in {:.5f} sec.'.format(attr['duration'])
            else:
                msg = 'Start `%s`...'
            log.info(msg % '/'.join(self.full_name + (node_id,)))

    def _set_function_node_output(self, node_id, node_attr, no_call,
                                  next_nds=None, **kw):
        """
        Set the function node output from node inputs.

        :param node_id:
            Function node id.
        :type node_id: str

        :param node_attr:
            Dictionary of node attributes.
        :type node_attr: dict[str, T]

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool

        :return:
            If the output have been evaluated correctly.
        :rtype: bool
        """

        # Namespace shortcuts for speed.
        o_nds, dist = node_attr['outputs'], self.dist

        # List of nodes that can still be estimated by the function node.
        output_nodes = next_nds or {
            k for k in self._succ[node_id] if k not in dist
        }

        if not output_nodes:  # This function is not needed.
            self.workflow.remove_node(node_id)  # Remove function node.
            return False

        wf_add_edge = self.wf_add_edge  # Namespace shortcuts for speed.

        if no_call:
            for u in output_nodes:  # Set workflow out.
                wf_add_edge(node_id, u)
            return True

        args = self.workflow.pred[node_id]  # List of the function's arguments.
        args = [args[k]['value'] for k in node_attr['inputs']]

        try:
            self._check_function_domain(args, node_attr, node_id)
            res = async_thread(self, args, node_attr, node_id, **kw)
            # noinspection PyUnresolvedReferences
            self.workflow.nodes[node_id]['results'] = res
        except SkipNode:
            return False

        # Set workflow.
        for k, v in zip(o_nds, res if len(o_nds) > 1 else [res]):
            if k in output_nodes and v is not NONE:
                wf_add_edge(node_id, k, value=v)

        return True  # Return that the output have been evaluated correctly.

    def _add_initial_value(self, data_id, value, initial_dist=0.0,
                           fringe=None, check_cutoff=None, no_call=None):
        """
        Add initial values updating workflow, seen, and fringe.

        :param fringe:
            Heapq of closest available nodes.
        :type fringe: list[(float | int, bool, (str, Dispatcher)]

        :param check_cutoff:
            Check the cutoff limit.
        :type check_cutoff: (int | float) -> bool

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool

        :param data_id:
            Data node id.
        :type data_id: str

        :param value:
            Data node value e.g., {'value': val}.
        :type value: dict[str, T]

        :param initial_dist:
            Data node initial distance in the ArciDispatch algorithm.
        :type initial_dist: float, int, optional

        :return:
            True if the data has been visited, otherwise false.
        :rtype: bool
        """

        # Namespace shortcuts for speed.
        nodes, seen, edge_weight = self.nodes, self.seen, self._edge_length
        wf_remove_edge, check_wait_in = self.wf_remove_edge, self.check_wait_in
        wf_add_edge, dsp_in = self.wf_add_edge, self._set_sub_dsp_node_input
        update_view = self._update_meeting

        if fringe is None:
            fringe = self.fringe

        if no_call is None:
            no_call = self.no_call

        check_cutoff = check_cutoff or self.check_cutoff

        if data_id not in nodes:  # Data node is not in the dmap.
            return False

        wait_in = nodes[data_id]['wait_inputs']  # Store wait inputs flag.

        index = nodes[data_id]['index']  # Store node index.

        wf_add_edge(START, data_id, **value)  # Add edge.

        if data_id in self._wildcards:  # Check if the data node has wildcard.

            self._visited.add(data_id)  # Update visited nodes.

            self.workflow.add_node(data_id)  # Add node to workflow.

            for w, edge_data in self.dmap[data_id].items():  # See func node.
                wf_add_edge(data_id, w, **value)  # Set workflow.

                node = nodes[w]  # Node attributes.

                # Evaluate distance.
                vw_dist = initial_dist + edge_weight(edge_data, node)

                update_view(w, vw_dist)  # Update view distance.

                # Check the cutoff limit and if all inputs are satisfied.
                if check_cutoff(vw_dist):
                    wf_remove_edge(data_id, w)  # Remove workflow edge.
                    continue  # Pass the node.
                elif node['type'] == 'dispatcher':
                    dsp_in(data_id, w, fringe, check_cutoff, no_call, vw_dist)
                elif check_wait_in(True, w):
                    continue  # Pass the node.

                seen[w] = vw_dist  # Update distance.
                if fringe is None:  # SubDispatchPipe.
                    continue
                vd = (True, w, self.index + node['index'])  # Virtual distance.

                heappush(fringe, (vw_dist, vd, (w, self)))  # Add 2 heapq.

            return True

        update_view(data_id, initial_dist)  # Update view distance.

        if check_cutoff(initial_dist):  # Check the cutoff limit.
            wf_remove_edge(START, data_id)  # Remove workflow edge.
        elif not check_wait_in(wait_in, data_id):  # Check inputs.
            seen[data_id] = initial_dist  # Update distance.
            if fringe is not None:  # SubDispatchPipe.
                vd = wait_in, str(data_id), self.index + index  # Virtual dist.

                # Add node to heapq.
                heappush(fringe, (initial_dist, vd, (data_id, self)))

            return True
        return False

    def _update_meeting(self, node_id, dist):
        view = self._meet
        if node_id in self._meet:
            view[node_id] = max(dist, view[node_id])
        else:
            view[node_id] = dist

    def _visit_nodes(self, node_id, dist, fringe, check_cutoff, no_call=False,
                     **kw):
        """
        Visits a node, updating workflow, seen, and fringe..

        :param node_id:
            Node id to visit.
        :type node_id: str

        :param dist:
            Distance from the starting node.
        :type dist: float, int

        :param fringe:
            Heapq of closest available nodes.
        :type fringe: list[(float | int, bool, (str, Dispatcher)]

        :param check_cutoff:
            Check the cutoff limit.
        :type check_cutoff: (int | float) -> bool

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool, optional

        :return:
            False if all dispatcher targets have been reached, otherwise True.
        :rtype: bool
        """

        # Namespace shortcuts.
        wf_rm_edge, wf_has_edge = self.wf_remove_edge, self.workflow.has_edge
        edge_weight, nodes = self._edge_length, self.nodes

        self.dist[node_id] = dist  # Set minimum dist.

        self._visited.add(node_id)  # Update visited nodes.

        if not self._set_node_output(node_id, no_call, **kw):  # Set output.
            # Some error occurs or inputs are not in the function domain.
            return True

        if self.check_targets(node_id):  # Check if the targets are satisfied.
            return False  # Stop loop.

        for w, e_data in self.dmap[node_id].items():
            if not wf_has_edge(node_id, w):  # Check wildcard option.
                continue

            node = nodes[w]  # Get node attributes.

            vw_d = dist + edge_weight(e_data, node)  # Evaluate dist.

            if check_cutoff(vw_d):  # Check the cutoff limit.
                wf_rm_edge(node_id, w)  # Remove edge that cannot be see.
                continue

            if node['type'] == 'dispatcher':
                self._set_sub_dsp_node_input(
                    node_id, w, fringe, check_cutoff, no_call, vw_d)

            else:  # See the node.
                self._see_node(w, fringe, vw_d)

        return True

    def _see_node(self, node_id, fringe, dist, w_wait_in=0):
        """
        See a node, updating seen and fringe.

        :param node_id:
            Node id to see.
        :type node_id: str

        :param fringe:
            Heapq of closest available nodes.
        :type fringe: list[(float | int, bool, (str, Dispatcher)]

        :param dist:
            Distance from the starting node.
        :type dist: float, int

        :param w_wait_in:
            Additional weight for sorting correctly the nodes in the fringe.
        :type w_wait_in: int, float

        :return:
            True if the node is visible, otherwise False.
        :rtype: bool
        """

        # Namespace shortcuts.
        seen, dists = self.seen, self.dist

        wait_in = self.nodes[node_id]['wait_inputs']  # Wait inputs flag.

        self._update_meeting(node_id, dist)  # Update view distance.

        # Check if inputs are satisfied.
        if self.check_wait_in(wait_in, node_id):
            pass  # Pass the node

        elif node_id in dists:  # The node w already estimated.
            if dist < dists[node_id]:  # Error for negative paths.
                raise DispatcherError('Contradictory paths found: '
                                      'negative weights?', sol=self)
        elif node_id not in seen or dist < seen[node_id]:  # Check min dist.
            seen[node_id] = dist  # Update dist.
            if fringe is not None:  # SubDispatchPipe.
                index = self.nodes[node_id]['index']  # Node index.

                # Virtual distance.
                vd = w_wait_in + int(wait_in), str(node_id), self.index + index

                # Add to heapq.
                heappush(fringe, (dist, vd, (node_id, self)))

            return True  # The node is visible.
        return False  # The node is not visible.

    def _remove_unused_nodes(self):
        """
        Removes unused function and sub-dispatcher nodes.
        """

        # Namespace shortcuts.
        nodes, wf_remove_node = self.nodes, self.workflow.remove_node
        add_visited, succ = self._visited.add, self.workflow.succ

        # Remove unused function and sub-dispatcher nodes.
        for n in [k for k in self.workflow.pred if k not in self._visited]:
            node_type = nodes[n]['type']  # Node type.

            if node_type == 'data':
                continue  # Skip data node.

            if node_type == 'dispatcher' and succ[n]:
                add_visited(n)  # Add to visited nodes.
                i = self.index + nodes[n]['index']
                self.sub_sol[i]._remove_unused_nodes()
                continue  # Skip sub-dispatcher node with outputs.

            wf_remove_node(n)  # Remove unused node.

    def _init_sub_dsp(self, dsp, fringe, outputs, no_call, initial_dist, index,
                      full_name, excluded_defaults):
        """
        Initialize the dispatcher as sub-dispatcher and update the fringe.

        :param fringe:
            Heapq of closest available nodes.
        :type fringe: list[(float | int, bool, (str, Dispatcher)]

        :param outputs:
            Ending data nodes.
        :type outputs: list[str], iterable

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool
        """

        # Initialize as sub-dispatcher.
        sol = self.__class__(
            dsp, {}, outputs, False, None, None, no_call, False,
            wait_in=self._wait_in.get(dsp, None), index=self.index + index,
            full_name=full_name, verbose=self.verbose,
            excluded_defaults=excluded_defaults
        )

        sol.sub_sol = self.sub_sol

        for f in sol.fringe or ():  # Update the fringe.
            item = (initial_dist + f[0], (2,) + f[1][1:], f[-1])
            heappush(fringe, item)

        return sol

    def _see_remote_link_node(self, node_id, fringe=None, dist=None,
                              check_dsp=lambda x: True):
        """
        See data remote links of the node (set output to remote links).

        :param node_id:
            Node id.
        :type node_id: str

        :param fringe:
            Heapq of closest available nodes.
        :type fringe: list[(float | int, bool, (str, Dispatcher)]

        :param dist:
            Distance from the starting node.
        :type dist: float, int

        :param check_dsp:
            A function to check if the remote dispatcher is ok.
        :type check_dsp: (Dispatcher) -> bool
        """
        # Get `p_id` if `node_id` is data node.
        p_id = self.nodes[node_id]['type'] == 'data' and self.index[:-1]
        if p_id and check_dsp(p_id) and node_id in self:
            # Get parent solution and child index.
            sol, c_i = self.sub_sol[p_id], self.index[-1:]
            for dsp_id, n in sol.dsp.nodes.items():
                if n['index'] == c_i and node_id in n.get('outputs', {}):
                    value = self[node_id]  # Get data output.
                    visited, has_edge = sol._visited, sol.workflow.has_edge
                    pass_result, see_node = sol.wf_add_edge, sol._see_node
                    for n_id in stlp(n['outputs'][node_id]):
                        # Node has been visited or inp do not coincide with out.
                        if not (n_id in visited or has_edge(n_id, dsp_id)):
                            pass_result(dsp_id, n_id, value=value)  # To child.
                            if fringe is not None:
                                see_node(n_id, fringe, dist, w_wait_in=2)
                    break

    def _check_sub_dsp_domain(self, dsp_id, node, pred, kw):
        if 'input_domain' in node and not (self.no_domain or self.no_call):
            try:
                adict = {k: v['value'] for k, v in pred.items()}
                if node.get('await_domain', True):
                    adict = {k: await_result(v) for k, v in adict.items()}
                kw['solution_domain'] = s = bool(node['input_domain'](adict))
                return s
            except Exception as ex:  # Some error occurs.
                msg = "Failed SUB-DSP DOMAIN '%s' due to:\n  %r"
                self._warning(msg, dsp_id, ex)
                return False

    def _set_sub_dsp_node_input(self, node_id, dsp_id, fringe, check_cutoff,
                                no_call, initial_dist):
        """
        Initializes the sub-dispatcher and set its inputs.

        :param node_id:
            Input node to set.
        :type node_id: str

        :param dsp_id:
            Sub-dispatcher node id.
        :type dsp_id: str

        :param fringe:
            Heapq of closest available nodes.
        :type fringe: list[(float | int, bool, (str, Dispatcher)]

        :param check_cutoff:
            Check the cutoff limit.
        :type check_cutoff: (int | float) -> bool

        :param no_call:
            If True data node estimation function is not used.
        :type no_call: bool

        :param initial_dist:
            Distance to reach the sub-dispatcher node.
        :type initial_dist: int, float

        :return:
            If the input have been set.
        :rtype: bool
        """

        # Namespace shortcuts.
        node = self.nodes[dsp_id]
        dsp, pred = node['function'], self.workflow.pred[dsp_id]
        distances, sub_sol = self.dist, self.sub_sol

        iv_nodes = [node_id]  # Nodes do be added as initial values.

        self._meet[dsp_id] = initial_dist  # Set view distance.

        # Check if inputs are satisfied.
        if self.check_wait_in(node['wait_inputs'], dsp_id):
            return False  # Pass the node

        if dsp_id not in distances:
            kw = {}
            dom = self._check_sub_dsp_domain(dsp_id, node, pred, kw)
            if dom is True:
                iv_nodes = pred  # Args respect the domain.
            elif dom is False:
                return False

            # Initialize the sub-dispatcher.
            sub_sol[self.index + node['index']] = sol = self._init_sub_dsp(
                dsp, fringe, node['outputs'], no_call, initial_dist,
                node['index'], self.full_name + (dsp_id,),
                set(node.get('inputs', {}).values())
            )
            self.workflow.add_node(dsp_id, solution=sol, **kw)

            distances[dsp_id] = initial_dist  # Update min distance.
        else:
            sol = sub_sol[self.index + node['index']]

        for n_id in iv_nodes:
            # Namespace shortcuts.
            val = pred[n_id]

            for n in stlp(node['inputs'][n_id]):
                # Add initial value to the sub-dispatcher.
                sol._add_initial_value(
                    n, val, initial_dist, fringe, check_cutoff, no_call
                )

        return True

    def _warning(self, msg, node_id, ex, *args, **kwargs):
        """
        Handles the error messages.

        .. note:: If `self.raises` is True the dispatcher interrupt the dispatch
           when an error occur, otherwise if `raises != ''` it logs a warning.
        """

        raises = self.raises(ex) if callable(self.raises) else self.raises

        if raises and isinstance(ex, DispatcherError):
            ex.update(self)
            raise ex

        self._errors[node_id] = msg % ((node_id, ex) + args)
        node_id = '/'.join(self.full_name + (node_id,))

        if raises:
            raise DispatcherError(
                msg, node_id, ex, *args, sol=self, ex=ex, **kwargs
            )
        elif raises != '':
            kwargs['exc_info'] = kwargs.get('exc_info', 1)
            try:
                log.error(msg, node_id, ex, *args, **kwargs)
            except TypeError:  # MicroPython.
                kwargs.pop('exc_info')
                log.error(msg, node_id, ex, *args, **kwargs)
