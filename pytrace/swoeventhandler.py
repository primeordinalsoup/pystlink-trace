#!/usr/bin/env python3
"""
  This module handles the individual DWT/ITM events from the
  SWO stream.

  The events have been decoded by the TPIO parser and are given
  to this module to handle.  This module is responsible for
  doing any logging, data aggregation, and presentation to the
  screen.
"""

import time
from ansiterm.ansiterm import *
import operator

class Tui(object):
    """the object that owns the whole screen, and contains
    the widgets for the TUI (Text UI)"""

    def __init__(self):
        self._screen = Screen()
        self.height_chars = self._screen.lines
        assert (self.height_chars > 10), "needs terminal at least 10 lines high!"
        self.width_chars = self._screen.cols
        self.prof_height_chars = min(int(self.height_chars/2 - 3), 15)
        self.isr_height_chars = min(int(self.height_chars/2 - 3), 7)
        self.log_height_chars = self.height_chars - self.prof_height_chars - self.isr_height_chars

        # first box; Profiling
        x_origin = 1
        y_origin = 1
        self._prof_list = StaticListBox(x_origin, y_origin, self.prof_height_chars, self.width_chars,
                                       initial=['big', 'pigs', 'oversized', 'hat', 'with','too','many', 'lines'])
                                       #bg=Colour.BLACK)
        x_origin += self.prof_height_chars
        self._screen.add_widget(self._prof_list)

        # next box, ISR counts
        self._isr_list = StaticListBox(x_origin, y_origin, self.isr_height_chars, self.width_chars,
                                       initial=['big', 'pigs', 'oversized', 'hat', 'with','too','many', 'lines'])
                                       #bg=Colour.BLACK)
        x_origin += self.isr_height_chars
        self._screen.add_widget(self._isr_list)

        # last box, logging output window
        self._log_list = StaticListBox(x_origin, y_origin, self.log_height_chars, self.width_chars,
                                       initial=['big', 'pigs', 'oversized', 'hat', 'with','too','many', 'lines'])
                                       #bg=Colour.BLACK)
        x_origin += self.log_height_chars
        self._screen.add_widget(self._log_list)

        # bottom of screen is the status bar
        self._status_bar = Text(x_origin, 1, Font(fg=Colour.RED, bold=True) + "big, bold and RED")
        self._screen.add_widget(self._status_bar)
        self._screen.refresh()

    def window_height_chars(self):
        return self.height_chars

    def window_width_chars(self):
        return self.width_chars

    def updateITMOutput(self, txt):
           self._log_list._lines = self._log_list._lines[1:]
           self._log_list._lines.append(txt)
           self._log_list.draw()

    def updateProfOutput(self, lines):
           self._prof_list._lines = lines
           self._prof_list.draw()

class SWOEventHandler(object):
    """ Receive incoming DWT/ITM events and present/log them"""
    def __init__(self):
        self._overflows = 0
        self._resetGprof()
        self._prof_interval_s = 0.7
        self._tui = Tui()

    def onOverflow(self):
        self._overflows += 1

    def onPCSample(self, addr, function_name):
        # increment histogram bin for this function
        # TODO: check idle addr range, special bin for 'idle' if specified
        # HARDWIRE to test for LAK
        self.gprof_hist[function_name] = self.gprof_hist.get(function_name, 0) + 1
        self.gprof_tot += 1
        if self._gprof_accum_time() > self._prof_interval_s:
            sorted_hist = sorted(self.gprof_hist.items(), key=operator.itemgetter(1), reverse=True)
            prof = []
            for k,v in sorted_hist:
                percent = v*100.0 / self.gprof_tot
                #bar_len = int(percent * 122 / 100.0) # 2/3rds width
                #bar_len = 55
                bar_len = int(percent * self._tui.window_width_chars() / 120) # 2/3rds width
                bar_text = "{}  {:3.1f}".format(k,percent) + " "*self._tui.window_width_chars()
                bar = Font(bg=Colour.GREEN) + bar_text[:bar_len] + Font(bg=Colour.BLACK) + bar_text[bar_len:]
                prof.append(bar)
                # prof.append("{}  {:3.1f}".format(k,percent))

            # prof = ["{}  {:3.1f}".format(k,v*100/self.gprof_tot) for k,v in sorted_hist]
            self._tui.updateProfOutput(prof)
            #self._tui.updateITMOutput("PC: {:08x} {}".format(addr, function_name))
            self._resetGprof()

    def onDWTData(self, value, dwt_index, is_write):
        if is_write:
            writeDir = "<-"
        else:
            writeDir = "->"
        self._tui.updateITMOutput("DWT{}: {} {:02x}".format(dwt_index, writeDir, value))

    def onExceptionTrace(self, exc_number, exc_function ):
        func_map = ["RESERVED", "ENTER", "EXIT", "RE-ENTER"]
        self._tui.updateITMOutput("EXC: {}: {}".format(exc_number-16, func_map[exc_function]))

    def onTextOutput(self, text):
        self._tui.updateITMOutput(text)

    def _resetGprof(self):
        self.gprof_hist = {}
        self.gprof_tot = 0
        self._hist_start_time = time.time()

    def _gprof_accum_time(self):
        return time.time() - self._hist_start_time
