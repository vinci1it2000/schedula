#!/bin/bash
#
# Release checklist
# =================
# 1. Bump-ver & Update Date+Title in ./CHANGES.rst.
# 2. (if FINAL)REMOVE `pip install --pre` from README!!!
# 3. Run TCs.
# 4. commit & TAG & push
# 5. Gen DOCS & MODEL in `cmd.exe` & check OK (i.e. diagrams??)
#    and build `wheel,` `sdist` , `doc` archives:
#       ./bin/package.sh
# 6. Upload to PyPi:
#    - DELETE any BETAS (but the last one?)!!
#       - twine upload -su <gpg-user> dist/* # Ignore warn about doc-package.
#
# +++MANUAL+++
# 7. Generate RELEASE_NOTES:
#    - open ./doc/_build/html/co2mpas_RelNotes.html ## & PrintAs 'co2mpas_RelNotes-v0.1.1.pdf'
# 8. Prepare site at http://co2mpas.io/
#   - copy ALLINONES
#   - copy `allinone/CO2MPAS/packages` dir created during:
#            pip install co2mpas --download %home%\packages
#    - Expand docs, link STABLE ad LATEST
# 9. Prepare email (and test)
#    - Use email-body to draft a new "Release" in github (https://github.com/JRCSTU/co2mpas/releases).
#

my_dir=`dirname "$0"`
cd $my_dir/..

## Generate Site:
rm -r ./doc/_build/
cmd /C co2mpas modelgraph -O doc/_build/html/_static/ co2mpas.model.model co2mpas.model.physical.wheels.wheels
cmd /C python setup.py build_sphinx

