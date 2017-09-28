#!/usr/bin/env python3
"""
  This module can parse the binary stream from an Arm Cortex-M TPIU and render
  the software packets (i.e. ITM print streams).
"""

DBG_EV_PORT_TIMESTAMP        = 8
DBG_EV_PORT_QFSIGDISPATCH    = 9
DBG_EV_PORT_QFSIGCOMPLETE    = 10
DBG_EV_PORT_QFSTATEENTRY     = 11
DBG_EV_PORT_FIRST_USER_EVENT = 20


class State:
    def onEntry(self, me):
        pass

    def onExit(self, me):
        pass


class StateMachine:
    def __init__(self, initialState):
        self.printEvents = True
        self.eventHandlers = {}
        self._enterInitialState(initialState)

    def setEventPrinting(self, enable):
        self.printEvents = enable

    def _enterInitialState(self, state):
        self.currState = state
        self.currState.onEntry(self)
        pass

    def trans(self, newState):
        self.currState.onExit(self)
        self.currState = newState
        self.currState.onEntry(self)

    def onRxByte(self, byte):
        self.currState.onRxByte(self, byte)

    def onEvent(self, event, data = None):
        if event in self.eventHandlers:
            self.eventHandlers[event](event, data)
        elif self.printEvents:
            print("Event! {}, data[{}]".format(event, data))


class TPIUParserSM(StateMachine):
    def __init__(self):
        StateMachine.__init__(self, _WaitingForHeader())

class SITData:
    """ data class for SIT data """
    def __init__(self, chan, lth):
        self.chan = chan
        self.expectedLth = lth
        self.lth = 0
        self.sum = 0
        self.data = []

    def addByte(self, byte):
        self.sum += byte << (self.lth*8) # shift in next byte (LSB first)
        self.lth += 1
        self.data.append(byte)

class _WaitingForHeader(State):
    def onRxByte(self, me, byte):
        #print "WAITING HEADER got byte 0x{:02x}".format(byte)
        if byte == 0x70:
            me.onEvent("Overflow")
        elif (byte & 0x7f) == 0x00:
            me.onEvent("Sync byte")
        elif ((byte & 0x03) != 0x00) and ((byte & 0x04) == 0x04):
            size = (2 ** (2+(byte & 0x03))) >> 3
            me.onEvent("HARDWARE SRC", "payload length {}".format(size))
            me.trans(_HardwareBody(size))
        elif ((byte & 0x03) != 0x00) and ((byte & 0x04) == 0x00):
            size = (2 ** (2+(byte & 0x03))) >> 3
            chan = (0xf8 & byte) >> 3
            me.onEvent("SOFTWARE SRC", "payload length {}".format(size))
            me.trans(_SoftwareBody(chan, size))

class _SoftwareBody(State):
    def __init__(self, channel, payloadLth):
        self.len = payloadLth
        self.sit = SITData(channel, payloadLth)
        #print "_SoftwareBody INIT"

    def onRxByte(self, me, byte):
        #print "SoftwareBody got byte {}, trans...".format(byte)
        self.sit.addByte(byte)
        self.len -= 1
        if self.len == 0:
            me.onEvent("SIT", self.sit)
            me.trans(_WaitingForHeader())

class _HardwareBody(State):
    def __init__(self, payloadLth):
        pass
        #print("_HardwareBody INIT")

    def onEntry(self, me):
        pass
        #print("HardwareBody: ENTRY")

    def onExit(self, me):
        pass
        #print("HardwareBody: EXIT")

    def onRxByte(self, me, byte):
        #print("HardwareBody got byte {}, trans...".format(byte))
        me.onEvent("Bob", "data about Bob")
        me.trans(_WaitingForHeader())
# here we assign the class variables shared by
# all TPIUParser objects.  They are references to
# the locally scoped state handler objects (singletons).

class TimeStamp(object):
    """ manages timebase from updates via SWO of
        the 50us TREF timer. """
    def __init__(self):
        self.time_50us = 0  # continuously incrementing value
        self.lastDiff = 0

    def update8(self, u8):
        """ increment timestamp using the 8bit modulo
        (LSB) of the 50us timer on the target. """
        self.lastDiff = (u8 - (self.time_50us & 0xff)) % 0x100
        # print "update8 {} {}".format(self.lastDiff, self.time_50us)
        self.time_50us += self.lastDiff

    def update16(self, u16):
        """ increment timestamp using the 8bit modulo
        (LSB) of the 50us timer on the target. """
        self.lastDiff = (u16 - (self.time_50us & 0xffff)) % 0x10000
        self.time_50us += self.lastDiff
        if (self.time_50us == self.lastDiff):
            self.lastDiff = 0  # first update of full timer.

    def fmtNull(self):
        return "[---.------]"

    def fmtAbs(self):
        time_us = self.time_50us * 50
        return "[{:03}.{:06}]".format(time_us/1000000, time_us%1000000)

    def fmtDiff(self):
        return "[   +{:06}]".format(self.lastDiff*50)

class TextOutput(object):
    """ manages a single channel's text output, collating
        and formatting it until a '\n'."""
    def __init__(self):
        self.line = ""
        self._terminated = False

    def update8(self, u8):
        if u8 == ord('\n'):
            self._terminated = True
        else:
            self.line += chr(u8)

    def updateInt(self, u):
        self.line += "{}({})".format(u, hex(u))

    def reset(self):
        self.line = ""
        self._terminated = False

    def isComplete(self):
        return self._terminated


class TPIUParser(object):
    def __init__(self):
        self._sm = TPIUParserSM()
        self._sm.setEventPrinting(False)
        self._sm.eventHandlers["SIT"] = self.onSIT
        self._term0 = TextOutput()
        self._timestamp = TimeStamp()

    def parseValue(self, intValue):
        self._sm.onRxByte(intValue)
        
    def parseBytes(self, bytes): 
        for intValue in bytes:
            # iterate bytesarray gives INTS
            self.parseValue(intValue)

    def onSIT(self, ev, sit):
        # IF 0..7 do printf, null term for single, itoa for 2/4 bytes
        # NOTE: we only use a single term0 for all 8 channel, need an array of them.
        if sit.chan < 8:
            if sit.lth == 1:
                # normal printable char (or line ending)
                self._term0.update8(sit.data[0])
                if self._term0.isComplete():
                    # output the completed line
                    print(self._term0.line)
                    #print("{}{}".format(self._timestamp.fmtDiff(), self._term0.line))
                    self._term0.reset()
            elif (sit.lth == 2) or (sit.lth == 4):
                # text output VALUE, format as dec(hex)
                self._term0.updateInt(sit.sum)
        elif sit.chan == DBG_EV_PORT_TIMESTAMP:
            #timestamp
            self._timestamp.update16(sit.sum)
            #print("{}  timer update".format(self._timestamp.fmtAbs()))
        elif sit.chan == DBG_EV_PORT_QFSIGDISPATCH:
            #qf dispatch
            if sit.lth == 1:
                # timestamp byte
                self._timestamp.update8(sit.sum)
            elif sit.lth == 4:
                # AO index plus signum
                ao = sit.data[3]
                sig = sit.data[0] + (sit.data[1]<<8) + (sit.data[2]<<16)
                # print "{}  ao sig;  {:02x} -> {:04x}".format(self._timestamp.fmtDiff(), ao, sig)
                print("{}  ao sig;  {:02x} -> {:04x}".format(self._timestamp.fmtAbs(), ao, sig))
        elif sit.chan == DBG_EV_PORT_QFSTATEENTRY:
            # AO new state address
            if sit.lth == 1:
                # timestamp byte
                self._timestamp.update8(sit.sum)
            elif sit.lth == 4:
                # AO index plus signum
                addr = sit.sum
                print("{}  QTRAN addr {:08x}".format(self._timestamp.fmtDiff(), addr))
