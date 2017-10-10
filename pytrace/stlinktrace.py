#!/usr/bin/env python3

# we package up via debian which makes an EGG, so we
# need to require to load the module
from pkg_resources import require
require("pyswd")
from swd import stlink
import math
import time
import queue, threading
import copy
#import usb

class StlinkTrace():
    """ST-Link SWO tracing class.
    This knows how to manage the arm Cortex-M ITM and TPIU via
    an ST-Link usb JTAG dongle as accessed by pyswd class (sold separately)."""

    def __init__(self, xtal_MHz=72, swo_baud=250000):
        self._stlink = stlink.Stlink()
        s = self._stlink.version.str
        self._xtal_MHz = xtal_MHz
        self._swo_baud = swo_baud
        print(s)
        print(self._stlink.get_target_voltage())
        print(hex(self._stlink.get_coreid()))
        # we remember all DWT settings for auto resetting after power cycles
        self._DWT = []
        # all False gives function value of 0, i.e. DWT disabled.
        dfltDWT = {"addr": 0, "size": 4, "getData": False, "getPC": False, "getOffset": False}
        for i in range(4):
            self._DWT.append(copy.deepcopy(dfltDWT))

        self._setupSWOTracing(self._xtal_MHz, self._swo_baud)
        self._readingSWO = False
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._pumpSWO)

    def _pumpSWO(self):
        """Thread function for pumping libUSB link to read
        SWO packets, check target OK, and reset target if
        needed."""
        zeroCnt = 0
        self._stlink.stop_trace_rx()
        self._stlink.start_trace_rx(baud_rate_hz=self._swo_baud)
        while self._readingSWO:
            v = self._stlink.get_target_voltage()
            if v < 1:
                print("powered OFF! - waiting for power up")
                while self._stlink.get_target_voltage() < 3:
                    pass
                print("target powered on!")
                time.sleep(0.1)
                self._stlink.leave_state()
                self._stlink.enter_debug_swd()
                self._setupSWOTracing(self._xtal_MHz, self._swo_baud)
                self._setAllWatches()
                self._stlink.stop_trace_rx()
                self._stlink.start_trace_rx(baud_rate_hz=self._swo_baud)
                zeroCNT = 0
            else:
                try:
                    num = self._stlink.get_trace_buffered_count()
                except:
                    break;
                #    num = 0
                #    pass
                if (num == 0):
                    zeroCnt += 1
                    if zeroCnt > 100:
                        # Stlink frozen? kick it.
                        #print("***** ST-Link FROZEN??!! - kicking it *****")
                        self._stlink.stop_trace_rx()
                        self._stlink.start_trace_rx(baud_rate_hz=self._swo_baud)
                        zeroCnt = 0
                elif ( num > 0 ):
                    self._queue.put(self._stlink.com.read_swo())
        self._stlink.stop_trace_rx()

    def startSWO(self):
        self._readingSWO = True
        self._thread.start()

    def stopSWO(self):
        self._readingSWO = False # will cause thread function to finish
        
    def readSWO(self):
        try:
            data = self._queue.get(timeout=1)
        except queue.Empty:
            data = None
        return data

    def _setAllWatches(self):
        for i in range(4):
            self._setWatch(i)
        
    def _setWatch(self, index):
        """ set the DWT(index) to the internally recorded setpoints. """
        print("setting DWT{}:".format(index))
        regOffset = 16 * index
        compRegAddr = 0xe0001020 + regOffset
        print("setting comp;  {:08x}  <- {}".format(compRegAddr, self._DWT[index]['addr']))
        self._stlink.set_mem32(compRegAddr, self._DWT[index]['addr'])      # DWT_COMPn

        addrBits = math.floor( math.log(self._DWT[index]['size'], 2) )
        maskRegAddr = 0xe0001024 + regOffset
        print("setting mask reg: {:08x} <- {}".format(maskRegAddr, addrBits))
        self._stlink.set_mem32(maskRegAddr, addrBits)  # DWT_MASKn

        function = 0
        if self._DWT[index]['getPC']:
            function |= 1 << 0
        if self._DWT[index]['getData']:
            function |= 1 << 1
        if self._DWT[index]['getOffset']:
            function |= 1 << 5
        funcRegAddr = 0xe0001028 + regOffset
        print("setting function reg: {:08x} <- {}".format(funcRegAddr, function))
        self._stlink.set_mem32(funcRegAddr, function) # DWT_FUNCTIONn

    def setWatch(self, index, addr, size = 4, getData = True, getPC = False, getOffset = False):
        """ set the DWT(index) to watch data access of address.  can get SWO output for
        the data (read and write), the PC for the instruction that accessed the addr, and the
        offset into the address block (address:size).  Note if requesting PC and offset you only
        get the offset due to limitations of the DWT. """
        self._DWT[index]['addr']      = addr
        self._DWT[index]['size']      = size
        self._DWT[index]['getPC']     = getPC
        self._DWT[index]['getData']   = getData
        self._DWT[index]['getOffset'] = getOffset
        self._setWatch(index)

    def _setupSWOTracing(self, xtal_MHz, baud):
        # captured via tshark from openocd with tpiu config
        self._stlink.set_mem32(0xe000edfc, 0x01000000)
        self._stlink.set_mem32(0xe0040004, 0x00000001)
        v = int(xtal_MHz*1000000/baud - 0.5)  # -1 + 0.5 for rounding => -0.5
        #print("XTAL {} MHz, baud {} => TPIU xtal REG VAL {}".format(xtal_MHz, baud, v))
        self._stlink.set_mem32(0xe0040010, v)
        self._stlink.set_mem32(0xe00400f0, 0x00000002)
        self._stlink.set_mem32(0xe0040304, 0x00000100)
        self._stlink.set_mem32(0xe0042004, 0x00000327)
        self._stlink.set_mem32(0xe0000fb0, 0xc5acce55)
        self._stlink.set_mem32(0xe0000e80, 0x00010009)
        self._stlink.set_mem32(0xe0000e00, 0xffffffff)
        self._stlink.set_mem32(0xe0000e04, 0x00000000)
        self._stlink.set_mem32(0xe0000e08, 0x00000000)
        self._stlink.set_mem32(0xe0000e0c, 0x00000000)
        self._stlink.set_mem32(0xe0000e10, 0x00000000)
        self._stlink.set_mem32(0xe0000e14, 0x00000000)
        self._stlink.set_mem32(0xe0000e18, 0x00000000)
        self._stlink.set_mem32(0xe0000e1c, 0x00000000)
        self._stlink.set_mem32(0xe0002008, 0x00000000)
        self._stlink.set_mem32(0xe000200c, 0x00000000)
        self._stlink.set_mem32(0xe0002010, 0x00000000)
        self._stlink.set_mem32(0xe0002014, 0x00000000)
        self._stlink.set_mem32(0xe0002018, 0x00000000)
        self._stlink.set_mem32(0xe000201c, 0x00000000)
        self._stlink.set_mem32(0xe0002020, 0x00000000)
        self._stlink.set_mem32(0xe0002024, 0x00000000)
        self._stlink.set_mem32(0xe0001028, 0x00000000)
        self._stlink.set_mem32(0xe0001038, 0x00000000)
        self._stlink.set_mem32(0xe0001048, 0x00000000)
        self._stlink.set_mem32(0xe0001058, 0x00000000)
        self._stlink.set_mem32(0xe0042004, 0x00000327)
