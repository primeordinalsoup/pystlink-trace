ST-LINK SWO Viewer
==================

This is just a command line tool to set up and read the SWO output
from an embedded target via a standard st-link V2.  It is based on an
open source project pyswd and some hand rolled SWO decoding.

Installing
----------

From the Dynamic repo:
$sudo apt-get install pystlink-trace
*this should be already installed as part of standard dev. meta package.*

Manually, in a python 3 environment:
- pip install -r requirements.txt
- pip install -e .


Usage
-----

$ stlink-trace --help

$ stlink-trace --version

$ stlink-trace -b 20000000   # over-ride default target XTAL freq. of 72000000

