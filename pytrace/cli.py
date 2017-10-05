#!/usr/bin/env python3

import click
import signal
from pytrace import stlinktrace, tpiuparser
import time
import subprocess

class GracefulInterruptHandler(object):
    """This is a context manager that hooks some signals and captures if they
    have fired, to allow breaking out a loop cleanly (do cleanup via 'with' construct)"""
    
    def __init__(self, signals=(signal.SIGINT, signal.SIGTERM, signal.SIGPIPE)):
        self.signals = signals
        self.original_handlers = {}

    def __enter__(self):
        self.interrupted = False
        self.released = False

        for sig in self.signals:
            self.original_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, self.handler)

        return self

    def handler(self, signum, frame):
        self.release()
        self.interrupted = True

    def __exit__(self, type, value, tb):
        self.release()

    def release(self):
        if self.released:
            return False

        for sig in self.signals:
            signal.signal(sig, self.original_handlers[sig])

        self.released = True
        return True
    
# NOTE: This version *must* match the pip package one in setup.py, please update them together!
@click.version_option(version="1.0.0")

@click.command()
@click.option('--xtal', default=72, help='XTAL frequency of target in MHz')
@click.option('--baud', default=250000, help='Baud rate for SWO from target (2000000 max)')
@click.option('--elf', default=None, help='application loaded on target (for selecting watch variables)')
@click.option('--sym0', default=None, help='symbol of memory to watch on DWT0')
@click.option('--addr0', default=None, help='address IN HEX to watch on DWT0')
@click.option('--size0', default=None, help='number of bytes IN DEC to watch on DWT0 (defaults to size in map constrained to 2**n OR 4 if addr set explicitly via --addr0)')
def run(xtal, baud, elf, sym0, addr0, size0):
    """Capture SWO trace output from stlink V2"""
    try:
        trace = stlinktrace.StlinkTrace(xtal, baud)
    except Exception as e:
        print("NO STLINK! exiting. {}".format(e))
    else:
        elfinspector = tpiuparser.Address2SymbolResolver(elf)
        if sym0 or addr0:
            # set the user provided explicit values (they override the symbol table)
            if addr0:
                addr = int(addr0,16)
            else:
                addr = None
            if size0:
                size = int(size0)
            else:
                size = None
            if not size:
                size = 4  # no size0 or sym0 set, default to 4
            addr = addr or elfinspector.name2addr(sym0)
            size = size or elfinspector.name2size(sym0)
            trace.setWatch(0, addr, size=size, getPC=True)
        parser = tpiuparser.TPIUParser(elf)

        print("starting SWO")
        trace.startSWO()  # while SWO active other calls than stopSWO and readSWO allowed
        with GracefulInterruptHandler() as h:
            while True:
                swo = trace.readSWO()
                if swo:
                    #print(swo)
                    parser.parseBytes(swo)
                if h.interrupted:
                    print("CAUGHT Linux signal - terminating.")
                    break
        print("stopping SWO")
        trace.stopSWO()

if __name__ == '__main__':
    run()
