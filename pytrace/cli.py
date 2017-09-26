#!/usr/bin/env python3

import click
from pytrace import stlinktrace
from pytrace import consoleio

# NOTE: This version *must* match the pip package one in setup.py, please update them together!
@click.version_option(version="1.0.0")

@click.command()
@click.option('--xtal', default=72000000, help='XTAL frequency of target in Hz')
def run(xtal):
    """Capture SWO trace output from stlink V2"""
    try:
        trace = stlinktrace.StlinkTrace(xtal)
    except Exception as e:
        print("NO STLINK! exiting. {}".format(e))
    else:
        trace.startSWO()
        print("starting SWO")
        with consoleio.Conio() as con:
            print("do something worthwhile. {}".format(xtal))
            while True:
                ch = con.getch() if con.kbhit() else ' '
                if ch == 'q' or ord(ch) == 3:
                    raise con.Break
                swo = trace.readSWO()
                if swo:
                    print(swo)
        print("stopping SWO")
        trace.stopSWO()

if __name__ == '__main__':
    run()
