Changelog
=========


v1.2.9 (2021-10-05)
-------------------

Feat
~~~~
- (drw): Add option to reduce length of file names.


Fix
~~~
- (setup): Correct supported python versions.

- (doc): Correct typos.


v1.2.8 (2021-05-31)
-------------------

Fix
~~~
- (doc): Skip KeyError when searching descriptions.


v1.2.7 (2021-05-19)
-------------------

Feat
~~~~
- (travis): Remove python 3.6 and add python 3.9 from text matrix.


Fix
~~~
- (sphinx): Add missing attribute.

- (sphinx): Update option parser.

- (doc): Update some documentation.

- (test): Correct test case missing library.


v1.2.6 (2021-02-09)
-------------------

Feat
~~~~
- (sol): Improve performances.


Fix
~~~
- (des): Correct description error due to `MapDispatch`.

- (drw): Correct `index` plotting.


v1.2.5 (2021-01-17)
-------------------

Fix
~~~
- (core): Update copyright.

- (drw): Correct viz rendering.


v1.2.4 (2020-12-12)
-------------------

Fix
~~~
- (drw): Correct plot auto-opening.


v1.2.3 (2020-12-11)
-------------------

Feat
~~~~
- (drw): Add plot option to use viz.js as back-end.


Fix
~~~
- (setup): Add missing requirement `requests`.


v1.2.2 (2020-11-30)
-------------------

Feat
~~~~
- (dsp): Add custom formatters for `MapDispatch` class.


v1.2.1 (2020-11-04)
-------------------

Feat
~~~~
- (dsp): Add `MapDispatch` class.

- (core): Add execution function log.


Fix
~~~
- (rtd): Correct documentation rendering in `rtd`.

- (autosumary): Correct bug for `AutosummaryEntry`.


v1.2.0 (2020-04-08)
-------------------

Feat
~~~~
- (dispatcher): Avoid failure when functions does not have the name.

- (ubuild): Add compiled and not compiled code.

- (sol): Improve speed importing functions directly for `heappop` and
  `heappush`.

- (dispatcher): Avoid failure when functions does not have the name.

- (dsp): Simplify repr of inf numbers.

- (micropython): Pin specific MicroPython version `v1.12`.

- (micropython): Add test using `.mpy` files.

- (setup): Add `MicroPython` support.

- (setup): Drop `dill` dependency and add `io` extra.

- (github): Add pull request templates.


Fix
~~~
- (test): Skip micropython tests.

- (ext): Update code for sphinx 3.0.0.

- (sphinx): Remove documentation warnings.

- (utils): Drop unused `pairwise` function.

- (dsp): Avoid fringe increment in `SubDispatchPipe`.


v1.1.1 (2020-03-12)
-------------------

Feat
~~~~
- (github): Add issue templates.

- (exc): Add base exception to `DispatcherError`.

- (build): Update build script.


v1.1.0 (2020-03-05)
-------------------

Feat
~~~~
- (core): Drop `networkx` dependency.

- (core): Add `ProcessPoolExecutor`.

- (asy): Add `ExecutorFactory` class.

- (asy): Split `asy` module.

- (core): Add support for python 3.8 and drop python 3.5.

- (asy): Check if `stopper` is set when getting executor.

- (asy): Add `mp_context` option in `ProcessExecutor` and
  `ProcessPoolExecutor`.


Fix
~~~
- (alg): Correct pipe generation when `NoSub` found.

- (asy): Remove un-useful and dangerous states before serialization.

- (asy): Ensure wait of all executor futures.

- (asy): Correct bug when future is set.

- (asy): Correct init and shutdown of executors.

- (sol): Correct raise exception order in `sol.result`.

- (travis): Correct tests collector.

- (test): Correct test for multiple async.


v1.0.0 (2020-01-02)
-------------------

Feat
~~~~
- (doc): Add code of conduct.

- (examples): Add new example + formatting.

- (sol): New `raises` option, if raises='' no warning logs.

- (web): Add query param `data` to include/exclude data into the server
  JSON response.

- (sphinx): Update dispatcher documenter and directive.

- (drw): Add wildcard rendering.


Fix
~~~
- (test): Update test cases.

- (dsp): Correct pipe extraction for wildcards.

- (setup): Add missing `drw` files.


v0.3.7 (2019-12-06)
-------------------

Feat
~~~~
- (drw): Update the `index` GUI of the plot.

- (appveyor): Drop `appveyor` in favor of `travis`.

- (travis): Update travis configuration file.

- (plot): Add node link and id in graph plot.


Fix
~~~
- (drw): Render dot in temp folder.

- (plot): Add `quiet` arg to `_view` method.

- (doc): Correct missing gh links.

- (core) :gh:`17`: Correct deprecated Graph attribute.


v0.3.6 (2019-10-18)
-------------------

Fix
~~~
- (setup) :gh:`17`: Update version networkx.

- (setup) :gh:`13`: Build universal wheel.

- (alg) :gh:`15`: Escape % in node id.

- (setup) :gh:`14`: Update tests requirements.

- (setup): Add env `ENABLE_SETUP_LONG_DESCRIPTION`.


v0.3.4 (2019-07-15)
-------------------

Feat
~~~~
- (binder): Add `@jupyterlab/plotly-extension`.

- (binder): Customize `Site._repr_html_` with env
  `SCHEDULA_SITE_REPR_HTML`.

- (binder): Add `jupyter-server-proxy`.

- (doc): Add binder examples.

- (gen): Create super-class of `Token`.

- (dsp): Improve error message.


Fix
~~~
- (binder): Simplify `processing_chain` example.

- (setup): Exclude `binder` and `examples` folders as packages.

- (doc): Correct binder data.

- (doc): Update examples for binder.

- (doc): Add missing requirements binder.

- (test): Add `state` to fake directive.

- (import): Remove stub file to enable autocomplete.

- Update to canonical pypi name of beautifulsoup4.


v0.3.3 (2019-04-02)
-------------------

Feat
~~~~
- (dispatcher): Improve error message.


Fix
~~~
- (doc): Correct bug for sphinx AutoDirective.

- (dsp): Add dsp as kwargs for a new Blueprint.

- (doc): Update PEP and copyright.


v0.3.2 (2019-02-23)
-------------------

Feat
~~~~
- (core): Add stub file.

- (sphinx): Add Blueprint in Dispatcher documenter.

- (sphinx): Add BlueDispatcher in documenter.

- (doc): Add examples.

- (blue): Customizable memo registration of blueprints.


Fix
~~~
- (sphinx): Correct bug when `"` is in csv-table directive.

- (core): Set module attribute when `__getattr__` is invoked.

- (doc): Correct utils description.

- (setup): Improve keywords.

- (drw): Correct tooltip string format.

- (version): Correct import.


v0.3.1 (2018-12-10)
-------------------

Fix
~~~
- (setup): Correct long description for pypi.

- (dsp): Correct bug `DispatchPipe` when dill.


v0.3.0 (2018-12-08)
-------------------

Feat
~~~~
- (blue, dispatcher): Add method `extend` to extend Dispatcher or
  Blueprint with Dispatchers or Blueprints.

- (blue, dsp): Add `BlueDispatcher` class + remove `DFun` util.

- (core): Remove `weight` attribute from `Dispatcher` struc.

- (dispatcher): Add method `add_func` to `Dispatcher`.

- (core): Remove `remote_links` attribute from dispatcher data nodes.

- (core): Implement callable raise option in `Dispatcher`.

- (core): Add feature to dispatch asynchronously and in parallel.

- (setup): Add python 3.7.

- (dsp): Use the same `dsp.solution` class in `SubDispatch` functions.


Fix
~~~
- (dsp): Do not copy solution when call `DispatchPipe`, but reset
  solution when copying the obj.

- (alg): Correct and clean `get_sub_dsp_from_workflow` algorithm.

- (sol): Ensure `bool` output from `input_domain` call.

- (dsp): Parse arg and kw using `SubDispatchFunction.__signature__`.

- (core): Do not support python 3.4.

- (asy): Do not dill the Dispatcher solution.

- (dispatcher): Correct bug in removing remote links.

- (core): Simplify and correct Exception handling.

- (dsp): Postpone `__signature__` evaluation in `add_args`.

- (gen): Make Token constant when pickled.

- (sol): Move callback invocation in `_evaluate_node`.

- (core) :gh:`11`: Lazy import of modules.

- (sphinx): Remove warnings.

- (dsp): Add missing `code` option in `add_function` decorator.


Other
~~~~~
- Refact: Update documentation.


v0.2.8 (2018-10-09)
-------------------

Feat
~~~~
- (dsp): Add inf class to model infinite numbers.


v0.2.7 (2018-09-13)
-------------------

Fix
~~~
- (setup): Correct bug when `long_description` fails.


v0.2.6 (2018-09-13)
-------------------

Feat
~~~~
- (setup): Patch to use `sphinxcontrib.restbuilder` in setup
  `long_description`.


v0.2.5 (2018-09-13)
-------------------

Fix
~~~
- (doc): Correct link docs_status.

- (setup): Use text instead rst to compile `long_description` + add
  logging.


v0.2.4 (2018-09-13)
-------------------

Fix
~~~
- (sphinx): Correct bug sphinx==1.8.0.

- (sphinx): Remove all sphinx warnings.


v0.2.3 (2018-08-02)
-------------------

Fix
~~~
- (des): Correct bug when SubDispatchFunction have no `outputs`.


v0.2.2 (2018-08-02)
-------------------

Fix
~~~
- (des): Correct bug of get_id when tuple ids nodes are given as input
  or outputs of a sub_dsp.

- (des): Correct bug when tuple ids are given as `inputs` or `outputs`
  of `add_dispatcher` method.


v0.2.1 (2018-07-24)
-------------------

Feat
~~~~
- (setup): Update `Development Status` to `5 - Production/Stable`.

- (setup): Add additional project_urls.

- (doc): Add changelog to rtd.


Fix
~~~
- (doc): Correct link docs_status.

- (des): Correct bugs get_des.


v0.2.0 (2018-07-19)
-------------------

Feat
~~~~
- (doc): Add changelog.

- (travis): Test extras.

- (des): Avoid using sphinx for `getargspec`.

- (setup): Add extras_require to setup file.


Fix
~~~
- (setup): Correct bug in `get_long_description`.


v0.1.19 (2018-06-05)
--------------------

Fix
~~~
- (dsp): Add missing content block in note directive.

- (drw): Make sure to plot same sol as function and as node.

- (drw): Correct format of started attribute.


v0.1.18 (2018-05-28)
--------------------

Feat
~~~~
- (dsp): Add `DispatchPipe` class (faster pipe execution, it overwrite
  the existing solution).

- (core): Improve performances replacing `datetime.today()` with
  `time.time()`.


v0.1.17 (2018-05-18)
--------------------

Feat
~~~~
- (travis): Run coveralls in python 3.6.


Fix
~~~
- (web): Skip Flask logging for the doctest.

- (ext.dispatcher): Update to the latest Sphinx 1.7.4.

- (des): Use the proper dependency (i.e., `sphinx.util.inspect`) for
  `getargspec`.

- (drw): Set socket option to reuse the address (host:port).

- (setup): Correct dill requirements `dill>=0.2.7.1` --> `dill!=0.2.7`.


v0.1.16 (2017-09-26)
--------------------

Fix
~~~
- (requirements): Update dill requirements.


v0.1.15 (2017-09-26)
--------------------

Fix
~~~
- (networkx): Update according to networkx 2.0.


v0.1.14 (2017-07-11)
--------------------

Fix
~~~
- (io): pin dill version <=0.2.6.

- (abort): abort was setting Exception.args instead of `sol` attribute.


Other
~~~~~
- Merge pull request :gh:`9` from ankostis/fixabortex.


v0.1.13 (2017-06-26)
--------------------

Feat
~~~~
- (appveyor): Add python 3.6.


Fix
~~~
- (install): Force update setuptools>=36.0.1.

- (exc): Do not catch KeyboardInterrupt exception.

- (doc) :gh:`7`: Catch exception for sphinx 1.6.2 (listeners are moved
  in EventManager).

- (test): Skip empty error message.


v0.1.12 (2017-05-04)
--------------------

Fix
~~~
- (drw): Catch dot error and log it.


v0.1.11 (2017-05-04)
--------------------

Feat
~~~~
- (dsp): Add `add_function` decorator to add a function to a dsp.

- (dispatcher) :gh:`4`: Use `kk_dict` function to parse inputs and
  outputs of `add_dispatcher` method.

- (dsp) :gh:`4`: Add `kk_dict` function.


Fix
~~~
- (doc): Replace type function with callable.

- (drw): Folder name without ext.

- (test): Avoid Documentation of DspPlot.

- (doc): fix docstrings types.


v0.1.10 (2017-04-03)
--------------------

Feat
~~~~
- (sol): Close sub-dispatcher solution when all outputs are satisfied.


Fix
~~~
- (drw): Log error when dot is not able to render a graph.


v0.1.9 (2017-02-09)
-------------------

Fix
~~~
- (appveyor): Setup of lmxl.

- (drw): Update plot index.


v0.1.8 (2017-02-09)
-------------------

Feat
~~~~
- (drw): Update plot index + function code highlight + correct plot
  outputs.


v0.1.7 (2017-02-08)
-------------------

Fix
~~~
- (setup): Add missing package_data.


v0.1.6 (2017-02-08)
-------------------

Fix
~~~
- (setup): Avoid setup failure due to get_long_description.

- (drw): Avoid to plot unneeded weight edges.

- (dispatcher): get_sub_dsp_from_workflow set correctly the remote
  links.


v0.1.5 (2017-02-06)
-------------------

Feat
~~~~
- (exl): Drop exl module because of formulas.

- (sol): Add input value of filters in solution.


Fix
~~~
- (drw): Plot just one time the filer attribute in workflow
  `+filers|solution_filters` .


v0.1.4 (2017-01-31)
-------------------

Feat
~~~~
- (drw): Save autoplot output.

- (sol): Add filters and function solutions to the workflow nodes.

- (drw): Add filters to the plot node.


Fix
~~~
- (dispatcher): Add missing function data inputs edge representation.

- (sol): Correct value when apply filters on setting the node output.

- (core): get_sub_dsp_from_workflow blockers can be applied to the
  sources.


v0.1.3 (2017-01-29)
-------------------

Fix
~~~
- (dsp): Raise a DispatcherError when the pipe workflow is not respected
  instead KeyError.

- (dsp): Unresolved references.


v0.1.2 (2017-01-28)
-------------------

Feat
~~~~
- (dsp): add_args  _set_doc.

- (dsp): Remove parse_args class.

- (readme): Appveyor badge status == master.

- (dsp): Add _format option to `get_unused_node_id`.

- (dsp): Add wildcard option to `SubDispatchFunction` and
  `SubDispatchPipe`.

- (drw): Create sub-package drw.

Fix
~~~
- (dsp): combine nested dicts with different length.

- (dsp): are_in_nested_dicts return false if nested_dict is not a dict.

- (sol): Remove defaults when setting wildcards.

- (drw): Misspelling `outpus` --> `outputs`.

- (directive): Add exception on graphviz patch for sphinx 1.3.5.


v0.1.1 (2017-01-21)
-------------------

Fix
~~~
- (site): Fix ResourceWarning: unclosed socket.

- (setup): Not log sphinx warnings for long_description.

- (travis): Wait util the server is up.

- (rtd): Missing requirement dill.

- (travis): Install first - pip install -r dev-requirements.txt.

- (directive): Tagname from _img to img.

- (directive): Update minimum sphinx version.

- (readme): Badge svg links.


Other
~~~~~
- Add project descriptions.

- (directive): Rename schedula.ext.dsp_directive --> schedula.ext.dispatcher.

- Update minimum sphinx version and requests.

