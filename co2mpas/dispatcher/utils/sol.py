#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains a comprehensive list of all modules and classes within dispatcher.

Docstrings should provide sufficient understanding for any individual function.
"""
from collections import OrderedDict
from copy import _reconstruct
from datetime import datetime
from heapq import heappush, heappop
import logging
import threading
from .alg import (add_edge_fun, remove_edge_fun, stlp, get_full_pipe,
                  _sort_sk_wait_in, get_sub_node)
from .cst import START, NONE, PLOT
from .des import parent_func
from .dsp import SubDispatch
from .exc import DispatcherError, DispatcherAbort


__all__ = ['Solution']

log = logging.getLogger(__name__)


class Solution(OrderedDict):
    def __hash__(self):
        return id(self)

    def __lt__(self, other):
        return isinstance(other, Solution) and id(other) < id(self)

    def __init__(self, dsp=None, inputs=None, outputs=None, wildcard=False,
                 cutoff=None, inputs_dist=None, no_call=False,
                 rm_unused_nds=False, wait_in=None, no_domain=False,
                 _empty=False, index=(-1,), stopper=None):

        super(Solution, self).__init__()
        self.index = index
        self.rm_unused_nds = rm_unused_nds
        self.no_call = no_call
        self.no_domain = no_domain
        self.cutoff = cutoff
        self._wait_in = wait_in or {}
        self.outputs = set(outputs or ())

        from .. import Dispatcher
        self._set_dsp_features(dsp or Dispatcher(caller=__name__))

        self.stopper = stopper or self.dsp.stopper

        if not _empty:
            self._set_inputs(inputs, inputs_dist)

            # Set wildcards.
            self._set_wildcards(*((self.inputs, outputs) if wildcard else ()))

            # Initialize workflow params.
            self._init_workflow()

    def _input_value(self):
        # Define a function that return the input value of a given data node.
        if self.no_call:
            # noinspection PyUnusedLocal
            def input_value(k):
                return {}
        else:
            inputs = self.inputs

            def input_value(k):
                return {'value': inputs[k]}
        return input_value

    def _set_dsp_features(self, dsp):
        self.dsp = dsp
        self.name = dsp.name
        self.nodes = dsp.nodes
        self.dmap = dsp.dmap
        self.raises = dsp.raises
        self._pred = dsp.dmap.pred
        self._succ = dsp.dmap.succ
        self._edge_length = dsp._edge_length

    def _set_inputs(self, inputs, initial_dist):
        if self.no_call:
            # Set initial values.
            initial_values = dict.fromkeys(self.dsp.default_values, NONE)

            if inputs is not None:  # Update initial values with input values.
                initial_values.update(dict.fromkeys(inputs, NONE))
        else:
            # Set initial values.
            initial_values = {k: v['value']
                              for k, v in self.dsp.default_values.items()}

            if inputs is not None:  # Update initial values with input values.
                initial_values.update(inputs)

        # Set initial values.
        initial_distances = {k: v['initial_dist']
                             for k, v in self.dsp.default_values.items()
                             if not inputs or k not in inputs}

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
        self._wf_add_edge = add_edge_fun(self.workflow)
        self._wf_remove_edge = remove_edge_fun(self.workflow)
        self.check_wait_in = self._check_wait_input_flag()
        self.check_targets = self._check_targets()
        self.check_cutoff = self._check_cutoff()

    def _clean_set(self):
        self.clear()
        from networkx import DiGraph
        self.workflow = DiGraph()
        self._visited = set()
        self._wf_pred = self.workflow.pred
        self._errors = OrderedDict()
        self.sub_dsp = {self.dsp: self}
        self.fringe = []  # Use heapq with (distance, wait, label).
        self.dist, self.seen, self._meet = {START: -1}, {START: -1}, {START: -1}
        self._update_methods()
        self._pipe = []

    def _init_workflow(self, inputs=None, input_value=None, inputs_dist=None,
                       initial_dist=0.0, clean=True):

        # Clean previous outputs.
        if clean:
            self._clean_set()

        # Namespace shortcuts for speed.
        add_value = self._add_initial_value

        self._visited.add(START)  # Nodes visited by the algorithm.

        # Add the starting node to the workflow graph.
        self.workflow.add_node(START, type='start')

        inputs_dist = inputs_dist or self.inputs_dist or {}  # Update inp dist.
        inputs = inputs or self.inputs
        input_value = input_value or self._input_value()

        # Add initial values to fringe and seen.
        it = ((inputs_dist.get(v, 0.0) + initial_dist, v) for v in inputs)
        for d, k in sorted(it):
            add_value(k, input_value(k), d)

        self._add_out_dsp_inputs()

    def run(self):
        # Initialized and terminated dispatcher sets.
        dsp_closed, dsp_init = set(), {self.dsp}

        # Reset function pipe.
        pipe = self._pipe = []

        # A function to check if a dispatcher has been initialized.
        check_dsp = dsp_init.__contains__

        # Namespaces shortcuts
        dsp_init_add, pipe_append = dsp_init.add, pipe.append
        dsp_closed_add = dsp_closed.add
        fringe, check_cutoff = self.fringe, self.check_cutoff

        def _dsp_closed_add(dsp):
            dsp_closed_add(dsp)
            for v in dsp.sub_dsp_nodes.values():
                _dsp_closed_add(v['function'])

        while fringe:
            # Visit the closest available node.
            n = (d, _, (v, sol)) = heappop(fringe)

            if sol.stopper.is_set():
                raise DispatcherAbort(self, "Stop requested.")
            # Skip terminated sub-dispatcher or visited nodes.
            if sol.dsp in dsp_closed or (v is not START and v in sol.dist):
                continue

            dsp_init_add(sol.dsp)  # Update initialized dispatcher sets.

            pipe_append(n)  # Add node to the pipe.

            # Set and visit nodes.
            if not sol._visit_nodes(v, d, fringe, check_cutoff, self.no_call):
                if self is sol:
                    break  # Reach all targets.
                else:
                    _dsp_closed_add(sol.dsp)  # Terminated sub-dispatcher.

            # See remote link node.
            sol._see_remote_link_node(v, fringe, d, check_dsp)

        if self.rm_unused_nds:  # Remove unused func and sub-dsp nodes.
            self._remove_unused_nodes()

        return self  # Data outputs.

    def get_sub_dsp_from_workflow(self, sources, reverse=False,
                                  add_missing=False, check_inputs=True):
        sub_dsp = self.dsp.get_sub_dsp_from_workflow(
            sources, self.workflow, reverse=reverse, add_missing=add_missing,
            check_inputs=check_inputs
        )

        return sub_dsp  # Return the sub-dispatcher map.

    @property
    def pipe(self):
        return get_full_pipe(self)

    def copy_structure(self, **kwargs):
        sol = self.__class__(
            self.dsp, self.inputs, self.outputs, False, self.cutoff,
            self.inputs_dist, self.no_call, self.rm_unused_nds, self._wait_in,
            self.no_domain, True, self.index, self.stopper
        )
        sol._clean_set()
        it = ['_wildcards', 'inputs', 'inputs_dist']
        it += [k for k, v in kwargs.items() if v]
        for k in it:
            setattr(sol, k, getattr(self, k))
        return sol

    def __deepcopy__(self, memo):
        rv = super(Solution, self).__reduce_ex__(4)
        i = id(self.stopper)
        if i not in memo:
            memo[i] = threading.Event()
        y = _reconstruct(self, rv, 1, memo)
        y._update_methods()
        return y

    def _add_out_dsp_inputs(self):
        # Nodes that are out of the dispatcher nodes.
        o = sorted(set(self.inputs).difference(self.nodes))

        # Add nodes that are out of the dispatcher nodes.
        if self.no_call:
            self.update(OrderedDict.fromkeys(o, None))
        else:
            self.update(OrderedDict((k, self.inputs[k]) for k in o))

    def _check_targets(self):
        """
        Returns a function to terminate the ArciDispatch algorithm when all
        targets have been visited.

        :return:
            A function to terminate the ArciDispatch algorithm.
        :rtype: (str) -> bool
        """

        if self.outputs:

            targets = self.outputs.copy()  # Namespace shortcut for speed.

            def check_targets(node_id):
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
                    targets.remove(node_id)  # Remove visited node.
                    return not targets  # If no targets terminate the algorithm.
                except KeyError:  # The node is not in the targets set.
                    return False
        else:
            # noinspection PyUnusedLocal
            def check_targets(node_id):
                return False

        return check_targets  # Return the function.

    def _check_cutoff(self):
        """
        Returns a function to stop the search of the investigated node of the
        ArciDispatch algorithm.

        :return:
            A function to stop the search.
        :rtype: (int | float) -> bool
        """

        if self.cutoff is not None:

            cutoff = self.cutoff  # Namespace shortcut for speed.

            def check_cutoff(distance):
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

                return distance > cutoff  # Check cutoff distance.

        else:  # cutoff is None.
            # noinspection PyUnusedLocal
            def check_cutoff(distance):
                return False

        return check_cutoff  # Return the function.

    def _check_wait_input_flag(self):
        """
        Returns a function to stop the search of the investigated node of the
        ArciDispatch algorithm.

        :return:
            A function to stop the search.
        :rtype: (bool, str) -> bool
        """

        wf_pred = self._wf_pred  # Namespace shortcuts.
        pred = {k: set(v).issubset for k, v in self._pred.items()}

        if self._wait_in:
            we = self._wait_in.get  # Namespace shortcut.

            def check_wait_input_flag(wait_in, n_id):
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

                # Return true if the node inputs are satisfied.
                if we(n_id, wait_in):
                    return not pred[n_id](wf_pred[n_id])
                return False

        else:
            def check_wait_input_flag(wait_in, n_id):
                # Return true if the node inputs are satisfied.
                return wait_in and not pred[n_id](wf_pred[n_id])

        return check_wait_input_flag  # Return the function.

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
        estimations = self._wf_pred[node_id]

        wait_in = node_attr['wait_inputs']  # Namespace shortcut.

        # Check if node has multiple estimations and it is not waiting inputs.
        if len(estimations) > 1 and not self._wait_in.get(node_id, wait_in):
            # Namespace shortcuts.
            dist, edg_length, edg = self.dist, self._edge_length, self.dmap.edge

            est = []  # Estimations' heap.

            for k, v in estimations.items():  # Calculate length.
                if k is not START:
                    d = dist[k] + edg_length(edg[k][node_id], node_attr)
                    heappush(est, (d, k, v))

            # The estimation with minimum distance from the starting node.
            estimations = {est[0][1]: est[0][2]}

            # Remove unused workflow edges.
            self.workflow.remove_edges_from([(v[1], node_id) for v in est[1:]])

        return estimations, wait_in  # Return estimations and wait_inputs flag.

    def _remove_wait_in(self):

        l = _sort_sk_wait_in(self)
        n_d = set()

        for d, k, _, w in l:
            if d == l[0][0]:
                w[k] = False
                if w is self._wait_in:
                    n_d.add(k)
        return n_d, l

    def _set_node_output(self, node_id, no_call, next_nds=None):
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
            return self._set_data_node_output(node_id, node_attr, no_call,
                                              next_nds)

        elif node_type == 'function':  # Set function node.
            return self._set_function_node_output(node_id, node_attr, no_call,
                                                  next_nds)

    def _set_data_node_output(self, node_id, node_attr, no_call, next_nds=None):
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

        if not no_call:
            if node_id is PLOT:
                est = est.copy()
                est[PLOT] = {'value': {'obj': self}}
            # Final estimation of the node and node status.
            if not wait_in:

                if 'function' in node_attr:  # Evaluate output.
                    try:
                        kwargs = {k: v['value'] for k, v in est.items()}
                        # noinspection PyCallingNonCallable
                        value = node_attr['function'](kwargs)
                    except Exception as ex:
                        # Some error occurs.
                        msg = "Failed DISPATCHING '%s' due to:\n  %r"
                        self._warning(msg, node_id, ex)
                        return False
                else:
                    # Data node that has just one estimation value.
                    value = list(est.values())[0]['value']

            else:  # Use the estimation function of node.
                try:
                    # Dict of all data node estimations.
                    kwargs = {k: v['value'] for k, v in est.items()}

                    # noinspection PyCallingNonCallable
                    value = node_attr['function'](kwargs)  # Evaluate output.
                except Exception as ex:
                    # Is missing estimation function of data node or some error.
                    msg = "Failed DISPATCHING '%s' due to:\n  %r"
                    self._warning(msg, node_id, ex)
                    return False
            try:
                # Apply filters to output.
                for f in node_attr.get('filters', ()):
                    value = f(value)
            except Exception as ex:
                # Some error occurs.
                msg = "Failed DISPATCHING '%s' due to:\n  %r"
                self._warning(msg, node_id, ex)
                return False

            if value is not NONE:  # Set data output.
                self[node_id] = value

            if 'callback' in node_attr:  # Invoke callback func of data node.
                try:
                    # noinspection PyCallingNonCallable
                    node_attr['callback'](value)
                except Exception as ex:
                    msg = "Failed CALLBACKING '%s' due to:\n  %s"
                    self._warning(msg, node_id, ex)

            value = {'value': value}  # Output value.
        else:
            self[node_id] = NONE  # Set data output.

            value = {}  # Output value.

        if next_nds:
            # namespace shortcuts for speed.
            wf_add_edge = self._wf_add_edge

            for u in next_nds:  # Set workflow.
                wf_add_edge(node_id, u, **value)

        else:
            # namespace shortcuts for speed.
            n, has, sub_dsp = self.nodes, self.workflow.has_edge, self.sub_dsp

            def no_visited_in_sub_dsp(i):
                node = n[i]
                if node['type'] == 'dispatcher' and has(i, node_id):
                    visited = sub_dsp[node['function']]._visited
                    return node['inputs'][node_id] not in visited
                return True

            # List of functions.
            succ_fun = [u for u in self._succ[node_id]
                        if no_visited_in_sub_dsp(u)]

            # Check if it has functions as outputs and wildcard condition.
            if succ_fun and succ_fun[0] not in self._visited:
                # namespace shortcuts for speed.
                wf_add_edge = self._wf_add_edge

                for u in succ_fun:  # Set workflow.
                    wf_add_edge(node_id, u, **value)

        return True  # Return that the output have been evaluated correctly.

    def _set_function_node_output(self, node_id, node_attr, no_call,
                                  next_nds=None):
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
        output_nodes = next_nds or set(self._succ[node_id]).difference(dist)

        if not output_nodes:  # This function is not needed.
            self.workflow.remove_node(node_id)  # Remove function node.
            return False

        wf_add_edge = self._wf_add_edge  # Namespace shortcuts for speed.

        if no_call:
            for u in output_nodes:  # Set workflow out.
                wf_add_edge(node_id, u)
            return True

        args = self._wf_pred[node_id]  # List of the function's arguments.
        args = [args[k]['value'] for k in node_attr['inputs']]
        args = [v for v in args if v is not NONE]

        attr = {'started': datetime.today()}
        try:
            # noinspection PyCallingNonCallable
            if not self.no_domain and 'input_domain' in node_attr and \
                    not node_attr['input_domain'](*args):
                return False  # Args are not respecting the domain.
            else:  # Use the estimation function of node.
                fun = node_attr['function']

                if isinstance(parent_func(fun), SubDispatch):
                    res = fun(*args, _sol_output=attr,
                              _sol_stopper=self.stopper)
                else:
                    res = fun(*args)

                # Apply filters to results.
                for f in node_attr.get('filters', ()):
                    res = f(res)

                attr['duration'] = datetime.today() - attr['started']

                # Save node.
                self.workflow.add_node(node_id, **attr)

                # List of function results.
                res = res if len(o_nds) > 1 else [res]

        except Exception as ex:
            if isinstance(ex, DispatcherError):  # Save intermediate results.
                attr['duration'] = datetime.today() - attr['started']

                # Save node.
                self.workflow.add_node(node_id, **attr)
            # Is missing function of the node or args are not in the domain.
            msg = "Failed DISPATCHING '%s' due to:\n  %r"
            self._warning(msg, node_id, ex)
            return False

        for k, v in zip(o_nds, res):  # Set workflow.
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
        wf_remove_edge, check_wait_in = self._wf_remove_edge, self.check_wait_in
        wf_add_edge, dsp_in = self._wf_add_edge, self._set_sub_dsp_node_input
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

                vd = (True, w, self.index + node['index'])  # Virtual distance.

                heappush(fringe, (vw_dist, vd, (w, self)))  # Add to heapq.

            return True

        update_view(data_id, initial_dist)  # Update view distance.

        if check_cutoff(initial_dist):  # Check the cutoff limit.
            wf_remove_edge(START, data_id)  # Remove workflow edge.
        elif not check_wait_in(wait_in, data_id):  # Check inputs.
            seen[data_id] = initial_dist  # Update distance.

            vd = (wait_in, data_id, self.index + index)  # Virtual distance.

            # Add node to heapq.
            heappush(fringe, (initial_dist, vd, (data_id, self)))

            return True
        return False

    def _update_meeting(self, node_id, dist):
        """

        :param node_id:
        :param dist:
        :return:
        """
        view = self._meet
        if node_id in self._meet:
            view[node_id] = max(dist, view[node_id])
        else:
            view[node_id] = dist

    def _visit_nodes(self, node_id, dist, fringe, check_cutoff, no_call=False):
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
        wf_rm_edge, wf_has_edge = self._wf_remove_edge, self.workflow.has_edge
        edge_weight, nodes = self._edge_length, self.nodes

        self.dist[node_id] = dist  # Set minimum dist.

        self._visited.add(node_id)  # Update visited nodes.

        if not self._set_node_output(node_id, no_call):  # Set node output.
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
                raise DispatcherError(self, 'Contradictory paths found: '
                                            'negative weights?')
        elif node_id not in seen or dist < seen[node_id]:  # Check min dist.
            seen[node_id] = dist  # Update dist.

            index = self.nodes[node_id]['index']  # Node index.

            # Virtual distance.
            vd = (w_wait_in + int(wait_in), node_id, self.index + index)

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
        for n in (set(self._wf_pred) - set(self._visited)):
            node_type = nodes[n]['type']  # Node type.

            if node_type == 'data':
                continue  # Skip data node.

            if node_type == 'dispatcher' and succ[n]:
                add_visited(n)  # Add to visited nodes.
                self.sub_dsp[nodes[n]['function']]._remove_unused_nodes()
                continue  # Skip sub-dispatcher node with outputs.

            wf_remove_node(n)  # Remove unused node.

    def _init_sub_dsp(self, dsp, fringe, outputs, no_call, initial_dist, index):
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
            stopper=self.stopper
        )

        sol.sub_dsp = self.sub_dsp

        for f in sol.fringe:  # Update the fringe.
            heappush(fringe, (initial_dist + f[0], (2,) + f[1][1:], f[-1]))

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

        node = self.nodes[node_id]  # Namespace shortcut.

        if node['type'] == 'data' and 'remote_links' in node:
            value = self[node_id]  # Get data output.

            for (dsp_id, dsp), type in node['remote_links']:
                if 'child' == type and check_dsp(dsp):
                    # Get node id of remote sub-dispatcher.
                    sol = self.sub_dsp[dsp]
                    for n_id in stlp(dsp.nodes[dsp_id]['outputs'][node_id]):
                        b = n_id in sol._visited  # Node has been visited.

                        # Input do not coincide with the output.
                        if not (b or sol.workflow.has_edge(n_id, dsp_id)):
                            # Donate the result to the child.
                            sol._wf_add_edge(dsp_id, n_id, value=value)
                            if fringe is not None:
                                # See node.
                                sol._see_node(n_id, fringe, dist, w_wait_in=2)

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
        dsp, pred = node['function'], self._wf_pred[dsp_id]
        distances, sub_dsp = self.dist, self.sub_dsp

        iv_nodes = [node_id]  # Nodes do be added as initial values.

        self._meet[dsp_id] = initial_dist  # Set view distance.

        # Check if inputs are satisfied.
        if self.check_wait_in(node['wait_inputs'], dsp_id):
            return False  # Pass the node

        if dsp_id not in distances:
            if 'input_domain' in node and not (self.no_domain or self.no_call):
                # noinspection PyBroadException
                try:
                    kwargs = {k: v['value'] for k, v in pred.items()}

                    if not node['input_domain'](kwargs):
                        return False  # Args are not respecting the domain.
                    else:
                        iv_nodes = pred  # Args respect the domain.
                except:
                    return False  # Some error occurs.

            # Initialize the sub-dispatcher.
            sub_dsp[dsp] = sol = self._init_sub_dsp(
                dsp, fringe, node['outputs'], no_call, initial_dist,
                node['index']
            )
            self.workflow.add_node(dsp_id, solution=sol)

            distances[dsp_id] = initial_dist  # Update min distance.
        else:
            sol = sub_dsp[dsp]

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
           when an error occur, otherwise it logs a warning.
        """

        self._errors[node_id] = msg % ((node_id, ex) + args)

        node_id = ','.join(self.dsp.get_full_node_id(node_id))

        if self.raises:
            raise DispatcherError(self, msg, node_id, ex, *args, **kwargs)
        elif isinstance(ex, DispatcherAbort):
            raise
        else:
            kwargs['exc_info'] = kwargs.get('exc_info', 1)
            log.error(msg, node_id, ex, *args, **kwargs)

    def get_node(self, *node_ids, node_attr='output'):
        """
        Returns a sub node of a solution.

        :param node_ids:
            A sequence of node ids or a single node id. The id order identifies
            a dispatcher sub-level.
        :type node_ids: str

        :param node_attr:
            Output node attr.

            If the searched node does not have this attribute, all its
            attributes are returned.

            When 'auto', returns the "default" attributes of the searched node,
            which are:

              - for data node: its output, and if not exists, all its
                attributes.
              - for function and sub-dispatcher nodes: the 'function' attribute.

            When 'description', returns the "description" of the searched node,
            searching also in function or sub-dispatcher input/output
            description.

            When 'output', returns the data node output.

            When 'default_value', returns the data node default value.

            When 'value_type', returns the data node value's type.

            When `None`, returns the node attributes.
        :type node_attr: str, None, optional

        :return:
            Node attributes and its real path.
        :rtype: (T, (str, ...))

        **Example**:

        .. dispatcher:: dsp
           :opt: workflow=True, graph_attr={'ratio': '1'}, depth=1

            >>> from co2mpas.dispatcher import Dispatcher
            >>> s_dsp = Dispatcher(name='Sub-dispatcher')
            >>> def fun(a, b):
            ...     return a + b
            ...
            >>> s_dsp.add_function('a + b', fun, ['a', 'b'], ['c'])
            'a + b'
            >>> dispatch = SubDispatch(s_dsp, ['c'], output_type='dict')
            >>> dsp = Dispatcher(name='Dispatcher')
            >>> dsp.add_function('Sub-dispatcher', dispatch, ['a'], ['b'])
            'Sub-dispatcher'

            >>> o = dsp.dispatch(inputs={'a': {'a': 3, 'b': 1}})
            ...

        Get the sub node output::

            >>> dsp.get_node('Sub-dispatcher', 'c')
            (4, ('Sub-dispatcher', 'c'))
            >>> dsp.get_node('Sub-dispatcher', 'c', node_attr='type')
            ('data', ('Sub-dispatcher', 'c'))

        .. dispatcher:: sub_dsp
           :opt: workflow=True, graph_attr={'ratio': '1'}, depth=0
           :code:

            >>> sub_dsp, sub_dsp_id = dsp.get_node('Sub-dispatcher')
        """

        # Returns the node.
        return get_sub_node(self.dsp, node_ids, node_attr, self)

    def plot(self, workflow=True, view=True, nested=True, edge_data=(),
             node_data=(), node_function=(), draw_outputs=0, node_styles=None,
             depth=-1, function_module=False, name=None, comment=None,
             directory=None, filename=None, format='svg', engine=None,
             encoding=None, graph_attr=None, node_attr=None, edge_attr=None,
             body=None):
        """
        Plots the Dispatcher with a graph in the DOT language with Graphviz.

        :param workflow:
           If True the latest solution will be plotted, otherwise the dmap.
        :type workflow: bool, optional

        :param view:
            Open the rendered directed graph in the DOT language with the sys
            default opener.
        :type view: bool, optional

        :param nested:
            If False the sub-dispatcher nodes are plotted on the same graph,
            otherwise they can be viewed clicking on the node that has an URL
            link.
        :type nested: bool, optional

        :param edge_data:
            Edge attributes to view.
        :type edge_data: tuple[str], optional

        :param node_data:
            Data node attributes to view.
        :type node_data: tuple[str], optional

        :param node_function:
            Function node attributes to view.
        :type node_function: tuple[str], optional

        :param draw_outputs:
            It modifies the defaults data node and edge attributes to view.
            If `draw_outputs` is:

                - 1: node attribute 'output' is drawn.
                - 2: edge attribute 'value' is drawn.
                - 3: node 'output' and edge 'value' attributes are drawn.
                - otherwise: node 'output' and edge 'value' attributes are not
                  drawn.
        :type draw_outputs: int, optional

        :param node_styles:
            Default node styles according to graphviz node attributes.
        :type node_styles: dict[str|Token, dict[str, str]]

        :param depth:
            Depth of sub-dispatch plots. If negative all levels are plotted.
        :type depth: int, optional

        :param function_module:
            If True the function labels are plotted with the function module,
            otherwise only the function name will be visible.
        :type function_module: bool, optional

        :param name:
            Graph name used in the source code.
        :type name: str

        :param comment:
            Comment added to the first line of the source.
        :type comment: str

        :param directory:
            (Sub)directory for source saving and rendering.
        :type directory: str, optional

        :param filename:
            File name for saving the source.
        :type filename: str, optional

        :param format:
            Rendering output format ('pdf', 'png', ...).
        :type format: str, optional

        :param engine:
            Layout command used ('dot', 'neato', ...).
        :type engine: str, optional

        :param encoding:
            Encoding for saving the source.
        :type encoding: str, optional

        :param graph_attr:
            Dict of (attribute, value) pairs for the graph.
        :type graph_attr: dict, optional

        :param node_attr:
            Dict of (attribute, value) pairs set for all nodes.
        :type node_attr: dict, optional

        :param edge_attr:
            Dict of (attribute, value) pairs set for all edges.
        :type edge_attr: dict, optional

        :param body:
            Dict of (attribute, value) pairs to add to the graph body.
        :type body: dict, optional

        :return:
            A directed graph source code in the DOT language.
        :rtype: graphviz.dot.Digraph

        Example:

        .. dispatcher:: dsp
           :opt: graph_attr={'ratio': '1'}
           :code:

            >>> from co2mpas.dispatcher import Dispatcher
            >>> dsp = Dispatcher(name='Dispatcher')
            >>> def fun(a):
            ...     return a + 1, a - 1
            >>> dsp.add_function('fun', fun, ['a'], ['b', 'c'])
            'fun'
            >>> dsp.plot(view=False, graph_attr={'ratio': '1'})
            <co2mpas.dispatcher.utils.drw.DspPlot object at 0x...>
        """

        from .drw import DspPlot
        dot = DspPlot(
            obj=self, workflow=workflow, nested=nested, view=view,
            edge_data=edge_data, node_data=node_data, draw_outputs=draw_outputs,
            node_function=node_function, depth=depth, node_styles=node_styles,
            function_module=function_module, name=name, comment=comment,
            directory=directory, filename=filename, format=format,
            engine=engine, encoding=encoding, graph_attr=graph_attr,
            node_attr=node_attr, edge_attr=edge_attr, body=body
        )

        return dot
