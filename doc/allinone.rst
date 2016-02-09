##########################
CO2MPAS All-In-One archive
##########################
A pre-populated folder with WinPython + CO2MPAS + Consoles for *Windows*.

.. contents:: Table of Contents
  :backlinks: top
  :depth: 4


1st steps
=========

0. Execute the ``INSTALL.bat`` script the first time after extracting the archive.

1. Start up the console of your choice using the appropriate bat-file:

    - Execute the ``CONSOLE.bat`` to open a console with the **command-prompt**
      (`cmd.exe`) shell.
      Command-examples starting with the ``>`` character are for this shell.

    - Execute the ``bash-console.bat`` if you prefer the UNIX-like **bash-shell**
      environment.
      Command-examples starting with the ``$`` character are for this shell.

    - WHEN COPY-PASTING COMMANDS from the examples in the documents,
      DO NOT INCLUDE THE ``>`` OR ``$`` CHARACTERS.


2. Your *HOME* folder is ``CO2MPAS``.  You may run all example code inside
   this folder.

        - To move to your HOME folder when in *command-prompt*, type:

          .. code-block:: console

            > cd %HOME%

        - To move to your HOME folder when in *bash*, type:

          .. code-block:: console

            $ cd ~          ## The '~' char expands to home-folder.


3. View the files contained in your HOME folder, and read their description,
   provided in the next section:

        - In *command-prompt*, type:

          .. code-block:: console

            > dir
            07/10/2015  18:59    <DIR>          .
            07/10/2015  18:59    <DIR>          ..
            07/10/2015  17:35             6,066 .bashrc
            07/10/2015  18:58             2,889 .bash_history
            06/10/2015  18:09             1,494 .bash_profile
            10/09/2014  20:32               113 .inputrc
            06/10/2015  21:59    <DIR>          .ipython
            07/10/2015  17:27    <DIR>          .jupyter
            07/10/2015  18:25    <DIR>          .matplotlib
            06/10/2015  18:09             1,236 .profile
            06/10/2015  22:15                13 .python_history
            07/10/2015  00:33               688 README.txt
            07/10/2015  00:27    <DIR>          tutorial
                           7 File(s)         12,499 bytes
                           6 Dir(s)  319,382,626,304 bytes free

        - In *bash*, type:

          .. code-block:: console

            $ ls -l
            -r--rwxr--+ 1 user Domain Users 688 Oct  7 00:33 README.txt
            dr--rwxr--+ 1 user Domain Users   0 Oct  7 00:27 tutorial


3. To check everything is ok, run the following 2 commands and see if their
   output is quasi-similar:

        - In *command-prompt*, type:

          .. code-block:: console

            REM The python-interpreter that comes 1st is what we care about.
            > where python
            D:\co2mpas_ALLINONE-XXbit-v1.0.2\Apps\WinPython-XXbit-3.4.3.5\python-3.4.3\python.exe
            D:\co2mpas_ALLINONE-XXbit-v1.0.2\Apps\Cygwin\bin\python

            > co2mpas --version
            co2mpas-1.1.1 at D:\co2mpas_ALLINONE-XXbit-v1.0.2\Apps\WinPython-XXbit-3.4.3.5\python-3.4.3\lib\site-packages\co2mpas

        - In *bash*, type:

          .. code-block:: console

            > which python
            /cygdrive/d/co2mpas_ALLINONE-XXbit-v1.0.2/Apps/WinPython-XXbit-3.4.3.5/python-3.4.3/python

            > co2mpas --version
            co2mpas-1.1.1 at D:\co2mpas_ALLINONE-XXbit-v1.0.2\Apps\WinPython-XXbit-3.4.3.5\python-3.4.3\lib\site-packages\co2mpas

   In case of problems, copy-paste the output from the above commands and send
   it to JRC.


4. Follow the *Usage* instructions; they are locally installed at
   ``CO2MPAS/vX.X.X/co2mpas-doc-X.X.X/index.html`` or on the CO2MPAS-site:
   http://docs.co2mpas.io/  Just select the correct version.

   Demo files have been pre-generated for you, so certain commands might report
   that they cannot overwrite existing files.  Ignore the messages or use
   the `--force` option to overwrite them.

5. When a new CO2MPAS version is out, you may *upgrade* to it, and avoid
   re-downloading the *all-in-one* archive.  Read the respective sub-section
   of the *Installation* section from the documents.


Generic Tips
============

- You may freely move & copy this folder around.
  But prefer NOT TO HAVE SPACES IN THE PATH LEADING TO IT.

- To view & edit textual files, such as ``.txt``, ``.bat`` or config-files
  starting with dot(``.``), you may use the "ancient" Window *notepad* editor,
  but it will save you from  a lot of trouble if you download and install
  **notepad++** from: http://portableapps.com/apps/development/notepadpp_portable
  (no admin-rights needed).

  Even better if you combine it with the "gem" file-manager of the '90s,
  **TotalCommander**, from http://www.ghisler.com/ (no admin-rights needed).
  From inside this file-manager, ``F3`` key-shortcut views files.

- The **Cygwin** POSIX-environment and its accompanying **bash-shell** are
  a much better choice to give console-commands compare to `cmd.exe` prompt,
  supporting *auto-completion* for various commands (with ``[TAB]``key) and
  enhanced history search (with ``[UP]/[DOWN]`` cursor-keys).

  There are MANY tutorials and crash-courses for bash:

  - a concise one:
    http://www.ks.uiuc.edu/Training/Tutorials/Reference/unixprimer.html
  - a more detailed guide (just ignore the Linux-specific part):
    http://linuxcommand.org/lc3_lts0020.php
  - a useful poster with all fundamental bash-commands (eg. `ls`, `pwd`, `cd`):
    http://www.improgrammer.net/linux-commands-cheat-sheet/

- The console automatically copies into clipboard anything that is selected
  with the mouse.  In case of errors, copy and paste the offending commands and
  their error-messages to emails sent to JRC.

- When a new CO2MPAS version comes out it is not necessary to download the full
  ALLINONE archive, but you choose instead to just *upgrade* co2mpas.

  Please follow the upgrade procedure in the main documentation.



File Contents
=============
::

    RUN_CO2MPAS.bat            ## Asks for Input & Output folders, and runs CO2MPAS for all Excel-files in Input.
    MAKE_TEMPLATE.bat          ## Asks for a folder to store an empty CO2MPAS input-file.
    MAKE_DEMOS.bat             ## Asks for a folder to store demo CO2MPAS input-files.
    MAKE_IPYTHON_NOTEBOOKS.bat ## Asks for a folder to store IPYTHON NOTEBOOKS that run CO2MPAS and generate reports.
    CONSOLE.bat                ## Open a python+cygwin enabled `cmd.exe` console.

    co2mpas-env.bat            ## Sets env-vars for python+cygwin and launches arguments as new command
                               ## !!!!! DO NOT MODIFY !!!!! used by Windows StartMenu shortcuts.
    bash-console.bat           ## Open a python+cygwin enabled `bash` console.


    CO2MPAS/                   ## User's HOME directory containing release-files and tutorial-folders.
    CO2MPAS/.*                 ## Configuration-files auto-generated by various programs, starting with dot(.).

    Apps/Cygwin/               ## Unix-folders for *Cygwin* environment (i.e. bash).
    Apps/WinPython/            ## Python environment (co2mpas is pre-installed inside it).
    Apps/Console2/             ## A versatile console-window supporting decent copy-paste.
    Apps/graphviz/             ## Graph-plotting library (needed to generate model-plots).
    CO2MPAS_*.ico              ## The logos used by the INSTALL.bat script.

    README                     ## This file, with instructions on this pre-populated folder.

