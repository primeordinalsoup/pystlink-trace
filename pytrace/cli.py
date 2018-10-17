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

    def __init__(self, trace, elves):
        self.trace = trace
        self.elfinspector = tpiuparser.Address2SymbolResolver(elves)

    def setupWatch(self, index, sym, addr, size, flags):
        # set the user provided explicit values (they override the symbol table)
        if addr:
            addr = int(addr,16)
        if size:
            size = int(size)
        if not size:
            size = 4  # no size or sym set, default to 4
        addr = addr or self.elfinspector.name2addr(sym)
        size = size or self.elfinspector.name2size(sym)

        getData = 'd' in flags
        getPC = 'p' in flags
        getOffset = 'o' in flags
        self.trace.setWatch(index, addr, size=size, getData=getData, getPC=getPC, getOffset=getOffset)

_global_options = [
    click.option('--xtal',   default=72,     help='XTAL frequency of target in MHz'),
    click.option('--baud',   default=250000, help='Baud rate for SWO from target (2000000 max)'),
	click.option('--isr',    default=0,      help='trace EXCEPTIONS'),
	click.option('--prof',   default=0,      help='sample PC and profile CPU usage'),
	click.option('--elf0',   default=None,   help='an application loaded on target, eg bootstrapper (for selecting watch variables)'),
	click.option('--elf1',   default=None,   help='application loaded on target eg main app(for selecting watch variables)'),
	click.option('--sym0',   default=None,   help='symbol of memory to watch on DWT0'),
	click.option('--addr0',  default=None,   help='address IN HEX to watch on DWT0'),
	click.option('--size0',  default=None,   help='number of bytes IN DEC to watch on DWT0 (defaults to size in map constrained to 2**n OR 4 if addr set explicitly via --addr0)'),
	click.option('--flags0', default="dp",   help='flags to control DWT reporting, d: data, p: PC, o: offset, r: reads, w: writes, u: unique only'),
	click.option('--sym1',   default=None,   help='symbol of memory to watch on DWT1'),
	click.option('--addr1',  default=None,   help='address IN HEX to watch on DWT1'),
	click.option('--size1',  default=None,   help='number of bytes IN DEC to watch on DWT1 (defaults to size in map constrained to 2**n OR 4 if addr set explicitly via --addr1)'),
	click.option('--flags1', default="dp",   help='flags to control DWT reporting, d: data, p: PC, o: offset, r: reads, w: writes, u: unique only'),
	click.option('--sym2',   default=None,   help='symbol of memory to watch on DWT2'),
	click.option('--addr2',  default=None,   help='address IN HEX to watch on DWT2'),
	click.option('--size2',  default=None,   help='number of bytes IN DEC to watch on DWT2 (defaults to size in map constrained to 2**n OR 4 if addr set explicitly via --addr2)'),
	click.option('--flags2', default="dp",   help='flags to control DWT reporting, d: data, p: PC, o: offset, r: reads, w: writes, u: unique only'),
	click.option('--sym3',   default=None,   help='symbol of memory to watch on DWT3'),
	click.option('--addr3',  default=None,   help='address IN HEX to watch on DWT3'),
	click.option('--size3',  default=None,   help='number of bytes IN DEC to watch on DWT3 (defaults to size in map constrained to 2**n OR 4 if addr set explicitly via --addr3)'),
	click.option('--flags3', default="dp",   help='flags to control DWT reporting, d: data, p: PC, o: offset, r: reads, w: writes, u: unique only'),
]

def global_options(func):
    for option in reversed(_global_options):
        func = option(func)
    return func

# NOTE: This version *must* match the pip package one in setup.py, please update them together!
@click.version_option(version="1.4.2")
@click.group()
def cmnds():
    pass

@cmnds.command()
@global_options
def log(**kwargs):
    """Capture SWO trace output from stlink V2"""
    run_trace(command='log', **kwargs)

@cmnds.command()
@global_options
def target(**kwargs):
    """Report on attached target, its ID and present voltage"""
    try:
        target = stlinktrace.StlinkTrace()
    except Exception as e:
        print("NO STLINK! exiting. {}".format(e))
    else:
        id = target.getCoreID()
        voltage = target.getTargetVoltage()
        print("ID: {:#X}\nVoltage: {:.4}".format(id, voltage))

def run_trace(command, xtal, baud, isr, prof, elf0, elf1, sym0, addr0, size0, sym1, addr1, size1, sym2, addr2, size2, sym3, addr3, size3, flags0, flags1, flags2, flags3):
    """Capture SWO trace output from stlink V2"""
    print("cmnd: {}".format(command))

    try:
        trace = stlinktrace.StlinkTrace(xtal, baud)
    except Exception as e:
        print("NO STLINK! exiting. {}".format(e))
    else:
        watchPointMgr = WatchPointManager(trace, (elf0, elf1))
        if sym0 or addr0:
            watchPointMgr.setupWatch(0, sym0, addr0, size0, flags0)
        if sym1 or addr1:
            watchPointMgr.setupWatch(1, sym1, addr1, size1, flags1)
        if sym2 or addr2:
            watchPointMgr.setupWatch(2, sym2, addr2, size2, flags2)
        if sym3 or addr3:
            watchPointMgr.setupWatch(3, sym3, addr3, size3, flags3)
        trace.setExceptionTracing(isr)
        trace.setProfiling(prof)
        parser = tpiuparser.TPIUParser([sym0, sym1, sym2, sym3], [flags0, flags1, flags2, flags3], [elf0, elf1])

        with GracefulInterruptHandler() as h:
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
