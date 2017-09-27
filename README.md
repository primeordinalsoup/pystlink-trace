ST-LINK SWO Viewer
==================

This is just a command line tool to set up and read the SWO output
from an embedded target via a standard st-link V2.  It is based on an
open source project pyswd and some hand rolled SWO decoding.

## Installing
From the Dynamic repo:
```bash
sudo apt-get install pytrace
```
*this should be already installed as part of standard dev. meta package.*

Via setuptools:
```bash
sudo python3 setup.py install          #installs to site-packages
sudo python3 setup.py install develop  #installs in place so changes to source apply instantly
```

Via Pip manually, in a python 3 environment:
```bash
pip install -r requirements.txt
pip install -e .
```

*TIP:*  Copy the pytrace-completion file to /etc/bash_completion.d to
activate tab completion.


Packaging
---------
You can make a debian package directly from this repo.  In the
following example the maintainer is the debian package maintainer, and the
version is the package version.
```bash
sudo apt-get install checkinstall
sudo checkinstall --exclude=/usr/local/lib/python3.5/dist-packages/easy-install.pth --pkgversion=1.0.0 --pkglicense=DCL --maintainer='pkraak@dynamiccontrols.com' --requires=pyswd -y python3 setup.py install
```

Usage
-----

$ pytrace --help
  
$ pytrace --version
  
$ pytrace --xtal 200   # over-ride default target XTAL freq. of 72mHz for 200MHz REMRE

