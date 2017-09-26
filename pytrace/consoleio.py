#!/usr/bin/env python3

import sys, tty, termios
from select import select

class Conio():
    """simple context manager class to set up console IO with
    no buffering (waiting for ENTER key) so any-key
    will trigger IO."""
    class Break(Exception):
        """Break out of the with statement."""

    def __init__(self):
        # set tty to RAW so no line buffering
        self._orig_settings = termios.tcgetattr(sys.stdin)

    def __enter__(self):
        tty.setraw(sys.stdin)
        return self
       
    def __exit__(self, etype, value, traceback):
        """restore tty (i.e. restore line buffering)"""
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._orig_settings)
        return True if etype == self.Break else etype

    def kbhit(self):
        return select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

    def getch(self):
        return sys.stdin.read(1)[0]
