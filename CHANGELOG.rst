Changelog
=========


v1.5.29 (2024-09-24)
--------------------

Fix
~~~
- (form): Correct fetch origin on startup.


v1.5.28 (2024-09-23)
--------------------

Feat
~~~~
- (form): Update resources.

- (form): Use also metadata instead of only product features for credits
  behaviour.

- (form): Change html title from json.


Fix
~~~
- (form): Improve Lock credits.

- (form): Correct Cookies behaviour.

- (core): Correct logic and performances of module imports.


v1.5.27 (2024-09-16)
--------------------

Feat
~~~~
- (form): Update resources.


Fix
~~~
- (form): Improve cache control.


v1.5.26 (2024-09-14)
--------------------

Fix
~~~
- (form): Add missing import.

- (setup): Add missing files.


v1.5.25 (2024-09-13)
--------------------

Feat
~~~~
- (form): Update resources.

- (form): Add form and render objects to Plasmic components.

- (form): Correct locale handling.


Fix
~~~
- (form): Update contact logic.


v1.5.24 (2024-09-12)
--------------------

Feat
~~~~
- (form): Update resources.


Fix
~~~
- (form): Correct error message for cascader.


v1.5.23 (2024-09-09)
--------------------

Feat
~~~~
- (form): Update resources.

- (form): Add configurable `send_static_file` function.

- (form): Add extra block in html template.

- (form): Improve passwords layout.

- (form): Make error notification optional in postData.

- (form): Add event emitter.


v1.5.22 (2024-09-06)
--------------------

Feat
~~~~
- (core): Make verbose customizable.

- (from): Improve DB code.


v1.5.21 (2024-09-04)
--------------------

Feat
~~~~
- (from, web, drw): Add method `init_app`.


v1.5.20 (2024-09-04)
--------------------

Feat
~~~~
- (form): Update resources.

- (form): Make contact mail usable outside app context.


Fix
~~~
- (setup): Add missing requirements.

- (doc): Correct Sphinx import error.

- (form): Correct bug in App component.


v1.5.19 (2024-09-02)
--------------------

Feat
~~~~
- (form): Update resources.


Fix
~~~
- (form): Correct app default page.

- (form): Correct App menu.

- (form): Correct flashing messages for html requests.

- (form): Add missing link in template.

- (form): Add missing extension.


v1.5.18 (2024-08-30)
--------------------

Feat
~~~~
- (form): Make `Wallet` methods usable without app.


Fix
~~~
- (form): Correct hash calculation of files.


v1.5.17 (2024-08-29)
--------------------

Fix
~~~
- (form): Improve file storage and add `get_file` utility function.

- (form): Ensure to have one wallet per user.

- (setup): Add missing requirements.


v1.5.16 (2024-08-28)
--------------------

Feat
~~~~
- (form): Update resources.

- (form): Update all `FileWidgets`.

- (form): Improve Steps code.

- (form): Update `form.postData` method.

- (form): Add files service.

- (form): Use a shared lock.

- (form): Add all translations.


Fix
~~~
- (form): Update antd translations.

- (setup): Add missing files.


v1.5.15 (2024-08-12)
--------------------

Feat
~~~~
- (form): Make `credits` `db.session` configurable.


Fix
~~~
- (form): Add missing requirements.


v1.5.14 (2024-08-08)
--------------------

Feat
~~~~
- (form): Update resources.

- (form): Improve DB object readability.

- (form): Make username registration optional.


Fix
~~~
- (setup): Correct flask security requirements.

- (form): Correct column size for stripe ids.

- (form): Correct balance query for mysql db.

- (form): Make all configs settable from envs.

- (form): Correct avatar DB type.

- (form): Correct typos.


v1.5.13 (2024-08-09)
--------------------

Feat
~~~~
- (form): Update resources.

- (form): Improve DB object readability.

- (form): Make username registration optional.


Fix
~~~
- (setup): Correct flask security requirements.

- (form): Correct column size for stripe ids.

- (form): Correct balance query for mysql db.

- (form): Make all configs settable from envs.

- (form): Correct avatar DB type.

- (form): Correct typos.


v1.5.13 (2024-08-08)
--------------------

Fix
~~~
- (form): Correct string length for mysql DB.


v1.5.12 (2024-08-08)
--------------------

Fix
~~~
- (form): Correct string length for mysql DB.


v1.5.12 (2024-08-07)
--------------------

Feat
~~~~
- (form): Update resources.

- (form): Add option to disable debug chart API.

- (core): Add new option to handle wildcards.

- (form): Make `static_context` loading dynamically.

- (form): Update `Credits` service.

- (form): Add mode features to Stripe component.

- (form): Apply `dereference` to `uiSchema` like `json-schema`.

- (form): Update Subscription handling and credits.

- (form): Update Stripe Card layout.

- (form): Add Stripe components.

- (form): Add Plasimc support.

- (form): Add `FloatButton` component.

- (form): Add GDPR service.

- (form): Update resources.

- (form): Update translations.

- (form): Add landing components.

- (form): Add router components.

- (form): Add custom settings and use `react-router-dom` for `App`.

- (form): Add Form as component.

- (form): Update resources.

- (form): Update server form.

- (form): Update layout of user anc contact rendering + add
  `loginRequired` option.

- (form): Add `autoComplete` to `User` components.

- (form): Change table orderable handler.

- (form): Merge `Loader.css` in `main.css`.

- (form): `ConfigProvider` handles the language changes.

- (form): Make `antd` as default theme.

- (form): Add `postData` method to `Form`.

- (form): Update stripe widget.

- (form): Add `Skeleton` template.

- (form): Add `Tag` and `Timeline` components.

- (form): Update Steps behaviour.

- (form): Add `jsx` extension in `webpack.config.js`.

- (form): Update resources.

- (form): Update `Steps` component.

- (form): Add tooltip and tour components.

- (form): Update resources.

- (form): Update Steps defaults.

- (form): Correct `InputNumber` focused behaviour.

- (form): Add `configProvider` option to layout widget.

- (form): Update server structure.

- (form): Add options for `CheckboxWidget`.

- (form): Add Markdown widget.

- (form): Add new table csv output and input format.

- (form): Update layout rendering.

- (form): Add `Alert`, `Drawer`, `Popconfirm`, `Progress`, `Result`,
  `Skeleton`, `Spin`, `Watermark` components.


Fix
~~~
- (form): Remove unused code.

- (doc): Correct bug for new version sphinx.

- (form): Correct form test cases.

- (core): Add missing requirements.

- (form): Correct `Admin` `CSRF`.

- (form): Add `setCurrentStep` feature to `Steps` component.

- (form): Hide page content when not logged.

- (form): Remove Landing components.

- (form): Correct Settings rendering.

- (form): Correct page layout.

- (form): Correct Landing formatting.

- (core): Remove unneeded resources.

- (form): Correct `formContext` generation.

- (form): Correct `idPrefix`.

- (form): Correct `PDFField` behaviour.

- (web): Correct flash messages encoding.

- (form): Correct `DraggerFileWidget` error colors.

- (form): Correct `Loader` layout.

- (form): Correct `Stripe` widget.

- (form): Correct `webhooks` CSRF bug.

- (form): Rollback `rjsf` version resources.

- (form): Correct callback dependencies.

- (form): Use debounce for updating values in editing mode.

- (form): Correct `RangeWidget` update timing.

- (form): Correct `ConfigProvider` handling.

- (form): Correct `MentionsWidget` behaviour.

- (form): Correct minus layout of App component.

- (form): Correct bug in rendering parent path.


v1.5.11 (2024-05-08)
--------------------

Feat
~~~~
- (form): Update resources.

- (form): Add option to `overwriteEnumOptions` in `SelectWidget`.

- (form): FlexLayout remove background.

- (form): Update Domain behaviour.

- (form): Add custom functions.


Fix
~~~
- (form): Update default `index-ui.json`.

- (form): Remove `margin` of `#content`.

- (form): Correct `extraInputProps` behaviour of `BaseInputTemplate`.

- (form): Correct `pagination` of `TableField`.

- (form): Update TabsField layout.

- (form): Update TabsField layout.

- (form): Correct App layout for sidebar.

- (form): Add missing parent parameter in `formContext`.

- (form): Correct validator options.


v1.5.10 (2024-04-21)
--------------------

Feat
~~~~
- (form): Update resources.

- (form): Add tiers calculation for stripe checkout.

- (form): Update `App`, `ArrayCloud`, `Submit`, `CloudDownloadField`,
  `CloudUploadField` components.

- (form): Add `Errors.Drawer` component.

- (form): Export `getComponents` and `getComponentDomains` in schedula
  js package.

- (form): Add `onCheckout` option to Stripe widget.


Fix
~~~
- (form): Improve JSON secrets behaviour.

- (form): Update server default config.

- (form): Correct typos in `getComponents`.

- (form): Run `editOnChange` after form `componentMount`.


v1.5.9 (2024-04-21)
-------------------

Fix
~~~
- (form): Correct bug when copying files in cmd line.


v1.5.8 (2024-04-20)
-------------------

Fix
~~~
- (setup): Add missing `package_data`.


v1.5.7 (2024-04-19)
-------------------

Feat
~~~~
- (form): Update resources.

- (form): Add cmd to generate a sample project and update the mode of
  passing `edit_on_change`, `pre_submit`, and `post_submit` options.

- (form): Remove `ExcelPreview` component and widget.

- (form): Add cmd to generate a sample project and update the mode of
  passing `edit_on_change`, `pre_submit`, and `post_submit` options.

- (form): Add Icon component.

- (form): Replace `xlsx-preview` with `univerjs`.


Fix
~~~
- (bin): Correct default option of `publish.sh`.

- (test): Correct order of selenium execution.


v1.5.6 (2024-04-03)
-------------------

Feat
~~~~
- (form): Update resources.

- (form): Add `ExcelPreviewWidget` and `ExcelPreview` components.

- (form): Change behaviour of `edit_on_change`, `pre_submit` and
  `post_submit` optional paths.

- (dsp): Add option to avoid cycles when extracting dsp from reverse
  graph.

- (form): Add `ResponsiveGridLayout` component.

- (form): Update `ant-design-draggable-modal` for antd v5.

- (form): Secure secrets data of payments.

- (form): Change icons of TableField and App component.

- (form): Improve rendering of tables.


Fix
~~~
- (test): Ensure timing for testcases.

- (form): Correct Cascader properties in omit.

- (form): Correct FileWidgets behaviours.

- (form): Correct CascaderField layout.


v1.5.5 (2024-03-19)
-------------------

Feat
~~~~
- (form): Update resources.


Fix
~~~
- (form): Enable caching of files on browser.

- (form): Correct toPathSchema for cascader.

- (form): Harmonize the extraInputProps of InputTemplate.

- (form): Correct Table reordering.

- (form): Improve performance of Form rendering.

- (form): Improve performances of retrieve schema.

- (form): Correct default language selection.

- (form): Correct Cascader Layout.

- (form): Correct emptyValue behaviour of `BaseInputTemplate`.


v1.5.4 (2024-03-17)
-------------------

Feat
~~~~
- (form): Update resources.

- (form): Add `ImageFileWidget`.

- (form): Make table field orderable.

- (form): Add Base template to cascader.

- (form): Add flexlayout to `App`.


Fix
~~~
- (form): Improve widget aspect.

- (form): Improve behaviour of InputTemplate.

- (form): Improve behaviour of Flex layout.


v1.5.3 (2024-03-14)
-------------------

Feat
~~~~
- (doc): Update copyright.

- (form): Update resources.

- (form): Update dependencies.

- (form): Add stripe component.

- (react): Add layout to function rendering.

- (form): Add auto loader for js files.

- (form,antd): Add option to edit when row is close.

- (form, antd): Add `DraggerFileWidget`.

- (form): Correct PDF rendering.

- (form,antd): Add `Mentions` widget.

- (form,antd): Add `Flex` component.

- (react): Add Static component to add html content using also
  dompurify.

- (form): Make pre-compiling validator dynamically.

- (doc): Add download badges.


Fix
~~~
- (requirements): Add missing `stripe` requirement.

- (form): Correct error for missing `blueprint_name` for `Flask-
  Security-Too`.

- (form): Correct typo in auto loader for js files.

- (react): Correct handling of preSubmit input.

- (form): Correct DateRangeWidget.

- (form, antd): Correct mentions.

- (form): Correct PDF paragraph rendering.


v1.5.2 (2023-11-19)
-------------------

Feat
~~~~
- (form): Update static code.

- (form): Add `antd` translations.

- (test): Update coverage python version.


Fix
~~~
- (drw): Correct broken link when same object is rendered twice.

- (asy): Ensure all processes are well closed.

- (form): Correct language selector bugs and uniform translation
  handling.


v1.5.1 (2023-11-11)
-------------------

Fix
~~~
- (doc): Correct docs errors.

- (doc): Add missing API links.

- (doc): Add readthedocs config file.


v1.5.0 (2023-11-10)
-------------------

Feat
~~~~
- (react): Split bundle.

- (react): Add pricing component.

- (setup): Add python 3.11.

- (form): Update static code.

- (form): Compress all static files.

- (form): Update default ui schema.

- (react): Update dev requirements.

- (react): Extend base ObjectField.

- (react): Extend base form.

- (form): Update static code.

- (example): Add output table title.

- (form): Remove unuseful log.

- (example): Update length converter form example.

- (form): Re-enable form tests.

- (form): Update requirements.

- (form): Update App component.

- (form): Correct behaviour of `get_form_context`.

- (form): Update App component.

- (form): Add automatic column table name form schema.

- (form): Add new requirements for server.

- (form): Update state only when errors change.

- (form)Simplify layout definition.

- (drw): Add option to run site when plotting.

- (drw): Add option to run site when plotting.

- (form)Simplify layout definition.


Fix
~~~
- (sphinx): Correct sphinx requirement `sphinx>=7.2`.

- (setup): Update form requirements.

- (test): Remove unwanted libs.

- (sphinx): Correct sphinx requirement.

- (core): Fix compatibility with python 3.8.

- (react): Correct layout.

- (react): Remove warning about `selectedKeys`.

- (react): Define validator before rendering.

- (react): Use `debounceValidate` instead `liveValidate`.

- (react): Correct uiSchema and schemaUtils errors.

- (react): Avoid the overwrite of rootSchema.

- (react): Speed up validator definition.

- (react): Correct `getFirstMatchingOption` parameters.

- (react): Update `rjsf` to version 5.13.6.

- (react): Remove unused import.

- (form): Correct requirements.

- (web): Correct blueprint_name.

- (form): Remove dependency from `pkg_resources`.

- (form): Correct filename for windows.

- (ext): Update autosummary according to new Sphinx.

- (web): Improve gzip encoding handler.


v1.4.9 (2023-01-23)
-------------------

Feat
~~~~
- (form): Update bundle.

- (dsp): Use `dataclass` for inf instance.


Fix
~~~
- (ext): Correct parent content getter.

- (form): Correct fullscreen behaviour.

- (form): Clean wrong error states.


v1.4.8 (2023-01-06)
-------------------

Feat
~~~~
- (form): Update bundle.

- (form): Make modal unmount.


Fix
~~~
- (form): Correct `useEffect` loop.

- (form): Add missing invocation of `editOnChange`.


v1.4.7 (2023-01-05)
-------------------

Feat
~~~~
- (form): Update bundle.

- (form): Request gzip schemas.

- (form): Enforce correct defaults.

- (form): Resolve schema.


Fix
~~~
- (test): Test only one python version for windows.

- (form): Invoke form validation after submit.

- (form): Use `retrieveSchema` function to retrieve field schema.

- (web): Correct debug url.


v1.4.6 (2023-01-04)
-------------------

Feat
~~~~
- (site): Drop gevent dependence.

- (form): Update bundle.

- (form): Add error handling on file widget.

- (form): Move `ReactModal` in a custom component.

- (form): Add `savingData` option to nav component.

- (form): Add download buttons to file widget.

- (form): Group all states to a single state + debounce live validation.

- (site): Enable async routes.

- (form): Reduce bundle size.

- (form): Add new method `path` for `ui:layout`.

- (form): Use gzip to POST requests.

- (form): Add download buttons to file widget.


Fix
~~~
- (form): Correct modal css.

- (form): Ensure datagrid string or bool format.


v1.4.5 (2022-12-27)
-------------------

Feat
~~~~
- (form): Add FileWidget + Improve Autosaving and enforce code
  splitting.


Fix
~~~
- (site): Correct `gevent` error when watcher is `None`.


v1.4.4 (2022-12-22)
-------------------

Feat
~~~~
- (test): Add more form test cases.

- (test): Disable logging for test cases.

- (site): Add option `url_prefix`.


Fix
~~~
- (form): Use modal instead popup to show the debug view.

- (web): Remove custom methods `PING` and `DEBUG` for standards `GET`
  and `POST`.


v1.4.3 (2022-12-21)
-------------------

Feat
~~~~
- (web): Add `DEBUG` method as `API` service.


Fix
~~~
- (test): Correct test cases to generate autodispatcher.

- (form): Correct bug when plot is empty.


v1.4.2 (2022-12-15)
-------------------

Feat
~~~~
- (form): Add options to edit/pre- post-process within the form
  dynamically.


v1.4.1 (2022-12-12)
-------------------

Feat
~~~~
- (base): Update default behaviour when invoking `plot`, `web` and
  `form`.

- (sol): Remove unused code.

- (core): Create a new module `utl`.


Fix
~~~
- (form): Correct form `url` API.

- (doc): Remove `requires.io`.


v1.4.0 (2022-12-12)
-------------------

Feat
~~~~
- (form): Add extension for forms with test cases.

- (drw): Add option to add raw body to dot graphviz file.

- (dsp): Improve readability of `MapDispatch` results.

- (core): Drop cutoff functionality.

- (dsp): Add options to use `SubDispatchFunction` like `SubDispatch`.

- (setup) :gh:`19`: Add option to publish schedula-core.

- (form): Add delete all button on datagrid.

- (parallel): Make sync the default executor.

- (setup) :gh:`19`: Add feature to install only core functionalities.


Fix
~~~
- (binder): Correct installation of binder.

- (form): Correct `CSRF` error handling.

- (jinja)Disable HTML AutoEscape.

- (asy): Avoid adding solution when `NoSub`.


v1.3.6 (2022-11-21)
-------------------

Feat
~~~~
- (form): Add data saver and restore options + fix fullscreen + improve
  `ScrollTop`.


Fix
~~~
- (form): Fix layout `isEmpty`.


v1.3.5 (2022-11-08)
-------------------

Fix
~~~
- (form): Correct data import in nav.


v1.3.4 (2022-11-07)
-------------------

Feat
~~~~
- (form): Add fullscreen support.

- (form): Add nunjucks support.

- (form): Add react-reflex component.

- (web): Add option to rise a WebResponse from a dispatch.

- (form): Add CSRF protection.


v1.3.3 (2022-11-03)
-------------------

Feat
~~~~
- (form): Add markdown.

- (form): Avoid rendering elements with empty children.

- (form): Add more option to accordion and stepper.

- (form): Change position of error messages.


Fix
~~~
- (rtd): Correct doc rendering.

- (form): Correct plotting behaviour.


v1.3.2 (2022-10-24)
-------------------

Feat
~~~~
- (drw, web, form): Add option to return a blueprint.

- (form): Update bundle.


Fix
~~~
- (form): Add extra missing package data.


v1.3.1 (2022-10-20)
-------------------

Fix
~~~
- (form): Add missing package data.

- (ext): Correct documenter doctest import.


v1.3.0 (2022-10-19)
-------------------

Feat
~~~~
- (form): Add new method form to create jsonschema react forms
  automatically.

- (blue): Add option to limit the depth of sub-dispatch blue.


Fix
~~~
- (sol): Correct default initialization for sub-dispatchers.

- (setup): Ensure correct size of distribution pkg.


v1.2.19 (2022-07-06)
--------------------

Feat
~~~~
- (dsp): Add new utility function `run_model`.

- (dsp): Add `output_type_kw` option to `SubDispatch` utility.

- (core): Add workflow when function is a dsp.


Fix
~~~
- (blue): Add memo when call register by default.


v1.2.18 (2022-07-02)
--------------------

Feat
~~~~
- (micropython): Update build for `micropython==v1.19.1`.

- (sol): Improve speed performance.

- (dsp): Make `shrink` optional for `SubDispatchPipe`.

- (core): Improve performance dropping `set` instances.


v1.2.17 (2022-06-29)
--------------------

Feat
~~~~
- (sol): Improve speed performances.


Fix
~~~
- (sol): Correct missing reference due to sphinx update.

- (dsp): Correct wrong workflow.pred reference.


v1.2.16 (2022-05-10)
--------------------

Fix
~~~
- (drw): Correct recursive plots.

- (doc): Correct `requirements.io` link.


v1.2.15 (2022-04-12)
--------------------

Feat
~~~~
- (sol): Improve performances of `_see_remote_link_node`.

- (drw): Improve performances of site rendering.


v1.2.14 (2022-01-21)
--------------------

Fix
~~~
- (drw): Correct plot of `DispatchPipe`.


v1.2.13 (2022-01-13)
--------------------

Feat
~~~~
- (doc): Update copyright.

- (actions): Add `fail-fast: false`.

- (setup): Add missing dev requirement.


Fix
~~~
- (drw): Skip permission error in server cleanup.

- (core): Correct import dependencies.

- (doc): Correct link target.


v1.2.12 (2021-12-03)
--------------------

Feat
~~~~
- (test): Add test cases improving coverage.


Fix
~~~
- (drw): Correct graphviz `_view` attribute call.

- (drw): Correct cleanup function.


v1.2.11 (2021-12-02)
--------------------

Feat
~~~~
- (actions): Add test cases.

- (test): Update test cases.

- (drw): Make plot rendering parallel.

- (asy): Add `sync` executor.

- (dispatcher): Add auto inputs and outputs + prefix tags for
  `add_dispatcher` method.

- (setup): Pin sphinx version.


Fix
~~~
- (test): Remove windows long path test.

- (test): Correct test cases for parallel.

- (drw): Correct optional imports.

- (doc): Remove sphinx warning.

- (drw): Correct body format.

- (asy): Correct `atexit_register` function.

- (bin): Correct script.


v1.2.10 (2021-11-11)
--------------------

Feat
~~~~
- (drw): Add custom style per node.

- (drw): Make clean-up site optional.

- (drw): Add `force_plot` option to data node to plot Solution results.

- (drw): Update graphs colors.


Fix
~~~
- (setup): Pin graphviz version <0.18.

- (alg): Ensure `str` type of `node_id`.

- (drw): Remove empty node if some node is available.

- (drw): Add missing node type on js script.

- (drw): Extend short name to sub-graphs.


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

