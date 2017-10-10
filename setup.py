from setuptools import setup
import sys

if (sys.version_info[0] != 3):
    print("Please run this setup.py with python3")
    exit(1)


with open('README.md') as f:
    readme = f.read()

with open('LICENSE.txt') as f:
    the_license = f.read()

setup(
    name='pytrace',
    # NOTE: You *must* update the version number in pytrace/cli.py as well!
    version='1.1.1',
    description='tool to view SWO tracing output from an st-link V2 jtag dongle.',
    long_description=readme,
    author='Peter Kraak<pkraak@dynamiccontrols.com>',
    license=the_license,
    packages=['pytrace'],
    entry_points={
        'console_scripts': [
            'pytrace=pytrace.cli:run'],
    }
)
