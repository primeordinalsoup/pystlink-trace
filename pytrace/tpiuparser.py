#!/usr/bin/env python3
"""
  This module can parse the binary stream from an Arm Cortex-M TPIU and render
  the software packets (i.e. ITM print streams).

  For details of the ITM, DWT, TPIO registers and also the TPIO protocol please see:
    "ARMv7-M Architecture Reference Manual",  ARM DDI 0403D (ID021310)
    Ch C1 ARMv7-M Debug
"""

from subprocess import Popen, PIPE, run
from enum import Enum

DBG_EV_PORT_TIMESTAMP        = 8
DBG_EV_PORT_QFSIGDISPATCH    = 9
DBG_EV_PORT_QFSIGCOMPLETE    = 10
DBG_EV_PORT_QFSTATEENTRY     = 11
DBG_EV_PORT_FIRST_USER_EVENT = 20



class Address2LineResolver(object):
    """This encapsulates a subprocess to get addr2line info from the elf file, to
    convert raw address values to file:line references."""

    def __init__(self, elfFiles=None):
        self._p = []
        for elf in elfFiles:
            if elf:
                # print("addr2line, adding {}".format(elf))
                self._p.append(Popen(['addr2line', '-f', '-e', elf], universal_newlines=True, stdin=PIPE, stdout=PIPE))

    def resolve(self, addr):
        for p in self._p:
            if p:
                addrTxt = "{}\n".format(hex(addr))
                p.stdin.write(addrTxt)
                p.stdin.flush()
                line = p.stdout.readline().rstrip("\r\n")   # FUNCTION name (-f switch) or '??'
                discard = p.stdout.readline().rstrip("\r\n")  # file:linenumber or '??:0'
                # print("resolve got [{}]".format(line))
                if line != "??":
                    return line
                else:
                    continue
            else:
                return ""
        return ""

class Address2SymbolResolver(object):
    """This encapsulates a map to get symbol info from the elf file, to
    convert raw address values to symbol text."""

    def __init__(self, elfFiles=None):
        self._addr2sym = {}
        for elfFile in elfFiles:
            if elfFile:
                # print("addr2name, adding {}".format(elfFile))
                outputBytes = run(["nm", "-S", elfFile], stdout=PIPE).stdout.split(b'\n')
                output = [l.decode("utf-8") for l in outputBytes]
                for l in output:
                    symData = l.split(' ')
                    if len(symData) == 4 and symData[2] in "tTdDwWbB":
                        # is a valid symbol record, grab it
                        self._addr2sym[int(symData[0],16)] = {"sym": symData[3], "section": symData[2], "size": int(symData[1], 16) }

    def addr2size(self, addr):
        rec = self.addr2sym(addr)
        if rec:
            return rec['size']
        else:
            return None

    def addr2name(self, addr):
        rec = self.addr2sym(addr)
        if rec:
            return rec['sym']
        else:
            return None
        
    def addr2FormattedName(self, addr):
        name = self.addr2name(addr)
        if name:
            return " [{}]".format(name)
        else:
            return ""

    def name2addr(self, name):
        for k in self._addr2sym:
            if self._addr2sym[k]['sym'] == name:
                return k
        return None

    def name2size(self, name):
        for k in self._addr2sym:
            if self._addr2sym[k]['sym'] == name:
                return self._addr2sym[k]['size']
        return None

    def addr2sym(self, addr):
        return self._addr2sym.get(addr, None)

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
    """ data class for Software Instrumentation data """
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

class Type(Enum):
    UNKNOWN           = -1
    EVENT_COUNT       = 0
    EXCEPTION_TRACE   = 1
    PC_SAMPLE         = 2
    DATA_TRACE_PC     = 3
    DATA_TRACE_OFFSET = 4
    DATA_TRACE_DATA   = 5

class HSPData:
    """ data class for Hardware Source Packet data """
    def __init__(self, discriminator, lth):
        self.discriminator = discriminator
        if discriminator == 0:
            self.type = Type.EVENT_COUNT
        elif discriminator == 1:
            self.type = Type.EXCEPTION_TRACE
        elif discriminator == 2:
            self.type = Type.PC_SAMPLE
        elif discriminator >=8 and discriminator <= 23:
            packetType = (discriminator & 0x18) >> 3
            packetSubType = discriminator & 0x01
            self.dwtIndex = (discriminator & 0x06) >> 1
            if packetType == 1:
                if packetSubType == 1:
                    self.type = Type.DATA_TRACE_OFFSET
                else:
                    self.type = Type.DATA_TRACE_PC
            elif packetType == 2:
                self.type = Type.DATA_TRACE_DATA
                self.isWrite = (packetSubType == 1)
            else:
                self.type = Type.UNKNOWN
        else:
            self.type = Type.UNKNOWN
        self.expectedLth = lth
        self.lth = 0
        self.value = 0
        self.data = []

    def addByte(self, byte):
        self.value += byte << (self.lth*8) # shift in next byte (LSB first)
        self.lth += 1
        self.data.append(byte)

class _WaitingForHeader(State):
    def onRxByte(self, me, byte):
        #print "WAITING HEADER got byte 0x{:02x}".format(bffyte)
        if byte == 0x70:
            me.onEvent("Overflow")
        elif (byte & 0x7f) == 0x00:
            me.onEvent("Sync byte")
        elif ((byte & 0x03) != 0x00) and ((byte & 0x04) == 0x04):
            size = (2 ** (2+(byte & 0x03))) >> 3
            disc = (0xf8 & byte) >> 3
            me.trans(_HardwareBody(disc, size))
        elif ((byte & 0x03) != 0x00) and ((byte & 0x04) == 0x00):
            size = (2 ** (2+(byte & 0x03))) >> 3
            chan = (0xf8 & byte) >> 3
            me.trans(_SoftwareBody(chan, size))
        else:
            me.onEvent("DUFFBYTE", "{:02x}".format(byte))
            
class _SoftwareBody(State):
    def __init__(self, channel, payloadLth):
        self.len = payloadLth
        self.sit = SITData(channel, payloadLth)

    def onRxByte(self, me, byte):
        self.sit.addByte(byte)
        self.len -= 1
        if self.len == 0:
            me.onEvent("SIT", self.sit)
            me.trans(_WaitingForHeader())

class _HardwareBody(State):
    def __init__(self, discriminator, payloadLth):
        self.len = payloadLth
        self.hsp = HSPData(discriminator, payloadLth)

    def onRxByte(self, me, byte):
        self.hsp.addByte(byte)
        self.len -= 1
        if self.len == 0:
            me.onEvent("HSP_"+self.hsp.type.name, self.hsp)
            me.trans(_WaitingForHeader())

class TimeStamp(object):
    """ manages timebase from updates via SWO of
        the 50us TREF timer. """
    def __init__(self):
        self.time_50us = 0  # continuously incrementing value
        self.lastDiff = 0
        self._time_s = 0

    def update8(self, u8):
        """ increment timestamp using the 8bit modulo
        (LSB) of the 50us timer on the target. """
        self.lastDiff = (u8 - (self.time_50us & 0xff)) % 0x100
        # print "update8 {} {}".format(self.lastDiff, self.time_50us)
        self.time_50us += self.lastDiff

    def update16(self, u16):
        """ increment timestamp using the 8bit modulo
        (LSB) of the 50us timer on the target. """
        self._time_s += 0.01  # hack to count timer update msgs, as modulo addition not working
        self.lastDiff = (u16 - (self.time_50us & 0xffff)) % 0x10000
        self.time_50us += self.lastDiff
        if (self.time_50us == self.lastDiff):
            self.lastDiff = 0  # first update of full timer.

    def fmtNull(self):
        return "[---.------]"

    def fmtAbs(self):
        time_us = self.time_50us * 50
        return "[{:07.2f}]".format(self._time_s)
        #return "[{:03}.{:06}]".format(time_us/1000000, time_us%1000000)
        #return "[{}]".format(time_us/1000000)

    def fmtDiff(self):
        return "[   +{:06}]".format(self.lastDiff*50)

class TextOutput(object):
    """ formats single chars and integers to the terminal, including
        translating \n into correct EOL """
    def update8(self, u8):
        if u8 == ord('\n'):
            # embedded uses \n as newline, let python decide what is EOL
            print("")
        else:
            # print the single ascii char WITHOUT newline
            print(chr(u8), end="")

    def updateInt(self, u):
        print( "{}({})".format(u, hex(u)) )


class TPIUParser(object):
    """ For details of the TPIU protocol see the Armv7-M Architecture Reference Manual """
    gprof_hist = {}

    def __init__(self, syms, flags, elfFiles=None):
        self._sm = TPIUParserSM()
        self.syms = syms
        self._overflows = 0
        self._sm.setEventPrinting(False)
        self._sm.eventHandlers["SIT"] = self.onSIT
        self._sm.eventHandlers["HSP_PC_SAMPLE"] = self.onPC
        self._sm.eventHandlers["HSP_EXCEPTION_TRACE"] = self.onExcTrace
        self._sm.eventHandlers["HSP_DATA_TRACE_PC"] = self.onPC
        self._sm.eventHandlers["HSP_DATA_TRACE_DATA"] = self.onData
        self._sm.eventHandlers["Overflow"] = self.onOverflow
        # next ones disabled for now as not used and noise/berr sets them off
        self._sm.eventHandlers["HSP_DATA_TRACE_OFFSET"] = self.onOffset
        #self._sm.eventHandlers["HSP_UNKNOWN"] = self.onUnknown
        self._term0 = TextOutput()
        self._timestamp = TimeStamp()
        self._displayDataRead = ['r' in flag for flag in flags]
        self._displayDataWrite = ['w' in flag for flag in flags]
        self._dataUnique = ['u' in flag for flag in flags]
        self._lastData = [None for i in range(4)]
        self.addr2line = Address2LineResolver(elfFiles)
        self.addr2sym = Address2SymbolResolver(elfFiles)

    def getGprof(self):
        # return list(self.gprof_hist)
        #  TODO: use sorted() with custom 'key' function
        #  to creat list of k,v tuples sorted by value, so
        #  we can display ranked list.  ALSO remove
        #  provided 'idle' function eg prvIdleTask.lto_priv.407
        #  for POD (pass in by cli argument), and list it separately
        #  so we can show CPU gas gauge, i.e. percent busy/idle
        return self.gprof_hist

    def parseValue(self, intValue):
        self._sm.onRxByte(intValue)
        
    def parseBytes(self, bytes): 
        for intValue in bytes:
            # iterate bytesarray gives INTS
            self.parseValue(intValue)

    def onOverflow(self, ev, data):
        self._overflows += 1
        if self._overflows > 50:
            self._overflows = 0
            print("!! getting overflows, increase baudrate or reduce tracing load.")
    
    def onUnknown(self, ev, hsp):
        print("UNKNOWN: disc {:02x} len {}".format(hsp.discriminator, hsp.expectedLth))
        
    def onExcTrace(self, ev, hsp):
        """Hardware Source Packet - Exception Trace value event"""
        exc_number = hsp.data[0]  # exception number bits 7..0
        # blend in bit8 of exception number (from next byte)
        bit8 = hsp.data[1] & 0x01
        exc_number += bit8 << 8
        # get 'function', i.e. what is happening with this exception
        exc_func = (hsp.data[1] & 0x30) >> 4
        func_map = ["RESERVED", "ENTER", "EXIT", "RE-ENTER"]
        print("EXC: {}: {}".format(exc_number-16, func_map[exc_func]))

    def onPC(self, ev, hsp):
        """Hardware Source Packet - PC value event"""
        if self.addr2line:
            function_name = self.addr2line.resolve(hsp.value).rstrip("\r\n")
            # increment histogram bin for this function
            self.gprof_hist[function_name] = self.gprof_hist.get(function_name, 0) + 1
            where = "# " + function_name
        else:
            where = ""
        print("PC: {:08x} {}".format(hsp.value, where))

    def onData(self, ev, hsp):
        """Hardware Source Packet - data value event"""
        index = hsp.dwtIndex
        if hsp.isWrite:
            if not self._displayDataWrite[index]:
                return
            writeDir = "<-"
        else:
            if not self._displayDataRead[index]:
                return
            writeDir = "->"
        if self.syms[index]:
            dest = self.syms[index]
        else:
            dest = "DWT{}".format(index)
        output = "DWT{}: {} {} {:02x}{}".format(index, dest, writeDir, hsp.value, self.addr2sym.addr2FormattedName(hsp.value))
        if self._dataUnique[index] and self._lastData[index] != hsp.value:
            print(output)
            self._lastData[index] = hsp.value
        elif not self._dataUnique[index]:
            print(output)

    def onOffset(self, ev, hsp):
        """Hardware Source Packet - data OFFSET event"""
        print("DWT{}: R/W @ offset {:08x}".format(hsp.dwtIndex, hsp.value))

    def onSIT(self, ev, sit):
        # IF 0..7 do printf, null term for single, itoa for 2/4 bytes
        # NOTE: we only use a single term0 for all 8 channel, need an array of them.
        if sit.chan < 8:
            if sit.lth == 1:
                # normal printable single char (or line ending)
                self._term0.update8(sit.data[0])
            elif (sit.lth == 2) or (sit.lth == 4):
                # text output VALUE, format as dec(hex)
                self._term0.updateInt(sit.sum)
        elif sit.chan == DBG_EV_PORT_TIMESTAMP:
            #timestamp
            self._timestamp.update16(sit.sum)
            print("{}  timer update".format(self._timestamp.fmtAbs()))
        elif sit.chan == DBG_EV_PORT_QFSIGDISPATCH:
            #qf dispatch
            if sit.lth == 1:
                # timestamp byte
                self._timestamp.update8(sit.sum)
                pass
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
                pass
            elif sit.lth == 4:
                # address of new state
                addr = sit.sum
                print("{}  QTRAN addr {:08x}{}".format(self._timestamp.fmtAbs(), addr, self.addr2sym.addr2FormattedName(addr)))
