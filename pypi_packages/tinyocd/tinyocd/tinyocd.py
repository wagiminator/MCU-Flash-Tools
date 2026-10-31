#!/usr/bin/env python3
# ===================================================================================
# Project:   tinyOCD - Programming Tool for STM32, PY32 and SAMD Microcontrollers
#                      via CMSIS-DAP (DAPLink), ST-Link or J-Link
# Version:   v1.0
# Year:      2026
# Author:    Stefan Wagner
# Github:    https://github.com/wagiminator
# License:   MIT License
# ===================================================================================
#
# Description:
# ------------
# Simple Python tool for flashing ARM Cortex-M microcontrollers via SWD using a
# CMSIS-DAP v1/v2 (DAPLink), ST-Link V2/V2-1/V3 or SEGGER J-Link programmer.
# Programmer and chip are detected automatically. The flash memory is programmed
# by a small generic flash loader that runs in the RAM of the target.
# Currently supports:
# - STM32: C0, F0, F1, F2, F3, F4, F7, G0, G4, H5, H7, L0, L1, L4, L4+, L5, U0,
#          U3, U5, WB, WBA, WL
# - PUYA:  PY32F002A, PY32F003, PY32F030, PY32F002B, PY32F071, PY32F072
#          (and compatible, e.g. AIR001)
# - ATMEL: ATSAMD09, ATSAMD10, ATSAMD11, ATSAMD20, ATSAMD21, ATSAMDA1, ATSAML21,
#          ATSAML22, ATSAMC20, ATSAMC21, ATSAMD51, ATSAME51, ATSAME53, ATSAME54
#
# References:
# -----------
# tinyOCD is inspired by and uses information from:
# - pyOCD:            https://github.com/pyocd/pyOCD
# - OpenOCD:          https://openocd.org
# - Black Magic Debug: https://github.com/blackmagic-debug/blackmagic
# - probe-rs:         https://github.com/probe-rs/probe-rs
# - PUYA PY32 SDK:    https://github.com/IOsetting/py32f0-template
#
# Dependencies:
# -------------
# - pyusb
# - libusb-package (optional, recommended on Windows)
# - hidapi (optional, for CMSIS-DAP v1 HID probes on Windows and macOS)
#
# Operating Instructions:
# -----------------------
# You need to install PyUSB to use tinyOCD. Install it via "pip install pyusb".
#
# Linux users need permission to access the programmer. Run:
# echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0483", MODE="666"' | sudo tee /etc/udev/rules.d/99-tinyocd.rules
# echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1366", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-tinyocd.rules
# echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0d28", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-tinyocd.rules
# echo 'KERNEL=="hidraw*", ATTRS{idVendor}=="0d28", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-tinyocd.rules
# sudo udevadm control --reload-rules
# (add further lines for other CMSIS-DAP vendor IDs, e.g. 2e8a, c251, 1a86)
#
# On Windows, ST-Link (with ST driver) and CMSIS-DAP v2 (WinUSB) normally work out
# of the box with libusb. A J-Link must use the WinUSB driver (J-Link Configurator:
# "Use WinUSB") or a libusb driver installed with Zadig (https://zadig.akeo.ie/).
#
# Connect the programmer to your PC and to the SWD interface of your MCU
# (SWDIO, SWCLK, GND, optionally NRST and VCC).
# Run:
# - tinyocd.py [-h] [-p {auto,cmsis-dap,stlink,jlink}] [-s SPEED] [-u] [-l] [-e]
#              [-B] [-G] [-R] [-f FLASH] [-t]
#   -h, --help                show help message and exit
#   -p, --probe               select programmer type (default: auto)
#   -s SPEED, --speed SPEED   SWD clock in kHz (default: 1000)
#   -u, --unlock              unlock chip (remove read protection, erases chip)
#   -l, --lock                lock chip (set read protection)
#   -e, --erase               perform a whole chip erase (implied with -f)
#   -B, --bootpin             make BOOT0 pin usable for embedded bootloader
#   -G, --pingpio             make NRST pin a GPIO pin
#   -R, --pinreset            make NRST pin a reset pin
#   -f FLASH, --flash FLASH   write BIN file to flash and verify
#   -t, --list                list supported chips
#
# - Example:
#   python3 tinyocd.py -f firmware.bin


import os
import sys
import time
import struct
import argparse

try:
    import usb.core
    import usb.util
except ImportError:
    usb = None


# ===================================================================================
# Main Function
# ===================================================================================

def _main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Minimal command line interface for tinyOCD')
    parser.add_argument('-p', '--probe',    default='auto', choices=['auto', 'cmsis-dap', 'stlink', 'jlink'],
                                            help='select programmer type (default: auto)')
    parser.add_argument('-s', '--speed',    type=int, default=1000, help='SWD clock in kHz (default: 1000)')
    parser.add_argument('-u', '--unlock',   action='store_true', help='unlock chip (remove read protection, erases chip)')
    parser.add_argument('-l', '--lock',     action='store_true', help='lock chip (set read protection)')
    parser.add_argument('-e', '--erase',    action='store_true', help='perform a whole chip erase (implied with -f)')
    parser.add_argument('-B', '--bootpin',  action='store_true', help='make BOOT0 pin usable for embedded bootloader')
    parser.add_argument('-G', '--pingpio',  action='store_true', help='make NRST pin a GPIO pin')
    parser.add_argument('-R', '--pinreset', action='store_true', help='make NRST pin a reset pin')
    parser.add_argument('-f', '--flash',    help='write BIN file to flash and verify')
    parser.add_argument('-t', '--list',     action='store_true', help='list supported chips')
    args = parser.parse_args(sys.argv[1:])

    # List supported chips
    if args.list:
        print_supported_chips()
        sys.exit(0)

    # Check arguments
    if not any( (args.unlock, args.lock, args.erase, args.bootpin, args.pingpio, args.pinreset, args.flash) ):
        print('No arguments - no action!')
        sys.exit(0)
    if args.pingpio and args.pinreset:
        sys.stderr.write('ERROR: -G and -R cannot be used together!\n')
        sys.exit(1)
    if args.speed < 1 or args.speed > 50000:
        sys.stderr.write('ERROR: SWD clock must be 1 - 50000 kHz!\n')
        sys.exit(1)

    # Read binary file
    data = None
    if args.flash is not None:
        try:
            with open(args.flash, 'rb') as f: data = f.read()
        except Exception as ex:
            sys.stderr.write('ERROR: %s!\n' % str(ex))
            sys.exit(1)
        if len(data) == 0:
            sys.stderr.write('ERROR: BIN file is empty!\n')
            sys.exit(1)

    # Establish connection to programmer
    try:
        print('Searching for programmer ...')
        probe = find_probe(args.probe)
        print('SUCCESS: Found %s.' % probe.name)
        if probe.voltage:
            print('Target voltage: %.2f V' % probe.voltage)
    except Exception as ex:
        sys.stderr.write('ERROR: %s!\n' % str(ex))
        sys.exit(1)

    # Performing actions
    ocd = None
    try:
        print('Connecting to MCU ...')
        ocd = Target(probe, args.speed)
        ocd.connect()
        if ocd.chip.flash_size:
            print('SUCCESS: Connected to %s with %d bytes of flash.' % (ocd.chip.name, ocd.chip.flash_size))
        else:
            print('SUCCESS: Connected to %s.' % ocd.chip.name)
        if ocd.locked:
            print('Chip is read protected (locked).')

        # Check option support before doing anything
        if args.bootpin and not ocd.chip.has_bootpin:
            raise Exception('BOOT0 pin configuration is not supported on this chip')
        if (args.pingpio or args.pinreset) and not ocd.chip.has_nrst:
            raise Exception('NRST pin configuration is not supported on this chip')
        if args.lock and not ocd.chip.has_lock:
            raise Exception('Read protection is not supported on this chip')
        if ocd.locked and not args.unlock and (args.erase or data is not None or args.bootpin or args.pingpio or args.pinreset):
            raise Exception('Chip is locked, use -u to unlock it (erases the chip)')
        if data is not None and not ocd.locked:
            ocd.check_image(data)

        # Unlock chip
        if args.unlock:
            print('Unlocking chip ...')
            if ocd.unlock():
                print('SUCCESS: Chip is unlocked.')
            if data is not None:
                ocd.check_image(data)

        # Perform chip erase
        if args.erase or data is not None:
            print('Performing whole chip erase ...')
            ocd.erase()
            print('SUCCESS: Chip is erased.')

        # Flash binary file
        if data is not None:
            print('Flashing %s to %s ...' % (args.flash, ocd.chip.name))
            ocd.flash_data(data)
            print('Verifying ...')
            ocd.verify_data(data)
            print('SUCCESS: %d bytes written and verified.' % len(data))

        # Configure option bytes
        if args.bootpin:
            print('Making BOOT0 pin usable for embedded bootloader ...')
            ocd.set_bootpin()
            print('SUCCESS: BOOT0 pin is now usable.')
        if args.pingpio:
            print('Configuring NRST pin as GPIO pin ...')
            ocd.set_nrst(gpio=True)
            print('SUCCESS: NRST is now a GPIO pin.')
        if args.pinreset:
            print('Configuring NRST pin as reset pin ...')
            ocd.set_nrst(gpio=False)
            print('SUCCESS: NRST is now a reset pin.')

        # Lock chip
        if args.lock:
            print('Locking chip ...')
            ocd.lock()
            print('SUCCESS: Chip is locked.')

        ocd.exit()

    except Exception as ex:
        sys.stderr.write('ERROR: %s!\n' % str(ex))
        try:
            if ocd is not None:
                ocd.exit(run=False)
            else:
                probe.close()
        except:
            pass
        sys.exit(1)

    print('DONE.')
    sys.exit(0)


# ===================================================================================
# Error Classes
# ===================================================================================

class ProbeError(Exception):
    pass

class TransferFault(Exception):
    pass


# ===================================================================================
# USB Helper Functions
# ===================================================================================

# Get libusb backend (libusb-package on Windows if available)
def usb_backend():
    try:
        import libusb_package
        return libusb_package.get_libusb1_backend()
    except Exception:
        return None

# Find all USB devices
def usb_devices():
    if usb is None:
        raise ProbeError('PyUSB is not installed, run "pip install pyusb"')
    try:
        return list(usb.core.find(find_all=True, backend=usb_backend()))
    except usb.core.NoBackendError:
        raise ProbeError('No libusb backend found, install libusb (or "pip install libusb-package")')

# Get USB string descriptor (None if not readable)
def usb_string(dev, index):
    if not index:
        return None
    try:
        return usb.util.get_string(dev, index)
    except Exception:
        return None

# Find programmer
def find_probe(kind='auto'):
    errors = list()
    devices = usb_devices()
    for dev in devices:
        candidates = list()
        if kind in ('auto', 'stlink') and dev.idVendor == STLINK_VID and dev.idProduct in STLINK_PIDS:
            candidates.append(STLink)
        if kind in ('auto', 'jlink') and dev.idVendor == JLINK_VID:
            candidates.append(JLink)
        if kind in ('auto', 'cmsis-dap'):
            candidates.append(CMSISDAP.from_usb)
        for probe_type in candidates:
            try:
                probe = probe_type(dev)
                if probe is not None:
                    return probe
            except usb.core.USBError as ex:
                errors.append('%04x:%04x: %s' % (dev.idVendor, dev.idProduct, ex))
            except ProbeError as ex:
                errors.append(str(ex))
    if kind in ('auto', 'cmsis-dap'):
        probe = CMSISDAP.from_hidapi()
        if probe is not None:
            return probe
    if errors:
        raise ProbeError('No usable programmer found (%s)' % '; '.join(errors))
    raise ProbeError('No programmer found (check connection, driver and USB access permissions)')


# ===================================================================================
# Probe Base Class (memory access interface)
# ===================================================================================

class Probe:
    name    = 'probe'
    voltage = None

    # Must be implemented: connect(speed_khz) -> DPIDR, reconnect(), close(), set_reset(asserted),
    # read_mem(addr, size) -> bytes, write_mem(addr, data), read16/write16/read8/write8,
    # read_ap(ap, reg), read_dp(reg)

    def read32(self, addr):
        return struct.unpack('<I', self.read_mem(addr, 4))[0]

    def write32(self, addr, value):
        self.write_mem(addr, struct.pack('<I', value & 0xFFFFFFFF))

    # Split transfers at 1 KB boundaries (TAR auto-increment limit)
    @staticmethod
    def _chunks(addr, size, maxsize):
        while size:
            n = min(size, maxsize, 0x400 - (addr & 0x3FF))
            yield addr, n
            addr += n
            size -= n


# ===================================================================================
# Raw SWD Probe (ADIv5 DP/MEM-AP access on top of DAP transfers)
# ===================================================================================

DP_DPIDR    = 0x00
DP_ABORT    = 0x00
DP_CTRLSTAT = 0x04
DP_SELECT   = 0x08
DP_RDBUFF   = 0x0C
AP_CSW      = 0x00
AP_TAR      = 0x04
AP_DRW      = 0x0C
AP_BASE     = 0xF8
AP_IDR      = 0xFC

ABORT_CLEAR = 0x1E          # ORUNERRCLR | WDERRCLR | STKERRCLR | STKCMPCLR
CSW_DEFAULT = 0x23000000    # HPROT[1] | MasterType (debug) | reserved
CSW_INC     = 0x00000010    # single address increment
CSW_SIZE    = {1: 0, 2: 1, 4: 2}

class RawSWDProbe(Probe):
    ORUNDETECT = 0          # overrun detection (set by probes that always do the data phase)

    def __init__(self):
        self._select = None
        self._csw = None
        self.ap = 0

    # --- to be implemented by subclass ---
    # _swj_sequence(nbits, data), _transfer(ops) -> list of read values
    # ops: list of (apndp, rnw, addr, value)

    def _write_block(self, ap, reg, words):
        self._transfer([(ap, 0, reg, w) for w in words])

    def _read_block(self, ap, reg, count):
        return self._transfer([(ap, 1, reg, 0)] * count)

    # --- SWD line handling ---
    def _swd_switch(self):
        self._swj_sequence(56, b'\xff' * 7)                 # line reset
        self._swj_sequence(16, b'\x9e\xe7')                 # JTAG to SWD sequence
        self._swj_sequence(56, b'\xff' * 7)                 # line reset
        self._swj_sequence(16, b'\x00\x00')                 # idle cycles

    def dp_connect(self):
        self._select = None
        self._csw = None
        dpidr = None
        for _ in range(3):
            try:
                self._swd_switch()
                dpidr = self._transfer([(0, 1, DP_DPIDR, 0)])[0]
                break
            except (ProbeError, TransferFault):
                time.sleep(0.01)
        if dpidr is None or dpidr in (0, 0xFFFFFFFF):
            raise ProbeError('No target found (check SWD connection and target power)')
        self._transfer([(0, 0, DP_ABORT, ABORT_CLEAR)])
        self._transfer([(0, 0, DP_CTRLSTAT, 0x50000000 | self.ORUNDETECT)])
        for _ in range(100):
            if (self._transfer([(0, 1, DP_CTRLSTAT, 0)])[0] & 0xA0000000) == 0xA0000000:
                break
            time.sleep(0.001)
        else:
            raise ProbeError('Target debug power-up failed')
        return dpidr

    def clear_errors(self):
        try:
            self._transfer([(0, 0, DP_ABORT, ABORT_CLEAR)])
        except Exception:
            pass
        self._select = None
        self._csw = None

    # --- AP/DP access ---
    def _sel_ops(self, reg):
        sel = (self.ap << 24) | (reg & 0xF0)
        if sel != self._select:
            self._select = sel
            return [(0, 0, DP_SELECT, sel)]
        return []

    def read_dp(self, reg):
        return self._transfer([(0, 1, reg, 0)])[0]

    def read_ap(self, ap, reg):
        old = self.ap
        self.ap = ap
        try:
            ops = self._sel_ops(reg) + [(1, 1, reg & 0x0C, 0)]
            return self._transfer(ops)[-1]
        finally:
            self.ap = old

    def _csw_ops(self, size, inc=True):
        csw = CSW_DEFAULT | CSW_SIZE[size] | (CSW_INC if inc else 0)
        ops = self._sel_ops(AP_CSW)
        if csw != self._csw:
            self._csw = csw
            ops.append((1, 0, AP_CSW, csw))
        return ops

    def _safe(self, func, *args):
        try:
            return func(*args)
        except TransferFault:
            self.clear_errors()
            raise

    # --- memory access ---
    def read_mem(self, addr, size):
        return self._safe(self._read_mem, addr, size)

    def _read_mem(self, addr, size):
        result = bytearray()
        for a, n in self._chunks(addr, size, 0x400):
            self._transfer(self._csw_ops(4) + [(1, 0, AP_TAR, a)])
            words = self._read_block(1, AP_DRW, n // 4)
            result += struct.pack('<%dI' % len(words), *words)
        return bytes(result)

    def write_mem(self, addr, data):
        return self._safe(self._write_mem, addr, data)

    def _write_mem(self, addr, data):
        if len(data) == 4:                                  # single word: one transfer incl. error check
            ops = self._csw_ops(4) + [(1, 0, AP_TAR, addr), (1, 0, AP_DRW, struct.unpack('<I', data)[0]),
                                      (0, 1, DP_CTRLSTAT, 0)]
            self._check_sticky(self._transfer(ops)[-1])
            return
        pos = 0
        for a, n in self._chunks(addr, len(data), 0x400):
            words = struct.unpack('<%dI' % (n // 4), data[pos:pos + n])
            self._transfer(self._csw_ops(4) + [(1, 0, AP_TAR, a)])
            self._write_block(1, AP_DRW, words)
            pos += n
        self._check_sticky(self.read_dp(DP_CTRLSTAT))

    # Write errors may be reported delayed (STICKYERR in CTRL/STAT)
    def _check_sticky(self, ctrlstat):
        if ctrlstat & 0x22:
            raise TransferFault('memory write fault')

    def _read_sized(self, addr, size):
        ops = self._csw_ops(size, False) + [(1, 0, AP_TAR, addr), (1, 1, AP_DRW, 0)]
        value = self._transfer(ops)[-1]
        return (value >> (8 * (addr & 3))) & ((1 << (8 * size)) - 1)

    def _write_sized(self, addr, size, value):
        ops = self._csw_ops(size, False) + [(1, 0, AP_TAR, addr), (1, 0, AP_DRW, value << (8 * (addr & 3))),
                                            (0, 1, DP_CTRLSTAT, 0)]
        self._check_sticky(self._transfer(ops)[-1])

    def read16(self, addr):
        return self._safe(self._read_sized, addr, 2)

    def write16(self, addr, value):
        self._safe(self._write_sized, addr, 2, value & 0xFFFF)

    def read8(self, addr):
        return self._safe(self._read_sized, addr, 1)

    def write8(self, addr, value):
        self._safe(self._write_sized, addr, 1, value & 0xFF)

    def reconnect(self):
        return self.dp_connect()


# ===================================================================================
# CMSIS-DAP Probe (v1 HID and v2 bulk)
# ===================================================================================

class CMSISDAP(RawSWDProbe):
    def __init__(self, transport, name):
        super().__init__()
        self.t = transport
        self.packet_size = 64
        self.name = name
        try:
            self.packet_size = max(64, struct.unpack('<H', self._info(0xFF)[:2])[0])
        except Exception:
            self.packet_size = 64
        self.t.packet_size = self.packet_size
        try:
            self.fw = self._info(0x04).decode('ascii', 'ignore').strip('\x00')
        except Exception:
            self.fw = ''
        if self.fw:
            self.name += ' (firmware %s)' % self.fw

    @staticmethod
    def from_usb(dev):
        product = usb_string(dev, dev.iProduct) or ''
        try:
            cfg = dev.get_active_configuration()
        except Exception:
            try:
                cfg = dev[0]                                # configuration descriptor only
            except Exception:
                return None
        hid_intf = None
        for intf in cfg:
            istr = usb_string(dev, intf.iInterface) or ''
            if 'CMSIS-DAP' not in istr.upper() and 'CMSIS-DAP' not in product.upper():
                continue
            if intf.bInterfaceClass == 0xFF:
                eps = [ep for ep in intf if usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK]
                if len(eps) >= 2:
                    return CMSISDAP(_DAPBulk(dev, intf, eps), 'CMSIS-DAP v2 "%s"' % product)
            elif intf.bInterfaceClass == 0x03 and hid_intf is None:
                hid_intf = intf
        if hid_intf is not None:
            return CMSISDAP(_DAPHidUsb(dev, hid_intf), 'CMSIS-DAP v1 "%s"' % product)
        return None

    @staticmethod
    def from_hidapi():
        try:
            import hid
        except Exception:
            return None
        for d in hid.enumerate():
            product = d.get('product_string') or ''
            if 'CMSIS-DAP' in product.upper():
                try:
                    return CMSISDAP(_DAPHidApi(hid, d['path']), 'CMSIS-DAP v1 "%s"' % product)
                except Exception:
                    continue
        return None

    def _cmd(self, data):
        resp = self.t.xfer(bytes(data))
        if len(resp) < 1 or resp[0] != data[0]:
            raise ProbeError('CMSIS-DAP: unexpected response to command 0x%02x' % data[0])
        return resp

    def _info(self, id):
        resp = self._cmd([0x00, id])
        return bytes(resp[2:2 + resp[1]])

    def connect(self, speed_khz):
        if self._cmd([0x02, 0x01])[1] != 0x01:                          # DAP_Connect (SWD)
            raise ProbeError('CMSIS-DAP: SWD mode not supported')
        self._cmd([0x11] + list(struct.pack('<I', speed_khz * 1000)))     # DAP_SWJ_Clock
        self._cmd([0x04, 0x02, 0x80, 0x00, 0x00, 0x00])                   # DAP_TransferConfigure
        self._cmd([0x13, 0x00])                                           # DAP_SWD_Configure
        self._speed = speed_khz
        return self.dp_connect()

    def close(self):
        try:
            self._cmd([0x03])                                             # DAP_Disconnect
        except Exception:
            pass
        self.t.close()

    def set_reset(self, asserted):
        self._cmd([0x10, 0x00 if asserted else 0x80, 0x80, 0, 0, 0, 0])   # DAP_SWJ_Pins (nRESET)

    def _swj_sequence(self, nbits, data):
        self._cmd([0x12, nbits & 0xFF] + list(data))

    def _check_ack(self, ack):
        if ack == 1:
            return
        if ack == 2:
            raise TransferFault('SWD WAIT timeout')
        if ack == 4:
            raise TransferFault('SWD FAULT')
        if ack & 0x08:
            raise ProbeError('SWD parity error')
        raise ProbeError('SWD no response from target')

    def _transfer(self, ops):
        result = list()
        i = 0
        while i < len(ops):
            req = bytearray([0x05, 0x00, 0x00])
            nreads = 0
            n = 0
            while i + n < len(ops):
                ap, rnw, reg, val = ops[i + n]
                need = 1 + (0 if rnw else 4)
                if len(req) + need > self.packet_size or 3 + 4 * (nreads + rnw) > self.packet_size or n >= 255:
                    break
                req.append(ap | (rnw << 1) | (reg & 0x0C))
                if not rnw:
                    req += struct.pack('<I', val & 0xFFFFFFFF)
                nreads += rnw
                n += 1
            req[2] = n
            resp = self._cmd(req)
            if resp[1] != n:
                self._check_ack(resp[2])
                raise ProbeError('CMSIS-DAP transfer incomplete')
            self._check_ack(resp[2])
            result += struct.unpack('<%dI' % nreads, bytes(resp[3:3 + 4 * nreads]))
            i += n
        return result

    def _write_block(self, ap, reg, words):
        maxw = (self.packet_size - 5) // 4
        for i in range(0, len(words), maxw):
            chunk = words[i:i + maxw]
            req = bytearray([0x06, 0x00]) + struct.pack('<H', len(chunk)) + bytes([ap | (reg & 0x0C)])
            req += struct.pack('<%dI' % len(chunk), *chunk)
            resp = self._cmd(req)
            if struct.unpack('<H', bytes(resp[1:3]))[0] != len(chunk):
                self._check_ack(resp[3])
                raise ProbeError('CMSIS-DAP block transfer incomplete')
            self._check_ack(resp[3])

    def _read_block(self, ap, reg, count):
        maxw = (self.packet_size - 4) // 4
        result = list()
        while count:
            n = min(count, maxw)
            req = bytearray([0x06, 0x00]) + struct.pack('<H', n) + bytes([ap | 0x02 | (reg & 0x0C)])
            resp = self._cmd(req)
            if struct.unpack('<H', bytes(resp[1:3]))[0] != n:
                self._check_ack(resp[3])
                raise ProbeError('CMSIS-DAP block transfer incomplete')
            self._check_ack(resp[3])
            result += struct.unpack('<%dI' % n, bytes(resp[4:4 + 4 * n]))
            count -= n
        return result


# CMSIS-DAP v2 transport (bulk endpoints)
class _DAPBulk:
    def __init__(self, dev, intf, eps):
        self.dev = dev
        self.intf = intf.bInterfaceNumber
        self.ep_out = [ep for ep in eps if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT][0]
        self.ep_in = [ep for ep in eps if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN][0]
        self.packet_size = 64
        usb.util.claim_interface(dev, self.intf)
        try:                                                    # flush stale responses
            while True:
                self.ep_in.read(1024, 10)
        except Exception:
            pass

    def xfer(self, data):
        self.ep_out.write(data, 1000)
        return bytes(self.ep_in.read(max(self.packet_size, 64) * 2, 2000))

    def close(self):
        try:
            usb.util.release_interface(self.dev, self.intf)
            usb.util.dispose_resources(self.dev)
        except Exception:
            pass


# CMSIS-DAP v1 transport via libusb (HID interrupt endpoints)
class _DAPHidUsb:
    def __init__(self, dev, intf):
        self.dev = dev
        self.intf = intf.bInterfaceNumber
        self.packet_size = 64
        try:
            if dev.is_kernel_driver_active(self.intf):
                dev.detach_kernel_driver(self.intf)
        except Exception:
            pass
        usb.util.claim_interface(dev, self.intf)
        self.ep_in = None
        self.ep_out = None
        for ep in intf:
            if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                self.ep_in = ep
            else:
                self.ep_out = ep
        if self.ep_in is None:
            raise ProbeError('CMSIS-DAP v1: no IN endpoint')

    def xfer(self, data):
        data = bytes(data) + b'\x00' * (self.packet_size - len(data))
        if self.ep_out is not None:
            self.ep_out.write(data, 1000)
        else:
            self.dev.ctrl_transfer(0x21, 0x09, 0x0200, self.intf, data, 1000)
        return bytes(self.ep_in.read(self.packet_size, 2000))

    def close(self):
        try:
            usb.util.release_interface(self.dev, self.intf)
            usb.util.dispose_resources(self.dev)
        except Exception:
            pass


# CMSIS-DAP v1 transport via hidapi
class _DAPHidApi:
    def __init__(self, hid, path):
        self.h = hid.device()
        self.h.open_path(path)
        self.packet_size = 64

    def xfer(self, data):
        data = bytes(data) + b'\x00' * (self.packet_size - len(data))
        self.h.write(b'\x00' + data)
        resp = self.h.read(self.packet_size, 2000)
        if not resp:
            raise ProbeError('CMSIS-DAP v1: no response')
        return bytes(resp)

    def close(self):
        try:
            self.h.close()
        except Exception:
            pass


# ===================================================================================
# SEGGER J-Link Probe (SWD via native USB protocol)
# ===================================================================================

JLINK_VID = 0x1366

class JLink(RawSWDProbe):
    ORUNDETECT = 1

    def __init__(self, dev):
        super().__init__()
        self.dev = dev
        try:
            dev.set_configuration()
        except Exception:
            pass
        cfg = dev.get_active_configuration()
        self.intf = None
        for intf in cfg:
            eps = [ep for ep in intf if usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK]
            if intf.bInterfaceClass == 0xFF and len(eps) == 2:
                self.intf = intf
                break
        if self.intf is None:
            raise ProbeError('J-Link: no vendor interface found (driver installed?)')
        for ep in self.intf:
            if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                self.ep_in = ep
            else:
                self.ep_out = ep
        usb.util.claim_interface(dev, self.intf.bInterfaceNumber)
        try:                                                    # flush stale responses
            while True:
                self.ep_in.read(4096, 10)
        except Exception:
            pass
        self.caps = struct.unpack('<I', self._cmd([0xE8], 4))[0]                # GET_CAPS
        n = struct.unpack('<H', self._cmd([0x01], 2))[0]                        # GET_VERSION
        self.fw = self._read(n).split(b'\x00')[0].decode('ascii', 'ignore')
        self.name = 'J-Link (%s)' % self.fw if self.fw else 'J-Link'
        try:
            hw = self._cmd([0x07], 8)                                           # GET_HW_STATUS
            self.voltage = struct.unpack('<H', hw[:2])[0] / 1000.0
        except Exception:
            self.voltage = None

    def _write(self, data):
        self.ep_out.write(bytes(data), 1000)

    def _read(self, size):
        result = bytearray()
        rsize = size + 1 if size % self.ep_in.wMaxPacketSize == 0 else size
        while len(result) < size:
            result += self.ep_in.read(max(rsize - len(result), 1), 2000)
        return bytes(result[:size])

    def _cmd(self, data, rsize=0):
        self._write(data)
        return self._read(rsize) if rsize else b''

    def connect(self, speed_khz):
        if self.caps & (1 << 17):                                               # SELECT_IF
            self._cmd([0xC7, 0x01], 4)                                          # select SWD
        self._cmd([0x05] + list(struct.pack('<H', min(speed_khz, 0xFFFE))))     # SET_SPEED
        return self.dp_connect()

    def close(self):
        try:
            usb.util.release_interface(self.dev, self.intf.bInterfaceNumber)
            usb.util.dispose_resources(self.dev)
        except Exception:
            pass

    def set_reset(self, asserted):
        self._cmd([0xDC if asserted else 0xDD])                                 # HW_RESET0/1

    # SWD I/O: list of (direction, value) bits -> list of input bits
    def _swd_io(self, bits):
        n = len(bits)
        nbytes = (n + 7) // 8
        dirb = bytearray(nbytes)
        outb = bytearray(nbytes)
        for i, (d, v) in enumerate(bits):
            if d:
                dirb[i >> 3] |= 1 << (i & 7)
            if v:
                outb[i >> 3] |= 1 << (i & 7)
        resp = self._cmd(bytes([0xCF, 0x00]) + struct.pack('<H', n) + dirb + outb, nbytes + 1)
        if resp[nbytes] != 0:
            raise ProbeError('J-Link SWD I/O error 0x%02x' % resp[nbytes])
        return [(resp[i >> 3] >> (i & 7)) & 1 for i in range(n)]

    def _swj_sequence(self, nbits, data):
        self._swd_io([(1, (data[i >> 3] >> (i & 7)) & 1) for i in range(nbits)])

    @staticmethod
    def _bits(value, n):
        return [(value >> i) & 1 for i in range(n)]

    # Expand ops into SWD transactions, handle posted AP reads via RDBUFF
    def _transfer(self, ops):
        results = [None] * sum(op[1] for op in ops)
        trans = list()                              # (apndp, rnw, addr, value, deliver_index)
        pending = None
        ridx = 0
        for ap, rnw, reg, val in ops:
            if ap and rnw:
                trans.append((1, 1, reg, 0, pending))
                pending = ridx
                ridx += 1
                continue
            if pending is not None:
                trans.append((0, 1, DP_RDBUFF, 0, pending))
                pending = None
            if rnw:
                trans.append((0, 1, reg, 0, ridx))
                ridx += 1
            else:
                trans.append((ap, 0, reg, val, None))
        if pending is not None:
            trans.append((0, 1, DP_RDBUFF, 0, pending))
        i = 0
        retries = 0
        while i < len(trans):
            chunk = trans[i:i + 48]
            bits = list()
            for ap, rnw, reg, val, _ in chunk:
                a2, a3 = (reg >> 2) & 1, (reg >> 3) & 1
                par = (ap + rnw + a2 + a3) & 1
                bits += [(1, 1), (1, ap), (1, rnw), (1, a2), (1, a3), (1, par), (1, 0), (1, 1), (0, 0)]
                bits += [(0, 0)] * 3
                if rnw:
                    bits += [(0, 0)] * 34
                else:
                    bits += [(0, 0)] + [(1, b) for b in self._bits(val, 32)] + [(1, bin(val & 0xFFFFFFFF).count('1') & 1)]
            bits += [(1, 0)] * 8
            inp = self._swd_io(bits)
            pos = 0
            for k, (ap, rnw, reg, val, deliver) in enumerate(chunk):
                ack = inp[pos + 9] | (inp[pos + 10] << 1) | (inp[pos + 11] << 2)
                if ack != 1:
                    i += k
                    if ack == 2 and retries < 1000:
                        retries += 1
                        self._single(0, 0, DP_ABORT, 0x10)
                        if ap and rnw and deliver is not None:
                            results[deliver] = self._single(0, 1, DP_RDBUFF, 0)
                            trans[i] = (ap, rnw, reg, val, None)
                        break
                    if ack == 4:
                        self._single(0, 0, DP_ABORT, ABORT_CLEAR)
                        raise TransferFault('SWD FAULT')
                    if ack == 2:
                        raise TransferFault('SWD WAIT timeout')
                    raise ProbeError('SWD no response from target')
                if rnw:
                    d = sum(inp[pos + 12 + b] << b for b in range(32))
                    if (bin(d).count('1') & 1) != inp[pos + 44]:
                        raise ProbeError('SWD parity error')
                    if deliver is not None:
                        results[deliver] = d
                    pos += 46
                else:
                    pos += 46
            else:
                i += len(chunk)
        return results

    # Single transaction (used for error recovery)
    def _single(self, ap, rnw, reg, val):
        a2, a3 = (reg >> 2) & 1, (reg >> 3) & 1
        par = (ap + rnw + a2 + a3) & 1
        bits = [(1, 1), (1, ap), (1, rnw), (1, a2), (1, a3), (1, par), (1, 0), (1, 1), (0, 0)] + [(0, 0)] * 3
        if rnw:
            bits += [(0, 0)] * 34
        else:
            bits += [(0, 0)] + [(1, b) for b in self._bits(val, 32)] + [(1, bin(val).count('1') & 1)]
        bits += [(1, 0)] * 8
        inp = self._swd_io(bits)
        if (inp[9] | (inp[10] << 1) | (inp[11] << 2)) != 1:
            raise ProbeError('SWD error during recovery')
        return sum(inp[12 + b] << b for b in range(32)) if rnw else None


# ===================================================================================
# ST-Link Probe (V2, V2-1, V3)
# ===================================================================================

STLINK_VID  = 0x0483
STLINK_PIDS = {                     # PID: (name, OUT endpoint, IN endpoint)
    0x3748: ('ST-Link V2',   0x02, 0x81),
    0x374a: ('ST-Link V2-1', 0x01, 0x81),
    0x374b: ('ST-Link V2-1', 0x01, 0x81),
    0x3752: ('ST-Link V2-1', 0x01, 0x81),
    0x374e: ('ST-Link V3',   0x01, 0x81),
    0x374f: ('ST-Link V3',   0x01, 0x81),
    0x3753: ('ST-Link V3',   0x01, 0x81),
    0x3754: ('ST-Link V3',   0x01, 0x81),
    0x3755: ('ST-Link V3',   0x01, 0x81),
    0x3757: ('ST-Link V3',   0x01, 0x81),
}
STLINK_OK = 0x80
STLINK_FAULTS = (0x01, 0x10, 0x11, 0x12, 0x14, 0x15, 0x16, 0x18, 0x19, 0x1a)
STLINK_V2_FREQ = ((4600, 0), (1800, 1), (1200, 2), (950, 3), (650, 5), (480, 7),
                  (400, 9), (360, 10), (240, 15), (150, 25), (125, 31), (100, 40))

class STLink(Probe):
    def __init__(self, dev):
        self.dev = dev
        self.pname, out_ep, in_ep = STLINK_PIDS[dev.idProduct]
        try:
            dev.set_configuration()
        except Exception:
            pass
        usb.util.claim_interface(dev, 0)
        self.ep_out, self.ep_in = out_ep, in_ep
        try:                                                    # flush stale responses
            while True:
                dev.read(self.ep_in, 64, 10)
        except Exception:
            pass
        self._idle()
        ver = struct.unpack('>H', self._cmd([0xF1], 6)[:2])[0]                  # GET_VERSION
        self.hw = (ver >> 12) & 0xF
        self.jtag = (ver >> 6) & 0x3F
        if self.hw >= 3:
            r = self._cmd([0xFB], 12)                                           # GET_VERSION_EXT
            self.jtag = r[2]
            self.version = 'V%dJ%dM%d' % (self.hw, self.jtag, r[3])
        else:
            self.version = 'V%dJ%dM%d' % (self.hw, self.jtag, ver & 0x3F)
        if self.hw < 3 and self.jtag < 24:
            raise ProbeError('ST-Link firmware %s is too old, please update' % self.version)
        self.name = '%s (firmware %s)' % (self.pname, self.version)
        try:
            a0, a1 = struct.unpack('<II', self._cmd([0xF7], 8))                 # GET_TARGET_VOLTAGE
            self.voltage = 2 * a1 * 1.2 / a0 if a0 else None
        except Exception:
            self.voltage = None
        self.maxrw = 1024

    def _version_ok(self, v2, v3):
        return self.jtag >= (v3 if self.hw >= 3 else v2)

    def _cmd(self, cmd, rsize=0, data=None):
        cmd = bytes(cmd) + b'\x00' * (16 - len(cmd))
        self.dev.write(self.ep_out, cmd, 1000)
        if data:
            self.dev.write(self.ep_out, bytes(data), 1000)
        if rsize:
            return bytes(self.dev.read(self.ep_in, rsize, 2000))
        return b''

    def _status(self, resp):
        if resp[0] != STLINK_OK:
            if resp[0] in STLINK_FAULTS:
                raise TransferFault('ST-Link transfer error 0x%02x' % resp[0])
            raise ProbeError('ST-Link error 0x%02x' % resp[0])

    def _idle(self):
        mode = self._cmd([0xF5], 2)[0]                                          # GET_CURRENT_MODE
        if mode == 0x00:
            self._cmd([0xF3, 0x07])                                             # DFU exit
        elif mode == 0x02:
            self._cmd([0xF2, 0x21])                                             # debug exit
        elif mode == 0x03:
            self._cmd([0xF4, 0x01])                                             # SWIM exit

    def connect(self, speed_khz):
        self._idle()
        if self.hw >= 3:
            self._status(self._cmd([0xF2, 0x61, 0x00, 0x00] + list(struct.pack('<I', speed_khz)), 8))
        else:
            div = STLINK_V2_FREQ[-1][1]
            for f, d in STLINK_V2_FREQ:
                if speed_khz >= f:
                    div = d
                    break
            self._status(self._cmd([0xF2, 0x43, div], 2))
        return self.reconnect()

    def reconnect(self):
        self._idle()
        self._status(self._cmd([0xF2, 0x30, 0xA3, 0x00], 2))                     # enter SWD
        if self._version_ok(28, 2):
            self._status(self._cmd([0xF2, 0x4B, 0x00, 0x00], 2))                 # init AP 0
        return self.read_dp(DP_DPIDR)

    def close(self):
        try:
            self._idle()
        except Exception:
            pass
        try:
            usb.util.release_interface(self.dev, 0)
            usb.util.dispose_resources(self.dev)
        except Exception:
            pass

    def set_reset(self, asserted):
        self._status(self._cmd([0xF2, 0x3C, 0x00 if asserted else 0x01], 2))

    def read_dp(self, reg):
        r = self._cmd([0xF2, 0x45] + list(struct.pack('<HH', 0xFFFF, reg)), 8)
        self._status(r)
        return struct.unpack('<I', r[4:8])[0]

    def read_ap(self, ap, reg):
        r = self._cmd([0xF2, 0x45] + list(struct.pack('<HH', ap, reg)), 8)
        self._status(r)
        return struct.unpack('<I', r[4:8])[0]

    def _rwstatus(self):
        self._status(self._cmd([0xF2, 0x3E], 12))                               # GETLASTRWSTATUS2

    def read_mem(self, addr, size):
        result = bytearray()
        for a, n in self._chunks(addr, size, self.maxrw):
            result += self._cmd([0xF2, 0x07] + list(struct.pack('<IH', a, n)), n)
            self._rwstatus()
        return bytes(result)

    def write_mem(self, addr, data):
        pos = 0
        for a, n in self._chunks(addr, len(data), self.maxrw):
            self._cmd([0xF2, 0x08] + list(struct.pack('<IH', a, n)), data=data[pos:pos + n])
            self._rwstatus()
            pos += n

    def read16(self, addr):
        if self._version_ok(26, 1):
            r = self._cmd([0xF2, 0x47] + list(struct.pack('<IH', addr, 2)), 2)
            self._rwstatus()
            return struct.unpack('<H', r)[0]
        return self.read8(addr) | (self.read8(addr + 1) << 8)

    def write16(self, addr, value):
        if self._version_ok(26, 1):
            self._cmd([0xF2, 0x48] + list(struct.pack('<IH', addr, 2)), data=struct.pack('<H', value & 0xFFFF))
            self._rwstatus()
        else:
            self.write8(addr, value & 0xFF)
            self.write8(addr + 1, (value >> 8) & 0xFF)

    def read8(self, addr):
        r = self._cmd([0xF2, 0x0C] + list(struct.pack('<IH', addr, 1)), 2)
        self._rwstatus()
        return r[0]

    def write8(self, addr, value):
        self._cmd([0xF2, 0x0D] + list(struct.pack('<IH', addr, 1)), data=bytes([value & 0xFF]))
        self._rwstatus()


# ===================================================================================
# Target Class (Cortex-M core control, chip detection, flash programming)
# ===================================================================================

DHCSR  = 0xE000EDF0
DCRSR  = 0xE000EDF4
DCRDR  = 0xE000EDF8
DEMCR  = 0xE000EDFC
AIRCR  = 0xE000ED0C
CPUID  = 0xE000ED00
DBGKEY = 0xA05F0000
C_DEBUGEN  = 1 << 0
C_HALT     = 1 << 1
C_MASKINTS = 1 << 3
S_REGRDY   = 1 << 16
S_HALT     = 1 << 17

CPU_NAMES = {0xC20: 'Cortex-M0', 0xC60: 'Cortex-M0+', 0xC23: 'Cortex-M3', 0xC24: 'Cortex-M4',
             0xC27: 'Cortex-M7', 0xD21: 'Cortex-M33', 0xD20: 'Cortex-M23'}

class Chip:
    def __init__(self, name, driver, flash_base, flash_size, ram_base=0x20000000, ram_size=0x1000,
                 regions=None, bootpin=None, nrst=False, lock=True):
        self.name        = name
        self.driver      = driver
        self.flash_base  = flash_base
        self.flash_size  = flash_size
        self.ram_base    = ram_base
        self.ram_size    = ram_size
        self.regions     = regions or [(flash_base, flash_size, 0)]
        self.has_bootpin = bootpin          # None: not available, 'fixed': always usable, 'option'
        self.has_nrst    = nrst
        self.has_lock    = lock


class Target:
    def __init__(self, probe, speed=1000):
        self.probe  = probe
        self.speed  = speed
        self.chip   = None
        self.locked = False
        self.halted = False

    # ------------------------------------------------------------------------------
    # Connection and Core Control
    # ------------------------------------------------------------------------------

    def connect(self):
        try:
            self.probe.connect(self.speed)
            self.halt()
        except Exception:
            self._connect_under_reset()                 # e.g. SWD pins disabled or low-power mode
        self.detect()
        if self.chip.driver is not None and not self.locked:
            self.reset_halt()

    def _connect_under_reset(self):
        self.probe.set_reset(True)
        time.sleep(0.05)
        try:
            self.probe.reconnect()
            try:
                self.write32(DEMCR, 1)
                self.write32(DHCSR, DBGKEY | C_DEBUGEN | C_HALT)
            except TransferFault:
                pass
        finally:
            self.probe.set_reset(False)
        time.sleep(0.05)
        try:
            self.halt()
        except Exception:
            self.halted = False         # possibly locked (e.g. SAMD security bit)

    def read32(self, addr):
        return self.probe.read32(addr)

    def write32(self, addr, value):
        self.probe.write32(addr, value)

    def read_mem(self, addr, size):
        return self.probe.read_mem(addr, size)

    def write_mem(self, addr, data):
        self.probe.write_mem(addr, data)

    def try_read32(self, addr):
        try:
            return self.read32(addr)
        except (TransferFault, ProbeError):
            if hasattr(self.probe, 'clear_errors'):
                self.probe.clear_errors()
            return None

    def wait(self, addr, mask, value=0, timeout=10.0, kick=None):
        start = time.time()
        while True:
            v = self.read32(addr)
            if (v & mask) == value:
                return v
            if kick:
                kick()
            if time.time() - start > timeout:
                raise Exception('Timeout waiting for target (0x%08x = 0x%08x)' % (addr, v))

    def halt(self):
        self.write32(DHCSR, DBGKEY | C_DEBUGEN | C_HALT)
        self.wait(DHCSR, S_HALT, S_HALT, 0.5)
        self.halted = True

    def reset_halt(self):
        self.write32(DEMCR, self.read32(DEMCR) | 1)                 # VC_CORERESET
        try:
            self.write32(AIRCR, 0x05FA0004)                          # SYSRESETREQ
        except (ProbeError, TransferFault):
            pass
        time.sleep(0.05)
        for _ in range(20):
            try:
                if self.read32(DHCSR) & S_HALT:
                    break
            except (ProbeError, TransferFault):
                self.reconnect()
            time.sleep(0.01)
        else:
            raise Exception('Target did not halt after reset')
        self.write32(DEMCR, self.read32(DEMCR) & ~1)
        self.halted = True
        self.freeze_watchdog()

    def reconnect(self):
        last = None
        for _ in range(20):
            try:
                self.probe.reconnect()
                self.halt()
                return
            except (ProbeError, TransferFault) as ex:
                last = ex
                time.sleep(0.1)
        raise Exception('Lost connection to target (%s)' % last)

    # Reconnect after the chip was reset by an option byte reload
    def reconnect_after_reset(self):
        time.sleep(0.2)
        try:
            self.reconnect()
        except Exception:
            self._connect_under_reset()
        self.locked = self.chip.driver.is_locked()
        if not self.locked:
            self.reset_halt()

    def write_reg(self, reg, value):
        self.write32(DCRDR, value)
        self.write32(DCRSR, reg | (1 << 16))
        self.wait(DHCSR, S_REGRDY, S_REGRDY, 0.5)

    def read_reg(self, reg):
        self.write32(DCRSR, reg)
        self.wait(DHCSR, S_REGRDY, S_REGRDY, 0.5)
        return self.read32(DCRDR)

    def freeze_watchdog(self):
        fz = getattr(self.chip.driver, 'iwdg_freeze', None) if self.chip and self.chip.driver else None
        if fz:
            v = self.try_read32(fz[0])
            if v is not None:
                try:
                    self.write32(fz[0], v | fz[1])
                except (ProbeError, TransferFault):
                    pass

    def exit(self, run=True):
        try:
            if run and self.halted:
                self.write32(DEMCR, 0)
                self.write32(DHCSR, DBGKEY | C_DEBUGEN)
                try:
                    self.write32(AIRCR, 0x05FA0004)
                except (ProbeError, TransferFault):
                    pass
                time.sleep(0.01)
                try:
                    self.write32(DHCSR, DBGKEY)
                except (ProbeError, TransferFault):
                    pass
        finally:
            try:
                self.probe.set_reset(False)
            except Exception:
                pass
            self.probe.close()

    # ------------------------------------------------------------------------------
    # Chip Detection
    # ------------------------------------------------------------------------------

    def detect(self):
        if not self.halted:
            # Core not accessible: check for a locked SAMD (DSU external access)
            did = self.try_read32(SAMD_DSU + 0x100 + 0x18)
            chip = samd_chip(self, did) if did else None
            if chip is None:
                raise Exception('Cannot access target core')
            self.chip = chip
            self.locked = True
            return
        cpuid = self.read32(CPUID)
        part = (cpuid >> 4) & 0xFFF
        self.cpu = CPU_NAMES.get(part, 'CPUID 0x%08x' % cpuid)
        idcodes = list()
        for addr in STM32_IDCODE_ADDR.get(part, []):
            idcode = self.try_read32(addr)
            if idcode is None:
                continue
            idcodes.append(idcode)
            dev = STM32_DEVICES.get(idcode & 0xFFF)
            if dev is not None and dev[0] == addr:
                self.chip = stm32_chip(self, part, idcode & 0xFFF, dev)
                break
        else:
            chip = None
            if part in (0xC20, 0xC60):
                chip = py32_chip(self, self.try_read32(0x40015800))
            if chip is None and part in (0xC60, 0xC24):
                chip = samd_chip(self, self.try_read32(SAMD_DSU + 0x18))
            if chip is None:
                raise Exception('Unsupported chip (%s, IDCODE %s)' % (self.cpu,
                                ', '.join('0x%08x' % i for i in idcodes) or 'n/a'))
            self.chip = chip
        self.locked = self.chip.driver.is_locked()

    # ------------------------------------------------------------------------------
    # Flash Loader
    # ------------------------------------------------------------------------------

    def _layout(self):
        base = self.chip.ram_base
        bufsize = min(self.chip.ram_size - 0x100, 0x4000)
        return base, base + 0xA0, base + 0x100, bufsize

    def load_loader(self):
        code = struct.pack('<%dH' % len(LOADER_CODE), *LOADER_CODE)
        self.write_mem(self.chip.ram_base, code + b'\x00' * ((-len(code)) % 4))

    # Run loader for count units of data (already in RAM buffer at src)
    def run_loader(self, p, src, dst, count, timeout=None):
        code, params, _, _ = self._layout()
        unit = p['unit']
        block = struct.pack('<17I', src, dst, count, unit, p.get('stride', unit),
                            p['sr'], p['busy'], p.get('xor', 0), p.get('err', 0),
                            p.get('cr', 0), p.get('trig', 0), p.get('pos', 0xFFFFFFFF),
                            p.get('flags', 0), p.get('set', 0), p.get('kick', 0),
                            p.get('kickval', 0), 0)
        self.write_mem(params, block)
        self.write_reg(0, params)
        self.write_reg(13, params)
        self.write_reg(14, code | 1)
        self.write_reg(15, code)
        self.write_reg(16, 0x01000000)
        self.write32(DHCSR, DBGKEY | C_DEBUGEN | C_HALT | C_MASKINTS)
        self.write32(DHCSR, DBGKEY | C_DEBUGEN | C_MASKINTS)
        if timeout is None:
            timeout = 2.0 + 0.05 * count
        start = time.time()
        while not (self.read32(DHCSR) & S_HALT):
            if time.time() - start > timeout:
                self.halt()
                raise Exception('Flash loader timeout at 0x%08x' % self.read_reg(2))
        result = self.read_reg(0)
        if result:
            fail = self.read32(params + 0x40)
            raise Exception('Flash operation failed at 0x%08x (status 0x%08x)' % (fail, result))

    # Write data to target using the loader (data length must be a multiple of unit)
    def loader_write(self, p, dst, data, stride=None):
        self.load_loader()
        _, _, buf, bufsize = self._layout()
        unit = p['unit']
        step = stride or unit
        chunk = max(unit, bufsize // unit * unit)
        pos = 0
        while pos < len(data):
            block = data[pos:pos + chunk]
            self.write_mem(buf, block + b'\xff' * ((-len(block)) % 4))
            count = len(block) // unit
            self.run_loader(p, buf, dst, count)
            dst += count * step
            pos += len(block)

    # ------------------------------------------------------------------------------
    # High-Level Functions
    # ------------------------------------------------------------------------------

    def check_image(self, data):
        end = self.chip.regions[-1][0] + self.chip.regions[-1][1]
        if len(data) > end - self.chip.flash_base:
            raise Exception('Not enough memory (file: %d bytes, flash: %d bytes)' % (len(data), self.chip.flash_size))
        pos = 0
        for addr, size, _ in self.chip.regions:
            off = addr - self.chip.flash_base
            if off > pos and data[pos:off].strip(b'\xff'):
                raise Exception('BIN file contains data outside of flash (offset 0x%x)' % pos)
            pos = off + size
        self.chip.driver.check_image(data)

    def unlock(self):
        if not self.locked:
            print('Chip is not locked, nothing to do.')
            return False
        self.chip.driver.unlock()
        self.reconnect_after_reset()
        if self.locked:
            raise Exception('Unlocking failed')
        self.detect()                                   # update chip information
        self.reset_halt()
        return True

    def lock(self):
        self.chip.driver.lock()
        self.reconnect_after_reset()

    def erase(self):
        self.chip.driver.erase()

    def flash_data(self, data):
        drv = self.chip.driver
        unit = drv.unit
        data = bytes(data) + b'\xff' * ((-len(data)) % unit)
        for addr, size, bank in self.chip.regions:
            off = addr - self.chip.flash_base
            seg = data[off:off + size]
            if not seg:
                continue
            drv.prepare(bank)
            try:
                self.loader_write(drv.loader_params(bank), addr, seg)
            finally:
                drv.finish(bank)

    def verify_data(self, data):
        for addr, size, bank in self.chip.regions:
            off = addr - self.chip.flash_base
            seg = data[off:off + size]
            if not seg:
                continue
            readback = self.read_mem(addr, len(seg) + ((-len(seg)) % 4))[:len(seg)]
            if readback != seg:
                for i in range(len(seg)):
                    if readback[i] != seg[i]:
                        raise Exception('Verification failed at 0x%08x' % (addr + i))

    def set_bootpin(self):
        if self.chip.has_bootpin == 'fixed':
            print('BOOT0 pin is always usable on this chip, nothing to do.')
            return
        self.chip.driver.bootpin()
        self.reconnect_after_reset()

    def set_nrst(self, gpio):
        self.chip.driver.nrst(gpio)
        self.reconnect_after_reset()


# ===================================================================================
# Flash Driver Base Class
# ===================================================================================

class FlashDriver:
    unit = 4
    iwdg_freeze = None

    def __init__(self, target):
        self.t = target

    def is_locked(self):
        return False

    def check_image(self, data):
        pass

    def prepare(self, bank):
        pass

    def finish(self, bank):
        pass

    def unlock(self):
        raise Exception('Unlocking is not supported on this chip')

    def lock(self):
        raise Exception('Locking is not supported on this chip')

    def bootpin(self):
        raise Exception('BOOT0 pin configuration is not supported on this chip')

    def nrst(self, gpio):
        raise Exception('NRST pin configuration is not supported on this chip')

    def r(self, reg):
        return self.t.read32(self.base + reg)

    def w(self, reg, value):
        self.t.write32(self.base + reg, value)

    def _unlock_keys(self, cr, lockbit, keyr, keys=(0x45670123, 0xCDEF89AB)):
        if self.r(cr) & lockbit:
            self.w(keyr, keys[0])
            self.w(keyr, keys[1])
            if self.r(cr) & lockbit:
                raise Exception('Unlocking flash controller failed')


# ===================================================================================
# STM32F0/F1/F3 Flash Driver
# ===================================================================================

class STM32F1Flash(FlashDriver):
    unit = 2

    def __init__(self, target, part, devid, size):
        super().__init__(target)
        self.base = 0x40022000
        self.f1 = (part == 0xC23)                                   # F1: Cortex-M3
        self.default_rdp = 0xA5 if self.f1 else 0xAA
        self.bootsel = devid in (0x445, 0x442)                      # F04x, F09x
        self.iwdg_freeze = (0xE0042004, 1 << 8) if self.f1 else \
                           ((0x40015808, 1 << 12) if part == 0xC20 else (0xE0042008, 1 << 12))

    def _bank(self, bank):
        return self.base + 0x40 * bank

    def _wait(self, bank, timeout=10.0):
        sr = self.t.wait(self._bank(bank) + 0x0C, 0x01, 0, timeout)
        if sr & 0x14:
            self.t.write32(self._bank(bank) + 0x0C, 0x34)
            raise Exception('Flash error (SR 0x%08x)' % sr)

    def _unlock(self, bank):
        b = self._bank(bank)
        if self.t.read32(b + 0x10) & 0x80:
            self.t.write32(b + 0x04, 0x45670123)
            self.t.write32(b + 0x04, 0xCDEF89AB)

    def banks(self):
        return sorted(set(r[2] for r in self.t.chip.regions))

    def is_locked(self):
        obr = self.r(0x1C)
        return bool(obr & 0x02) if self.f1 else bool((obr >> 1) & 0x03)

    def erase(self):
        for bank in self.banks():
            b = self._bank(bank)
            self._unlock(bank)
            self._wait(bank)
            self.t.write32(b + 0x0C, 0x34)
            self.t.write32(b + 0x10, 0x04)                          # MER
            self.t.write32(b + 0x10, 0x44)                          # MER | STRT
            self._wait(bank, 60.0)
            self.t.write32(b + 0x10, 0x80)                          # LOCK

    def prepare(self, bank):
        b = self._bank(bank)
        self._unlock(bank)
        self._wait(bank)
        self.t.write32(b + 0x0C, 0x34)
        self.t.write32(b + 0x10, 0x01)                              # PG

    def loader_params(self, bank):
        return {'unit': 2, 'flags': 1, 'sr': self._bank(bank) + 0x0C, 'busy': 0x01, 'err': 0x14}

    def finish(self, bank):
        self.t.write32(self._bank(bank) + 0x10, 0x80)

    def _options(self, rdp=None, user_set=0):
        obr = self.r(0x1C)
        wrp = self.r(0x20)
        if self.f1:
            user, data = (obr >> 2) & 0xFF, (obr >> 10) & 0xFFFF
        else:
            user, data = (obr >> 8) & 0xFF, (obr >> 16) & 0xFFFF
        if rdp is None:
            rdp = 0x00 if self.is_locked() else self.default_rdp
        user |= user_set
        ob = [rdp, user, data & 0xFF, data >> 8, wrp & 0xFF, (wrp >> 8) & 0xFF, (wrp >> 16) & 0xFF, wrp >> 24]
        self._unlock(0)
        self.w(0x08, 0x45670123)                                    # OPTKEYR
        self.w(0x08, 0xCDEF89AB)
        self.w(0x10, 0x220)                                         # OPTER | OPTWRE
        self.w(0x10, 0x260)                                         # OPTER | OPTWRE | STRT
        self._wait(0, 60.0)
        self.w(0x10, 0x210)                                         # OPTPG | OPTWRE
        self.t.loader_write(self.loader_params(0), 0x1FFFF800, struct.pack('<8H', *ob))
        if self.f1:
            self.w(0x10, 0x80)
            try:
                self.t.write32(AIRCR, 0x05FA0004)                   # reload option bytes by reset
            except (ProbeError, TransferFault):
                pass
        else:
            try:
                self.w(0x10, 0x2200)                                # OBL_LAUNCH | OPTWRE
            except (ProbeError, TransferFault):
                pass

    def unlock(self):
        self._options(rdp=self.default_rdp)

    def lock(self):
        self._options(rdp=0x00)

    def bootpin(self):
        if self.f1:
            raise Exception('BOOT0 pin configuration is not supported on this chip')
        self._options(user_set=0x90 if self.bootsel else 0x10)      # (BOOT_SEL) | nBOOT1


# ===================================================================================
# STM32F2/F4/F7 Flash Driver
# ===================================================================================

class STM32F4Flash(FlashDriver):
    unit = 2

    def __init__(self, target, part, devid, size):
        super().__init__(target)
        self.base = 0x40023C00
        self.iwdg_freeze = (0xE0042008, 1 << 12)
        optcr = target.read32(self.base + 0x14)
        if devid in (0x419, 0x434):
            self.dual = size >= 2048 * 1024 or (size == 1024 * 1024 and bool(optcr & (1 << 30)))
        elif devid == 0x451:
            self.dual = not (optcr & (1 << 29))
        else:
            self.dual = False

    def _wait(self, timeout=10.0):
        sr = self.t.wait(self.base + 0x0C, 1 << 16, 0, timeout)
        if sr & 0xF2:
            self.w(0x0C, 0xF3)
            raise Exception('Flash error (SR 0x%08x)' % sr)

    def _unlock(self):
        self._unlock_keys(0x10, 1 << 31, 0x04)

    def is_locked(self):
        return ((self.r(0x14) >> 8) & 0xFF) != 0xAA

    def erase(self):
        self._unlock()
        self._wait()
        self.w(0x0C, 0xF3)
        cr = 0x04 | (1 << 15 if self.dual else 0) | (1 << 8)        # MER (| MER1) | PSIZE x16
        self.w(0x10, cr)
        self.w(0x10, cr | (1 << 16))                                # STRT
        self._wait(120.0)
        self.w(0x10, 1 << 31)

    def prepare(self, bank):
        self._unlock()
        self._wait()
        self.w(0x0C, 0xF3)
        self.w(0x10, 0x101)                                         # PG | PSIZE x16

    def loader_params(self, bank):
        return {'unit': 2, 'flags': 1, 'sr': self.base + 0x0C, 'busy': 1 << 16, 'err': 0xF2}

    def finish(self, bank):
        self.w(0x10, 1 << 31)

    def _set_rdp(self, rdp):
        self._unlock()
        if self.r(0x14) & 1:
            self.w(0x08, 0x08192A3B)
            self.w(0x08, 0x4C5D6E7F)
        self._wait()
        optcr = (self.r(0x14) & ~0xFF03) | (rdp << 8)
        self.w(0x14, optcr)
        self.w(0x14, optcr | 0x02)                                  # OPTSTRT
        self._wait(300.0)
        self.w(0x14, optcr | 0x01)                                  # OPTLOCK
        try:
            self.t.write32(AIRCR, 0x05FA0004)
        except (ProbeError, TransferFault):
            pass

    def unlock(self):
        self._set_rdp(0xAA)

    def lock(self):
        self._set_rdp(0xBB)


# ===================================================================================
# STM32L0/L1 Flash Driver
# ===================================================================================

class STM32L0Flash(FlashDriver):
    def __init__(self, target, part, devid, size):
        super().__init__(target)
        self.l1 = (part == 0xC23)
        self.base = 0x40023C00 if self.l1 else 0x40022000
        self.page = 256 if self.l1 else 128
        self.unit = self.page // 2                                  # half page
        self.size = size
        self.iwdg_freeze = (0xE0042008 if self.l1 else 0x40015808, 1 << 12)

    def _unlock(self):
        pecr = self.r(0x04)
        if pecr & 0x01:
            self.w(0x0C, 0x89ABCDEF)
            self.w(0x0C, 0x02030405)
        if self.r(0x04) & 0x02:
            self.w(0x10, 0x8C9DAEBF)
            self.w(0x10, 0x13141516)
        if self.r(0x04) & 0x03:
            raise Exception('Unlocking flash controller failed')

    def _lock(self):
        self.w(0x04, (self.r(0x04) & ~0x608) | 0x01)                # clear ERASE/FPRG/PROG, set PELOCK

    def _wait(self, timeout=10.0):
        sr = self.t.wait(self.base + 0x18, 0x01, 0, timeout)
        if sr & 0x32700:
            self.w(0x18, 0x32F00)
            raise Exception('Flash error (SR 0x%08x)' % sr)

    def is_locked(self):
        return (self.r(0x1C) & 0xFF) != 0xAA

    def erase(self):
        self._unlock()
        self._wait()
        self.w(0x18, 0x32F00)
        self.w(0x04, (self.r(0x04) & ~0x400) | 0x208)               # ERASE | PROG
        p = {'unit': 4, 'stride': self.page, 'sr': self.base + 0x18, 'busy': 0x01, 'err': 0x32700}
        try:
            self.t.loader_write(p, 0x08000000, bytes(4 * (self.size // self.page)), stride=self.page)
        finally:
            self._lock()

    def prepare(self, bank):
        self._unlock()
        self._wait()
        self.w(0x18, 0x32F00)
        self.w(0x04, (self.r(0x04) & ~0x200) | 0x408)               # FPRG | PROG

    def loader_params(self, bank):
        return {'unit': self.unit, 'sr': self.base + 0x18, 'busy': 0x01, 'err': 0x32700}

    def finish(self, bank):
        self._lock()

    def _set_rdp(self, rdp):
        self._unlock()
        self.w(0x14, 0xFBEAD9C8)                                    # OPTKEYR
        self.w(0x14, 0x24252627)
        self._wait()
        lo = (self.r(0x1C) & 0x100) | rdp
        self.t.write32(0x1FF80000, lo | ((~lo & 0xFFFF) << 16))
        self._wait(120.0)
        try:
            self.w(0x04, self.r(0x04) | (1 << 18))                  # OBL_LAUNCH
        except (ProbeError, TransferFault):
            pass

    def unlock(self):
        self._set_rdp(0xAA)

    def lock(self):
        self._set_rdp(0xBB)


# ===================================================================================
# STM32 C0/G0/G4/L4/L4+/L5/U0/U3/U5/WB/WBA/WL Flash Driver
# ===================================================================================

class STM32L4Flash(FlashDriver):
    def __init__(self, target, part, devid, size, opts):
        super().__init__(target)
        self.base = opts.get('base', 0x40022000)
        self.l5 = opts.get('l5', False)
        self.dual = opts.get('dual', False)
        self.unit = 16 if opts.get('quad') else 8
        self.boot = opts.get('boot')
        self.nrststyle = opts.get('nrst')
        self.busy = (1 << 16) | (1 << 18) | ((1 << 17) if devid == 0x467 else 0)
        self.KEYR, self.OPTKEYR, self.SR, self.CR, self.OPTR = \
            (0x08, 0x10, 0x20, 0x28, 0x40) if self.l5 else (0x08, 0x0C, 0x10, 0x14, 0x20)
        if opts.get('tz') and (self.r(self.OPTR) & (1 << 31)):
            raise Exception('TrustZone is enabled on this chip, not supported')
        fz = opts.get('fz')
        self.iwdg_freeze = (fz, 1 << 12) if fz else None

    def _wait(self, timeout=10.0):
        sr = self.t.wait(self.base + self.SR, self.busy, 0, timeout)
        if sr & 0x3FA:
            self.w(self.SR, 0x3FB)
            raise Exception('Flash error (SR 0x%08x)' % sr)

    def _unlock(self):
        self._unlock_keys(self.CR, 1 << 31, self.KEYR)

    def is_locked(self):
        return (self.r(self.OPTR) & 0xFF) != 0xAA

    def erase(self):
        self._unlock()
        self._wait()
        self.w(self.SR, 0x3FB)
        cr = 0x04 | ((1 << 15) if self.dual else 0)                 # MER1 (| MER2)
        self.w(self.CR, cr)
        self.w(self.CR, cr | (1 << 16))                             # STRT
        self._wait(120.0)
        self.w(self.CR, 1 << 31)

    def prepare(self, bank):
        self._unlock()
        self._wait()
        self.w(self.SR, 0x3FB)
        self.w(self.CR, 0x01)                                       # PG

    def loader_params(self, bank):
        return {'unit': self.unit, 'sr': self.base + self.SR, 'busy': self.busy, 'err': 0x3FA}

    def finish(self, bank):
        self.w(self.CR, 1 << 31)

    def _set_optr(self, func):
        self._unlock()
        if self.r(self.CR) & (1 << 30):
            self.w(self.OPTKEYR, 0x08192A3B)
            self.w(self.OPTKEYR, 0x4C5D6E7F)
            if self.r(self.CR) & (1 << 30):
                raise Exception('Unlocking option bytes failed')
        self._wait()
        self.w(self.SR, 0x3FB | (1 << 15))
        self.w(self.OPTR, func(self.r(self.OPTR)))
        self.w(self.CR, self.r(self.CR) | (1 << 17))                # OPTSTRT
        self._wait(300.0)
        try:
            self.w(self.CR, self.r(self.CR) | (1 << 27))            # OBL_LAUNCH
        except (ProbeError, TransferFault):
            pass

    def unlock(self):
        self._set_optr(lambda v: (v & ~0xFF) | 0xAA)

    def lock(self):
        self._set_optr(lambda v: (v & ~0xFF) | 0xBB)

    def bootpin(self):
        if self.boot == 'sel':                                      # C0/G0/U0: nBOOT_SEL=0, nBOOT1=1
            self._set_optr(lambda v: (v & ~(1 << 24)) | (1 << 25))
        elif self.boot == 'sw':                                     # G4/L4/WB/WL: nSWBOOT0=1, nBOOT1=1
            self._set_optr(lambda v: v | (1 << 26) | (1 << 23))
        elif self.boot == 'sw5':                                    # L5/U5: nSWBOOT0=1
            self._set_optr(lambda v: v | (1 << 26))
        else:
            super().bootpin()

    def nrst(self, gpio):
        mode = 0b10 if gpio else 0b11
        if self.nrststyle == 'g0':
            self._set_optr(lambda v: (v & ~(3 << 27)) | (mode << 27))
        elif self.nrststyle == 'g4':
            self._set_optr(lambda v: (v & ~(3 << 28)) | (mode << 28))
        else:
            super().nrst(gpio)


# ===================================================================================
# STM32H7 Flash Driver
# ===================================================================================

class STM32H7Flash(FlashDriver):
    def __init__(self, target, part, devid, size):
        super().__init__(target)
        self.base = 0x52002000
        self.h7a = (devid == 0x480)
        self.unit = 16 if self.h7a else 32
        self.iwdg_freeze = (0x5C001054, 1 << 18)

    def _b(self, bank):
        return self.base + 0x100 * bank

    def _wait(self, bank, timeout=10.0):
        sr = self.t.wait(self._b(bank) + 0x10, 0x05, 0, timeout)
        if sr & 0x07EE0000:
            self.t.write32(self._b(bank) + 0x14, 0x07EE0000)
            raise Exception('Flash error (SR 0x%08x)' % sr)

    def _unlock(self, bank):
        b = self._b(bank)
        if self.t.read32(b + 0x0C) & 1:
            self.t.write32(b + 0x04, 0x45670123)
            self.t.write32(b + 0x04, 0xCDEF89AB)
            if self.t.read32(b + 0x0C) & 1:
                raise Exception('Unlocking flash controller failed')

    def is_locked(self):
        return ((self.r(0x1C) >> 8) & 0xFF) != 0xAA

    def erase(self):
        for bank in sorted(set(r[2] for r in self.t.chip.regions)):
            b = self._b(bank)
            self._unlock(bank)
            self._wait(bank)
            self.t.write32(b + 0x14, 0x07EF0000)
            if self.h7a:
                cr, start = 0x08, 1 << 5                            # BER, START
            else:
                cr, start = 0x08 | (3 << 4), 1 << 7                 # BER | PSIZE x64, START
            self.t.write32(b + 0x0C, cr)
            self.t.write32(b + 0x0C, cr | start)
            self._wait(bank, 120.0)
            self.t.write32(b + 0x0C, 0x01)

    def prepare(self, bank):
        b = self._b(bank)
        self._unlock(bank)
        self._wait(bank)
        self.t.write32(b + 0x14, 0x07EF0000)
        self.t.write32(b + 0x0C, 0x02)                              # PG

    def loader_params(self, bank):
        return {'unit': self.unit, 'sr': self._b(bank) + 0x10, 'busy': 0x05, 'err': 0x07EE0000}

    def finish(self, bank):
        self.t.write32(self._b(bank) + 0x0C, 0x01)

    def _set_rdp(self, rdp):
        if self.r(0x18) & 1:
            self.w(0x08, 0x08192A3B)
            self.w(0x08, 0x4C5D6E7F)
            if self.r(0x18) & 1:
                raise Exception('Unlocking option bytes failed')
        self.w(0x24, 1 << 30)                                       # clear OPTCHANGEERR
        self.w(0x20, (self.r(0x20) & ~0xFF00) | (rdp << 8))
        self.w(0x18, self.r(0x18) | 0x02)                           # OPTSTART
        cur = self.t.wait(self.base + 0x1C, 0x01, 0, 300.0)
        self.w(0x18, self.r(0x18) | 0x01)                           # OPTLOCK
        if cur & (1 << 30):
            raise Exception('Option byte change error')
        try:
            self.t.write32(AIRCR, 0x05FA0004)
        except (ProbeError, TransferFault):
            pass

    def unlock(self):
        self._set_rdp(0xAA)

    def lock(self):
        self._set_rdp(0xBB)


# ===================================================================================
# STM32H5 Flash Driver
# ===================================================================================

class STM32H5Flash(FlashDriver):
    unit = 16
    iwdg_freeze = (0x44024008, 1 << 12)

    def __init__(self, target, part, devid, size):
        super().__init__(target)
        self.base = 0x40022000

    def _wait(self, timeout=10.0):
        sr = self.t.wait(self.base + 0x20, 0x0B, 0, timeout)
        if sr & 0x00FC0000:
            self.w(0x30, 0x00FF0000)
            raise Exception('Flash error (SR 0x%08x)' % sr)

    def _unlock(self):
        self._unlock_keys(0x28, 0x01, 0x04)

    def erase(self):
        self._unlock()
        self._wait()
        self.w(0x30, 0x00FF0000)
        self.w(0x28, 1 << 15)                                       # MER
        self.w(0x28, (1 << 15) | (1 << 5))                          # MER | START
        self._wait(120.0)
        self.w(0x28, 0x01)

    def prepare(self, bank):
        self._unlock()
        self._wait()
        self.w(0x30, 0x00FF0000)
        self.w(0x28, 0x02)                                          # PG

    def loader_params(self, bank):
        return {'unit': 16, 'sr': self.base + 0x20, 'busy': 0x0B, 'err': 0x00FC0000}

    def finish(self, bank):
        self.w(0x28, 0x01)


# ===================================================================================
# PUYA PY32 Flash Driver
# ===================================================================================

PY32_VARIANTS = {
    #          timing params, stride,  word step, IWDG_SW, NRST_MODE, nBOOT1, RDP
    'f0xx':  (0x1FFF0F1C, 0x14, 4, 12, 14, 15,   True),
    'f07x':  (0x1FFF3238, 0x28, 8, 11, 13, 14,   True),
    'f002b': (0x1FFF011C, 0x00, 4, 12, 14, None, False),
}

class PY32Flash(FlashDriver):
    unit = 128

    def __init__(self, target, variant):
        super().__init__(target)
        self.base = 0x40022000
        self.variant = variant
        self.tbase, self.tstride, self.tstep, self.iwdg_bit, self.nrst_bit, self.nboot1_bit, self.rdp = \
            PY32_VARIANTS[variant]
        self.iwdg_freeze = (0x40015808, 1 << 12)

    def _kick(self):
        self.t.write32(0x40003000, 0xAAAA)                          # reload IWDG

    def _wait(self, timeout=10.0):
        sr = self.t.wait(self.base + 0x10, 1 << 16, 0, timeout, kick=self._kick)
        if sr & 0x10:
            self.w(0x10, 0x11)
            raise Exception('Flash write protection error')

    def _setup(self):
        self._unlock_keys(0x14, 1 << 31, 0x08)
        # Flash timing according to current HSI frequency (from factory configuration)
        hsi = (self.t.read32(0x40021004) >> 13) & 0x07
        if self.variant == 'f002b':
            addr = 0x1FFF0130 if hsi == 5 else 0x1FFF011C
            e = [self.t.read32(addr + 4 * i) for i in range(5)]
            ts = ((0x100, e[0] & 0x1FF), (0x104, (e[0] >> 18) & 0x3FF), (0x110, (e[0] >> 9) & 0x1FF),
                  (0x108, e[1] & 0x1FF), (0x10C, (e[1] >> 16) & 0xFFF), (0x114, e[2] & 0x3FFFF),
                  (0x118, e[3] & 0x3FFFF), (0x11C, e[4] & 0xFFFF), (0x120, (e[4] >> 16) & 0x3FFF))
        else:
            if hsi > 4:
                hsi = 0
            addr = self.tbase + hsi * self.tstride
            e = [self.t.read32(addr + self.tstep * i) for i in range(5)]
            ts = ((0x100, e[0] & 0xFF), (0x104, (e[0] >> 16) & 0x1FF), (0x110, (e[0] >> 8) & 0xFF),
                  (0x108, e[1] & 0xFF), (0x10C, (e[1] >> 16) & 0x7FF), (0x114, e[2] & 0x1FFFF),
                  (0x118, e[3] & 0x1FFFF), (0x11C, e[4] & 0xFFFF), (0x120, (e[4] >> 16) & 0x3FFF))
        for reg, value in ts:
            self.w(reg, value)
        # Configure hardware watchdog for long timeout
        if not (self.r(0x20) >> self.iwdg_bit) & 1:
            self.t.write32(0x40003000, 0x5555)
            self.t.write32(0x40003004, 0x06)
            self.t.write32(0x40003008, 0xFFF)
            self._kick()
        self._wait()
        self.w(0x10, 0x11)                                          # clear EOP, WRPERR

    def is_locked(self):
        return self.rdp and (self.r(0x20) & 0xFF) != 0xAA

    def erase(self):
        self._setup()
        self.w(0x14, (1 << 2) | (1 << 24))                          # MER | EOPIE
        self.t.write32(0x08000000, 0xFFFFFFFF)
        self._wait(60.0)
        self.w(0x14, 1 << 31)

    def prepare(self, bank):
        self._setup()
        self.w(0x14, 0)

    def loader_params(self, bank):
        return {'unit': 128, 'sr': self.base + 0x10, 'busy': 1 << 16, 'err': 0x10,
                'cr': self.base + 0x14, 'trig': 1 << 19, 'pos': 124, 'flags': 2,
                'set': (1 << 0) | (1 << 24), 'kick': 0x40003000, 'kickval': 0xAAAA}

    def finish(self, bank):
        self.w(0x14, 1 << 31)

    def _set_optr(self, func):
        self._setup()
        if self.r(0x14) & (1 << 30):
            self.w(0x0C, 0x08192A3B)
            self.w(0x0C, 0x4C5D6E7F)
        optr, sdkr, wrpr = self.r(0x20), self.r(0x24), self.r(0x2C)
        btcr = self.r(0x28) if self.variant == 'f002b' else None
        self.w(0x20, func(optr) & 0xFFFF)
        self.w(0x24, sdkr & 0xFFFF)
        self.w(0x2C, wrpr & 0xFFFF)
        if btcr is not None:
            self.w(0x28, btcr & 0xFFFF)
        self.w(0x14, self.r(0x14) | (1 << 17) | (1 << 24))          # OPTSTRT | EOPIE
        self.t.write32(0x40022080, 0xFF)
        self._wait(120.0)
        self.w(0x14, self.r(0x14) & ~((1 << 17) | (1 << 24)))
        try:
            self.w(0x14, self.r(0x14) | (1 << 27))                  # OBL_LAUNCH
        except (ProbeError, TransferFault):
            pass

    def unlock(self):
        self._set_optr(lambda v: (v & ~0xFF) | 0xAA)

    def lock(self):
        if not self.rdp:
            super().lock()
        self._set_optr(lambda v: (v & ~0xFF) | 0x55)

    def bootpin(self):
        if self.nboot1_bit is None:
            super().bootpin()
        self._set_optr(lambda v: v | (1 << self.nboot1_bit))

    def nrst(self, gpio):
        self._set_optr(lambda v: (v & ~(1 << self.nrst_bit)) | ((1 if gpio else 0) << self.nrst_bit))


# ===================================================================================
# Microchip/ATMEL SAMD Flash Drivers
# ===================================================================================

SAMD_DSU     = 0x41002000
SAMD_NVMCTRL = 0x41004000

class SAMDFlash(FlashDriver):
    def __init__(self, target, d5x):
        super().__init__(target)
        self.base = SAMD_NVMCTRL
        self.d5x = d5x
        param = self.r(0x08)
        self.unit = 8 << ((param >> 16) & 0x07)                     # page size
        self.size = (param & 0xFFFF) * self.unit

    def is_locked(self):
        status = self.t.try_read32(SAMD_DSU + 0x100)
        if status is None:
            return True
        return bool((status >> 16) & 0x01)                          # STATUSB.PROT

    def _cmd(self, cmd):
        if self.d5x:
            self.t.probe.write16(self.base + 0x10, 0xFFFF)
            self.w(0x04, 0xA500 | cmd)
            self.t.wait(self.base + 0x10, 1 << 16, 1 << 16, 2.0)    # STATUS.READY
            flags = self.t.probe.read16(self.base + 0x10)
            if flags & 0x4E:
                raise Exception('NVM controller error (INTFLAG 0x%04x)' % flags)
        else:
            self.w(0x18, 0x1C)
            self.w(0x14, 0x02)
            self.w(0x00, 0xA500 | cmd)
            flags = self.t.wait(self.base + 0x14, 0x01, 0x01, 2.0)  # INTFLAG.READY
            if flags & 0x02:
                raise Exception('NVM controller error (STATUS 0x%04x)' % (self.r(0x18) & 0xFFFF))

    def _bootprot(self):
        user = self.t.read32(0x00804000)
        if self.d5x:
            return (15 - ((user >> 26) & 0x0F)) * 8192
        v = user & 0x07
        return 0 if v == 7 else 256 << (7 - v)

    def check_image(self, data):
        if self.t.locked:
            return
        bp = self._bootprot()
        if bp and data[:bp].strip(b'\xff'):
            raise Exception('First %d bytes of flash are protected by BOOTPROT fuse (bootloader)' % bp)

    def erase(self):
        try:                                                        # disable DSU write protection
            if self.d5x:
                self.t.write32(0x40000000, (1 << 16) | (1 << 5) | (1 << 1))
            else:
                self.t.write32(0x41000000, 1 << 1)
        except (ProbeError, TransferFault):
            if hasattr(self.t.probe, 'clear_errors'):
                self.t.probe.clear_errors()
        self.t.probe.write8(SAMD_DSU + 0x101, 0x1F)                 # clear STATUSA
        self.t.probe.write8(SAMD_DSU + 0x100, 0x10)                 # CTRL.CE (chip erase)
        start = time.time()
        while not (self.t.probe.read8(SAMD_DSU + 0x101) & 0x01):    # STATUSA.DONE
            if time.time() - start > 5.0:
                raise Exception('Chip erase timeout')
            time.sleep(0.01)
        if self.t.probe.read8(SAMD_DSU + 0x101) & 0x08:
            raise Exception('Chip erase failed')
        self.t.reconnect_after_reset()

    def prepare(self, bank):
        if self.d5x:
            self.t.probe.write16(self.base, self.t.probe.read16(self.base) & ~0x30)     # WMODE = MAN
            regions, lock = 32, self.r(0x18)
            for i in range(regions):
                if not (lock >> i) & 1:
                    self.w(0x14, i * (self.size // regions))
                    self._cmd(0x12)                                 # UR
            self._cmd(0x15)                                         # PBC
        else:
            self.w(0x04, self.r(0x04) | 0x80)                       # CTRLB.MANW
            regions, lock = 16, self.r(0x20) & 0xFFFF
            for i in range(regions):
                if not (lock >> i) & 1:
                    self.w(0x1C, (i * (self.size // regions)) >> 1)
                    self._cmd(0x41)                                 # UR
            self._cmd(0x44)                                         # PBC

    def loader_params(self, bank):
        if self.d5x:
            return {'unit': self.unit, 'sr': self.base + 0x10, 'busy': 1 << 16, 'xor': 1 << 16,
                    'err': 0x4E, 'cr': self.base + 0x04, 'trig': 0xA503, 'pos': self.unit}
        return {'unit': self.unit, 'sr': self.base + 0x14, 'busy': 0x01, 'xor': 0x01,
                'err': 0x02, 'cr': self.base, 'trig': 0xA504, 'pos': self.unit}

    def unlock(self):
        self.erase()

    def lock(self):
        self._cmd(0x16 if self.d5x else 0x45)                       # SSB
        try:
            self.t.write32(AIRCR, 0x05FA0004)
        except (ProbeError, TransferFault):
            pass


# ===================================================================================
# Chip Definitions and Detection
# ===================================================================================

# DBGMCU_IDCODE addresses depending on CPU core
STM32_IDCODE_ADDR = {
    0xC20: [0x40015800],                    # Cortex-M0
    0xC60: [0x40015800],                    # Cortex-M0+
    0xC23: [0xE0042000],                    # Cortex-M3
    0xC24: [0xE0042000],                    # Cortex-M4
    0xC27: [0x5C001000, 0xE0042000],        # Cortex-M7 (H7, F7)
    0xD21: [0xE0044000, 0x44024000],        # Cortex-M33 (L5, U3, U5, WBA, H5)
}

_M0 = 0x40015800
_M4 = 0xE0042000
_M33 = 0xE0044000
_L4 = {'boot': 'sw', 'fz': 0xE0042008}
_G0 = {'boot': 'sel', 'nrst': 'g0', 'fz': 0x40015808}
_L5 = {'l5': True, 'tz': True, 'dual': True, 'fz': 0xE0044008}

# DEV_ID: (IDCODE address, name, driver, flash size register, max flash KB, min RAM KB, options)
STM32_DEVICES = {
    # STM32F0/F1/F3
    0x444: (_M0,  'STM32F03x',             'f1', 0x1FFFF7CC,   32,   4, {}),
    0x445: (_M0,  'STM32F04x/F070x6',      'f1', 0x1FFFF7CC,   32,   6, {}),
    0x440: (_M0,  'STM32F05x/F030x8',      'f1', 0x1FFFF7CC,   64,   8, {}),
    0x448: (_M0,  'STM32F07x/F070xB',      'f1', 0x1FFFF7CC,  128,  16, {}),
    0x442: (_M0,  'STM32F09x/F030xC',      'f1', 0x1FFFF7CC,  256,  32, {}),
    0x412: (_M4,  'STM32F10x (low density)',    'f1', 0x1FFFF7E0,   32,   4, {}),
    0x410: (_M4,  'STM32F10x (medium density)', 'f1', 0x1FFFF7E0,  128,  10, {}),
    0x414: (_M4,  'STM32F10x (high density)',   'f1', 0x1FFFF7E0,  512,  32, {}),
    0x430: (_M4,  'STM32F10x (XL density)',     'f1', 0x1FFFF7E0, 1024,  64, {}),
    0x418: (_M4,  'STM32F105/F107',        'f1', 0x1FFFF7E0,  256,  64, {}),
    0x420: (_M4,  'STM32F100 (low/medium density)', 'f1', 0x1FFFF7E0, 128, 4, {}),
    0x428: (_M4,  'STM32F100 (high density)',       'f1', 0x1FFFF7E0, 512, 24, {}),
    0x422: (_M4,  'STM32F302xB/C/F303xB/C/F358',    'f1', 0x1FFFF7CC, 256, 32, {}),
    0x446: (_M4,  'STM32F302xD/E/F303xD/E/F398',    'f1', 0x1FFFF7CC, 512, 64, {}),
    0x432: (_M4,  'STM32F37x',             'f1', 0x1FFFF7CC,  256,  16, {}),
    0x438: (_M4,  'STM32F303x6/8/F334/F328', 'f1', 0x1FFFF7CC, 64,  12, {}),
    0x439: (_M4,  'STM32F301/F302x6/8/F318', 'f1', 0x1FFFF7CC, 64,  16, {}),
    # STM32F2/F4/F7
    0x411: (_M4,  'STM32F2xx',             'f4', 0x1FFF7A22, 1024,  64, {}),
    0x413: (_M4,  'STM32F40x/F41x',        'f4', 0x1FFF7A22, 1024, 128, {}),
    0x419: (_M4,  'STM32F42x/F43x',        'f4', 0x1FFF7A22, 2048, 192, {}),
    0x434: (_M4,  'STM32F469/F479',        'f4', 0x1FFF7A22, 2048, 320, {}),
    0x423: (_M4,  'STM32F401xB/C',         'f4', 0x1FFF7A22,  256,  64, {}),
    0x433: (_M4,  'STM32F401xD/E',         'f4', 0x1FFF7A22,  512,  96, {}),
    0x431: (_M4,  'STM32F411',             'f4', 0x1FFF7A22,  512, 128, {}),
    0x441: (_M4,  'STM32F412',             'f4', 0x1FFF7A22, 1024, 256, {}),
    0x458: (_M4,  'STM32F410',             'f4', 0x1FFF7A22,  128,  32, {}),
    0x421: (_M4,  'STM32F446',             'f4', 0x1FFF7A22,  512, 128, {}),
    0x463: (_M4,  'STM32F413/F423',        'f4', 0x1FFF7A22, 1536, 320, {}),
    0x449: (_M4,  'STM32F74x/F75x',        'f4', 0x1FF0F442, 1024, 320, {}),
    0x451: (_M4,  'STM32F76x/F77x',        'f4', 0x1FF0F442, 2048, 512, {}),
    0x452: (_M4,  'STM32F72x/F73x',        'f4', 0x1FF07A22,  512, 256, {}),
    # STM32L0/L1
    0x457: (_M0,  'STM32L01x/L02x',        'l0', 0x1FF8007C,   16,   2, {}),
    0x425: (_M0,  'STM32L031/L041',        'l0', 0x1FF8007C,   32,   8, {}),
    0x417: (_M0,  'STM32L05x/L06x',        'l0', 0x1FF8007C,   64,   8, {}),
    0x447: (_M0,  'STM32L07x/L08x',        'l0', 0x1FF8007C,  192,  20, {}),
    0x416: (_M4,  'STM32L1xx (Cat.1)',     'l0', 0x1FF8004C,  128,  10, {}),
    0x429: (_M4,  'STM32L1xx (Cat.2)',     'l0', 0x1FF8004C,  128,  16, {}),
    0x427: (_M4,  'STM32L1xx (Cat.3)',     'l0', 0x1FF800CC,  256,  32, {}),
    0x436: (_M4,  'STM32L1xx (Cat.4)',     'l0', 0x1FF800CC,  384,  48, {}),
    0x437: (_M4,  'STM32L1xx (Cat.5/6)',   'l0', 0x1FF800CC,  512,  80, {}),
    # STM32C0/G0/U0
    0x443: (_M0,  'STM32C01x',             'l4', 0x1FFF75A0,   32,   6, _G0),
    0x453: (_M0,  'STM32C03x',             'l4', 0x1FFF75A0,   32,  12, _G0),
    0x44C: (_M0,  'STM32C05x',             'l4', 0x1FFF75A0,   64,  12, _G0),
    0x493: (_M0,  'STM32C071',             'l4', 0x1FFF75A0,  128,  24, _G0),
    0x44D: (_M0,  'STM32C09x',             'l4', 0x1FFF75A0,  256,  36, _G0),
    0x466: (_M0,  'STM32G03x/G04x',        'l4', 0x1FFF75E0,   64,   8, _G0),
    0x456: (_M0,  'STM32G05x/G06x',        'l4', 0x1FFF75E0,   64,  18, _G0),
    0x460: (_M0,  'STM32G07x/G08x',        'l4', 0x1FFF75E0,  128,  36, _G0),
    0x467: (_M0,  'STM32G0Bx/G0Cx',        'l4', 0x1FFF75E0,  512, 144, dict(_G0, dual=True)),
    0x459: (_M0,  'STM32U031',             'l4', 0x1FFF3EA0,   64,  12, _G0),
    0x489: (_M0,  'STM32U073/U083',        'l4', 0x1FFF6EA0,  256,  40, _G0),
    # STM32G4/L4/L4+/WB/WL
    0x468: (_M4,  'STM32G43x/G44x',        'l4', 0x1FFF75E0,  128,  32, {'boot': 'sw', 'nrst': 'g4', 'fz': 0xE0042008}),
    0x469: (_M4,  'STM32G47x/G48x',        'l4', 0x1FFF75E0,  512, 128, {'boot': 'sw', 'nrst': 'g4', 'fz': 0xE0042008, 'dual': True}),
    0x479: (_M4,  'STM32G49x/G4Ax',        'l4', 0x1FFF75E0,  512, 112, {'boot': 'sw', 'nrst': 'g4', 'fz': 0xE0042008}),
    0x415: (_M4,  'STM32L47x/L48x',        'l4', 0x1FFF75E0, 1024,  96, dict(_L4, dual=True)),
    0x435: (_M4,  'STM32L43x/L44x',        'l4', 0x1FFF75E0,  256,  48, _L4),
    0x461: (_M4,  'STM32L49x/L4Ax',        'l4', 0x1FFF75E0, 1024, 256, dict(_L4, dual=True)),
    0x462: (_M4,  'STM32L45x/L46x',        'l4', 0x1FFF75E0,  512, 128, _L4),
    0x464: (_M4,  'STM32L41x/L42x',        'l4', 0x1FFF75E0,  128,  40, _L4),
    0x470: (_M4,  'STM32L4Rx/L4Sx',        'l4', 0x1FFF75E0, 2048, 192, dict(_L4, dual=True)),
    0x471: (_M4,  'STM32L4Px/L4Qx',        'l4', 0x1FFF75E0, 1024, 192, dict(_L4, dual=True)),
    0x494: (_M4,  'STM32WB1x',             'l4', 0x1FFF75E0,  320,  12, {'base': 0x58004000, 'boot': 'sw'}),
    0x495: (_M4,  'STM32WB5x',             'l4', 0x1FFF75E0, 1024, 192, {'base': 0x58004000, 'boot': 'sw'}),
    0x496: (_M4,  'STM32WB3x',             'l4', 0x1FFF75E0,  512,  96, {'base': 0x58004000, 'boot': 'sw'}),
    0x497: (_M4,  'STM32WLE/WL5x',         'l4', 0x1FFF75E0,  256,  32, {'base': 0x58004000, 'boot': 'sw'}),
    # STM32L5/U3/U5/WBA
    0x472: (_M33, 'STM32L55x/L56x',        'l4', 0x0BFA05E0,  512, 192, dict(_L5, boot='sw5')),
    0x455: (_M33, 'STM32U535/U545',        'l4', 0x0BFA07A0,  512, 192, dict(_L5, quad=True, boot='sw5')),
    0x482: (_M33, 'STM32U57x/U58x',        'l4', 0x0BFA07A0, 2048, 192, dict(_L5, quad=True, boot='sw5')),
    0x481: (_M33, 'STM32U59x/U5Ax',        'l4', 0x0BFA07A0, 4096, 192, dict(_L5, quad=True, boot='sw5')),
    0x476: (_M33, 'STM32U5Fx/U5Gx',        'l4', 0x0BFA07A0, 4096, 192, dict(_L5, quad=True, boot='sw5')),
    0x454: (_M33, 'STM32U37x/U38x',        'l4', 0x0BFA07A0, 1024,  64, _L5),
    0x42A: (_M33, 'STM32U3Bx/U3Cx',        'l4', 0x0BFA07A0, 2048,  64, _L5),
    0x492: (_M33, 'STM32WBA5x',            'l4', 0x0BF907A0, 1024,  64, dict(_L5, quad=True, dual=False)),
    0x4B0: (_M33, 'STM32WBA6x',            'l4', 0x0BFA07A0, 2048,  64, dict(_L5, quad=True)),
    0x4B2: (_M33, 'STM32WBA2x',            'l4', 0x0BF8D7A0,  512,  32, dict(_L5, dual=False)),
    # STM32H5/H7
    0x474: (0x44024000, 'STM32H503',       'h5', 0x08FFF80C,  128,  32, {}),
    0x478: (0x44024000, 'STM32H52x/H53x',  'h5', 0x08FFF80C,  512, 128, {}),
    0x484: (0x44024000, 'STM32H56x/H57x',  'h5', 0x08FFF80C, 2048, 256, {}),
    0x450: (0x5C001000, 'STM32H74x/H75x',  'h7', 0x1FF1E880, 2048, 128, {}),
    0x480: (0x5C001000, 'STM32H7Ax/H7Bx',  'h7', 0x08FFF80C, 2048, 128, {}),
    0x483: (0x5C001000, 'STM32H72x/H73x',  'h7', 0x1FF1E880, 1024, 128, {}),
}

def stm32_chip(target, part, devid, dev):
    addr, name, kind, fsize_addr, maxkb, ramkb, opts = dev
    v = target.try_read32(fsize_addr & ~3)
    kb = 0 if v is None else (v >> (8 * (fsize_addr & 2))) & 0xFFFF
    if devid == 0x436:                                              # L1 Cat.4: 0 = 384 KB, 1 = 256 KB
        kb = 256 if kb == 1 else 384
    if kb == 0 or kb == 0xFFFF or kb > maxkb:
        kb = maxkb
    size = kb * 1024
    base = 0x08000000
    regions = None
    bootpin, nrst, lock = 'fixed', False, True
    if kind == 'f1':
        drv = STM32F1Flash(target, part, devid, size)
        if devid == 0x430 and size > 0x80000:
            regions = [(base, 0x80000, 0), (base + 0x80000, size - 0x80000, 1)]
        if part != 0xC23:
            bootpin = 'option'
    elif kind == 'f4':
        drv = STM32F4Flash(target, part, devid, size)
    elif kind == 'l0':
        drv = STM32L0Flash(target, part, devid, size)
    elif kind == 'l4':
        drv = STM32L4Flash(target, part, devid, size, opts)
        bootpin = 'option' if opts.get('boot') else None
        nrst = opts.get('nrst') is not None
    elif kind == 'h7':
        drv = STM32H7Flash(target, part, devid, size)
        if devid in (0x450, 0x480) and size >= 0x100000:
            half = size // 2
            regions = [(base, half, 0), (base + 0x100000, half, 1)]
    else:
        drv = STM32H5Flash(target, part, devid, size)
        lock = False
    return Chip(name, drv, base, size, 0x20000000, ramkb * 1024, regions, bootpin, nrst, lock)

def py32_chip(target, idcode):
    if idcode is None:
        return None
    if idcode == 0x06188061:
        v = target.try_read32(0x1FFF31FC)
        if v is None:
            return None
        flash = ((v & 7) + 1) << 14                                 # 16 KB units (max. 128 KB)
        return Chip('PY32F07x', PY32Flash(target, 'f07x'), 0x08000000, flash, 0x20000000, 0x2000,
                    bootpin='option', nrst=True)
    if (idcode & 0xFFF) != 0 or idcode in (0, 0xFFFFFFFF):
        return None
    v = target.try_read32(0x1FFF0FFC)
    t = target.try_read32(0x1FFF0F1C)
    if v not in (None, 0, 0xFFFFFFFF) and t not in (None, 0, 0xFFFFFFFF):
        flash, ram = ((v & 7) + 1) << 13, (((v >> 4) & 3) + 1) << 11
        return Chip('PY32F002A/F003/F030', PY32Flash(target, 'f0xx'), 0x08000000, flash, 0x20000000, ram,
                    bootpin='option', nrst=True)
    t = target.try_read32(0x1FFF011C)
    if t not in (None, 0, 0xFFFFFFFF):
        return Chip('PY32F002B', PY32Flash(target, 'f002b'), 0x08000000, 0x6000, 0x20000000, 0xC00,
                    bootpin=None, nrst=True, lock=False)
    return None

SAMD_FAMILIES = {   # (processor, family, series): name
    (1, 0, 0): 'ATSAMD20', (1, 0, 1): 'ATSAMD21', (1, 0, 2): 'ATSAMD10', (1, 0, 3): 'ATSAMD11',
    (1, 0, 4): 'ATSAMD09', (1, 1, 1): 'ATSAML21', (1, 1, 2): 'ATSAML22', (1, 2, 0): 'ATSAMC20',
    (1, 2, 1): 'ATSAMC21', (6, 0, 6): 'ATSAMD51', (6, 3, 1): 'ATSAME51', (6, 3, 3): 'ATSAME53',
    (6, 3, 4): 'ATSAME54',
}

def samd_chip(target, did):
    if did is None:
        return None
    key = (did >> 28, (did >> 23) & 0x1F, (did >> 16) & 0x3F)
    name = SAMD_FAMILIES.get(key)
    if name is None:
        return None
    d5x = key[0] == 6
    drv = SAMDFlash(target, d5x) if target.halted else SAMDLockedFlash(target, d5x)
    return Chip(name, drv, 0x00000000, drv.size, 0x20000000, 0x10000 if d5x else 0x1000, bootpin=None)

class SAMDLockedFlash(SAMDFlash):
    def __init__(self, target, d5x):
        FlashDriver.__init__(self, target)
        self.base = SAMD_NVMCTRL
        self.d5x = d5x
        self.unit = 64
        self.size = 0

def print_supported_chips():
    print('Supported chips:')
    names = sorted(set(d[1] for d in STM32_DEVICES.values()))
    line = ''
    for n in names:
        if len(line) + len(n) > 76:
            print('  ' + line.rstrip(', '))
            line = ''
        line += n + ', '
    print('  ' + line.rstrip(', '))
    print('  PY32F002A, PY32F003, PY32F030, PY32F002B, PY32F071, PY32F072')
    print('  ' + ', '.join(sorted(set(SAMD_FAMILIES.values()))))


# ===================================================================================
# Generic Flash Loader (Thumb code, Cortex-M0 compatible, see loader.S)
# ===================================================================================

LOADER_CODE = (
    0x6801, 0x6842, 0x6883, 0x2B00, 0xD03A, 0x6B45, 0x2D00, 0xD003, 0x6A46, 0x6837,
    0x432F, 0x6037, 0x2400, 0x6AC5, 0x42AC, 0xD101, 0xF000, 0xF833, 0x68C5, 0x42AC,
    0xD20A, 0x6B05, 0x086D, 0xD203, 0x590D, 0x5115, 0x3404, 0xE7F0, 0x5B0D, 0x5315,
    0x3402, 0xE7EC, 0xF3BF, 0x8F4F, 0x6B86, 0x2E00, 0xD001, 0x6BC7, 0x6037, 0x6946,
    0x6836, 0x69C7, 0x407E, 0x6987, 0x423E, 0xD1F3, 0x6946, 0x6836, 0x6A07, 0x423E,
    0xD10E, 0x6B45, 0x2D00, 0xD003, 0x6A46, 0x6837, 0x43AF, 0x6037, 0x68C5, 0x1949,
    0x6905, 0x1952, 0x3B01, 0xE7C2, 0x2000, 0xBE00, 0x6402, 0x0030, 0xBE00, 0x6A46,
    0x6A87, 0x6B05, 0x08AD, 0xD301, 0x6835, 0x432F, 0x6037, 0x4770,
)


# ===================================================================================

if __name__ == "__main__":
    _main()
