from .graphviz import setup as setup_graphviz
from .documenter import setup as setup_documenter, PLOT


def setup(app):
    setup_graphviz(app)
    setup_documenter(app)
