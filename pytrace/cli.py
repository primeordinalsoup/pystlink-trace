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
        trace.startSWO()
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
            outputBytes = subprocess.run(["nm", "-S", elf], stdout=subprocess.PIPE).stdout.split(b'\n')
            output = [l.decode("utf-8") for l in outputBytes]
            for l in output:
                if sym0 in l:
                    print("line [{}]".format(l))
                    symData = l.split(' ')
                    print(symData)
                    addr = addr or int( symData[0], 16 )  # --addrn overrides address in map
                    size = size or int( symData[1], 16 )  # --sizen overrides size in map
                    print("GOT SYM!  {}\nsetting watch @addr: {} size {}".format(sym0, addr, size))
                    break
            if not size:
                size = 4  # no size0 or sym0 set, default to 4
            trace.setWatch(0, addr, size=size, getPC=True)
        print("starting SWO")
        parser = tpiuparser.TPIUParser(elf)

        with GracefulInterruptHandler() as h:
            currmode = trace._stlink.com.xfer([0xf5], rx_len=2)
            while True:
                v = trace._stlink.get_target_voltage()
                if v < 1:
                    print("powered OFF! - waiting for power up")
                    while trace._stlink.get_target_voltage() < 3:
                        pass
                    print("target powered on!")
                    time.sleep(0.1)
                    trace._stlink.leave_state()
                    trace._stlink.enter_debug_swd()
                    trace._setupSWOTracing(xtal, baud)
                    trace.startSWO()

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
