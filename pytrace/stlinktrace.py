#!/usr/bin/env python3

from swd import stlink

class StlinkTrace():
    """ST-Link SWO tracing class.
    This knows how to manage the arm Cortex-M ITM and TPIU via
    an ST-Link usb JTAG dongle as accessed by pyswd class (sold separately)."""

    def __init__(self, xtal_hz=72000000):
        self._stlink = stlink.Stlink()
        s = self._stlink.version.str
        self._xtal_hz = xtal_hz
        print(s)
        print(self._stlink.get_target_voltage())
        print(hex(self._stlink.get_coreid()))
        self._setupSWOTracing(self._xtal_hz)

    def startSWO(self):
        self._stlink.stop_trace_rx()
        self._stlink.start_trace_rx()

    def stopSWO(self):
        self._stlink.stop_trace_rx()
        
    def readSWO(self):
        num = self._stlink.get_trace_buffered_count()
        if ( num > 0 ):
            # Demeter?  This is obviously wrong but pyswd not our toy.
            return self._stlink._com.read_swo()
            #use  property getter;  return self._stlink.com.read_swo()
        else:
            return None

    def _w(self, addr, data):
        print("write_mem32 {:08x} <= {:04x}".format(addr, data));
        self._stlink.write_mem32(addr, list((data).to_bytes(4, byteorder='little')))
        # PKPK todo:  OR try set_mem32(addr, INT), writes one 4 byte number?
        print("last sts: {}".format(self._stlink.get_last_rw_status()))

    def _setupSWOTracing(self, xtal_hz):
        # captured via tshark from openocd with tpiu config
        self._w(0xe000edfc, 0x01000000)
        self._w(0xe0040004, 0x00000001)
        ## self._w(0xe0040010, 0x00000023)   # 72/35+1 = 2
        self._w(0xe0040010, int(xtal_hz/2000000 - 0.5))  # -1 + 0.5 for rounding => -0.5
        self._w(0xe00400f0, 0x00000002)
        self._w(0xe0040304, 0x00000100)
        self._w(0xe0042004, 0x00000327)
        self._w(0xe0000fb0, 0xc5acce55)
        self._w(0xe0000e80, 0x00010009)
        self._w(0xe0000e00, 0xffffffff)
        self._w(0xe0000e04, 0x00000000)
        self._w(0xe0000e08, 0x00000000)
        self._w(0xe0000e0c, 0x00000000)
        self._w(0xe0000e10, 0x00000000)
        self._w(0xe0000e14, 0x00000000)
        self._w(0xe0000e18, 0x00000000)
        self._w(0xe0000e1c, 0x00000000)
        self._w(0xe0002008, 0x00000000)
        self._w(0xe000200c, 0x00000000)
        self._w(0xe0002010, 0x00000000)
        self._w(0xe0002014, 0x00000000)
        self._w(0xe0002018, 0x00000000)
        self._w(0xe000201c, 0x00000000)
        self._w(0xe0002020, 0x00000000)
        self._w(0xe0002024, 0x00000000)
        self._w(0xe0001028, 0x00000000)
        self._w(0xe0001038, 0x00000000)
        self._w(0xe0001048, 0x00000000)
        self._w(0xe0001058, 0x00000000)
        self._w(0xe0042004, 0x00000327)
