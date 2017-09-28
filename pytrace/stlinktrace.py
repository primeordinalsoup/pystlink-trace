#!/usr/bin/env python3

# we package up via debian which makes an EGG, so we
# need to require to load the module
from pkg_resources import require
require("pyswd")
from swd import stlink

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
        self._setupSWOTracing(self._xtal_MHz, self._swo_baud)

    def startSWO(self):
        self._stlink.stop_trace_rx()
        self._stlink.start_trace_rx(baud_rate_hz=self._swo_baud)

    def stopSWO(self):
        self._stlink.stop_trace_rx()
        
    def readSWO(self):
        num = self._stlink.get_trace_buffered_count()
        if ( num > 0 ):
            return self._stlink.com.read_swo()
        else:
            return None

    def _setupSWOTracing(self, xtal_MHz, baud):
        # captured via tshark from openocd with tpiu config
        self._stlink.set_mem32(0xe000edfc, 0x01000000)
        self._stlink.set_mem32(0xe0040004, 0x00000001)
        v = int(xtal_MHz*1000000/baud - 0.5)  # -1 + 0.5 for rounding => -0.5
        print("XTAL {} MHz, baud {} => TPIU xtal REG VAL {}".format(xtal_MHz, baud, v))
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
