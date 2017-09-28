#!/usr/bin/env python3

import click
import signal
from pytrace import stlinktrace, tpiuparser
import time

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
def run(xtal, baud):
    """Capture SWO trace output from stlink V2"""
    try:
        trace = stlinktrace.StlinkTrace(xtal, baud)
    except Exception as e:
        print("NO STLINK! exiting. {}".format(e))
    else:
        trace.startSWO()
        print("starting SWO")
        parser = tpiuparser.TPIUParser()

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
