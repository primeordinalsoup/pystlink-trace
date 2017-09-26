#!/usr/bin/env python3

import click
import signal
from pytrace import stlinktrace, tpiuparser

class GracefulInterruptHandler(object):

    def __init__(self, sig=signal.SIGINT):
        self.sig = sig

    def __enter__(self):
        self.interrupted = False
        self.released = False

        self.original_handler = signal.getsignal(self.sig)

        def handler(signum, frame):
            self.release()
            self.interrupted = True

        signal.signal(self.sig, handler)

        return self

    def __exit__(self, type, value, tb):
        self.release()

    def release(self):

        if self.released:
            return False

        signal.signal(self.sig, self.original_handler)

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
