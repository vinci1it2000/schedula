from distutils.core import setup

setup(
    name='dispatcher',
    version='0.0.1',
    packages=['', 'doc', 'tests', 'dispatcher'],
    url='',
    license='',
    author='Vincenzo Arcidiacono',
    author_email='vinci1it2000@gmail.com',
    description='A dispatch function calls.',
    requires=[
        'networkx',
        'matplotlib',
        'dill',
        'graphviz'
    ]
)
