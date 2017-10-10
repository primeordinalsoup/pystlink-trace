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

class WatchPointManager(object):
    """Utility class to set up watchpoint from command line arguments."""

    def __init__(self, trace, elf):
        self.trace = trace
        self.elfinspector = tpiuparser.Address2SymbolResolver(elf)

    def setupWatch(self, index, sym, addr, size):
        # set the user provided explicit values (they override the symbol table)
        if addr:
            addr = int(addr,16)
        if size:
            size = int(size)
        if not size:
            size = 4  # no size or sym set, default to 4
        addr = addr or self.elfinspector.name2addr(sym)
        size = size or self.elfinspector.name2size(sym)
        if size != 4:
            getOffset = True
        else:
            getOffset = False
        self.trace.setWatch(index, addr, size=size, getData=True, getPC=True, getOffset=getOffset)


# NOTE: This version *must* match the pip package one in setup.py, please update them together!
@click.version_option(version="1.1.1")

@click.command()
@click.option('--xtal',  default=72,     help='XTAL frequency of target in MHz')
@click.option('--baud',  default=250000, help='Baud rate for SWO from target (2000000 max)')
@click.option('--elf',   default=None,   help='application loaded on target (for selecting watch variables)')
@click.option('--sym0',  default=None,   help='symbol of memory to watch on DWT0')
@click.option('--addr0', default=None,   help='address IN HEX to watch on DWT0')
@click.option('--size0', default=None,   help='number of bytes IN DEC to watch on DWT0 (defaults to size in map constrained to 2**n OR 4 if addr set explicitly via --addr0)')
@click.option('--sym1',  default=None,   help='symbol of memory to watch on DWT1')
@click.option('--addr1', default=None,   help='address IN HEX to watch on DWT1')
@click.option('--size1', default=None,   help='number of bytes IN DEC to watch on DWT1 (defaults to size in map constrained to 2**n OR 4 if addr set explicitly via --addr1)')
@click.option('--sym2',  default=None,   help='symbol of memory to watch on DWT2')
@click.option('--addr2', default=None,   help='address IN HEX to watch on DWT2')
@click.option('--size2', default=None,   help='number of bytes IN DEC to watch on DWT2 (defaults to size in map constrained to 2**n OR 4 if addr set explicitly via --addr2)')
@click.option('--sym3',  default=None,   help='symbol of memory to watch on DWT3')
@click.option('--addr3', default=None,   help='address IN HEX to watch on DWT3')
@click.option('--size3', default=None,   help='number of bytes IN DEC to watch on DWT3 (defaults to size in map constrained to 2**n OR 4 if addr set explicitly via --addr3)')
def run(xtal, baud, elf, sym0, addr0, size0, sym1, addr1, size1, sym2, addr2, size2, sym3, addr3, size3):
    """Capture SWO trace output from stlink V2"""
    try:
        trace = stlinktrace.StlinkTrace(xtal, baud)
    except Exception as e:
        print("NO STLINK! exiting. {}".format(e))
    else:
        watchPointMgr = WatchPointManager(trace, elf)
        if sym0 or addr0:
            watchPointMgr.setupWatch(0, sym0, addr0, size0)
        if sym1 or addr1:
            watchPointMgr.setupWatch(1, sym1, addr1, size1)
        if sym2 or addr2:
            watchPointMgr.setupWatch(2, sym2, addr2, size2)
        if sym3 or addr3:
            watchPointMgr.setupWatch(3, sym3, addr3, size3)
        parser = tpiuparser.TPIUParser(elf)

        with GracefulInterruptHandler() as h:
            print("starting SWO")
            trace.startSWO()  # while SWO active NO other calls than stopSWO and readSWO allowed
            try:
                while True:
                    swo = trace.readSWO()
                    if swo:
                        parser.parseBytes(swo)
                    if h.interrupted:
                        print("CAUGHT Linux signal - terminating.")
                        print("stopping SWO")
                        trace.stopSWO()
                        break
            except:
                trace.stopSWO()

if __name__ == '__main__':
    run()
