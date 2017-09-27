#!/usr/bin/env python3

import click
import signal
from pytrace import stlinktrace, tpiuparser

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
def run(xtal):
    """Capture SWO trace output from stlink V2"""
    try:
        trace = stlinktrace.StlinkTrace(xtal)
    except Exception as e:
        print("NO STLINK! exiting. {}".format(e))
    else:
        trace.startSWO()
        print("starting SWO")
        parser = tpiuparser.TPIUParser()

        with GracefulInterruptHandler() as h:
            while True:
                swo = trace.readSWO()
                if swo:
                    #print(swo)
                    parser.parseBytes(swo)
                if h.interrupted:
                    print("CAUGHT ^C")
                    break

        print("stopping SWO")
        trace.stopSWO()

if __name__ == '__main__':
    run()
