def dict_diff(adict: dict, excluded: set) -> dict:
    if excluded:
        return {k: v for k, v in adict.items() if k not in excluded}
    return adict.copy()


def select_diff(adict: dict, excluded: set, key: str) -> dict:
    if excluded:
        return {k: v[key] for k, v in adict.items() if k not in excluded}
    return {k: v[key] for k, v in adict.items()}


def get_unused_node_id(graph, initial_guess='unknown', _format='{}<%d>'):
    """
    Finds an unused node id in `graph`.

    :param graph:
        A directed graph.
    :type graph: schedula.utils.graph.DiGraph

    :param initial_guess:
        Initial node id guess.
    :type initial_guess: str, optional

    :param _format:
        Format to generate the new node id if the given is already used.
    :type _format: str, optional

    :return:
        An unused node id.
    :rtype: str
    """

    nodes = graph.nodes  # Namespace shortcut for speed.
    node_id = initial_guess  # Initial guess.
    if node_id in nodes:
        n = 0  # Counter.
        id_fmt = _format.format(node_id.replace('%', '%%'))  # Node id format.
        node_id = id_fmt % n  # Guess.
        while node_id in nodes:  # Check if node id is used.
            n += 1
            node_id = id_fmt % n

    return node_id  # Returns an unused node id.
