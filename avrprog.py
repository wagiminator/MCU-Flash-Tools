#!/usr/bin/env python3
# =====================================================================================
# Project:   avrprog - Programming Tool for AVR Microcontrollers with USBasp/USBtinyISP
# Version:   v1.0
# Year:      2026
# Based on:  avrdude 8.3 (https://github.com/avrdudes/avrdude)
# License:   GNU General Public License v2.0 or later (derived from avrdude)
# =====================================================================================
#
# Description:
# ------------
# Simple single-file Python tool for flashing classic AVR microcontrollers via ISP
# with a USBasp or a USBtinyISP programmer. The programmer type and the connected
# chip are detected automatically. It is a Python port of the relevant parts of
# avrdude 8.3 (usbasp.c, usbtiny.c and the memory algorithms of avr.c, update.c and
# main.c); the USB traffic follows avrdude's. The part data was generated from
# avrdude.conf.
#
# Currently supports these 50 AVRs:
#   ATtiny13(A), ATtiny24A/44A/84A, ATtiny25/45/85, ATtiny2313(A)/4313,
#   ATtiny261A/461A/861A, ATtiny441/841, ATtiny1634, ATtiny167,
#   ATmega8(A), ATmega16(A), ATmega32(A), ATmega48PA/88PA, ATmega168(P)(PA),
#   ATmega328(P)(PB), ATmega64, ATmega128, ATmega162, ATmega164PA/324PA/644PA,
#   ATmega1284(P), ATmega640/1280/2560/2561, ATmega8515, ATmega8535,
#   ATmega32U4, ATmega8U2/16U2, AT90USB1286.
#
# References:
# -----------
# - avrdude: https://github.com/avrdudes/avrdude
# - USBasp:  https://www.fischl.de/usbasp/
# - USBtinyISP: https://learn.adafruit.com/usbtinyisp
#
# Dependencies:
# -------------
# - PyUSB
#
# Operating Instructions:
# -----------------------
# You need to install PyUSB to use avrprog. Install it via "pip install pyusb".
# On Windows, PyUSB also needs a libusb backend ("pip install libusb-package") and
# the programmer needs a libusb compatible driver (WinUSB, libusb-win32 or libusbK,
# installable with Zadig: https://zadig.akeo.ie).
#
# Linux users need permission to access the device. Run:
# echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="16c0", ATTR{idProduct}=="05dc", MODE="666"' | sudo tee /etc/udev/rules.d/99-avrprog.rules
# echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1781", ATTR{idProduct}=="0c9f", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-avrprog.rules
# sudo udevadm control --reload-rules
#
# Connect the programmer to your PC and its ISP cable to the AVR. Run:
# - avrprog.py [-h] [-t {usbasp,usbtiny}] [-p PART] [-B BITCLOCK] [-e] [-f FLASH]
#              [-l LFUSE] [-H HFUSE] [-E EFUSE] [-L LOCK] [-r] [-F] [--list]
#   -h, --help                show help message and exit
#   -t, --programmer          programmer type (default: auto-detect)
#   -p, --part                chip type (default: auto-detect by signature)
#   -B, --bitclock            ISP clock: period in us (e.g. 10) or frequency (e.g. 125kHz)
#   -e, --erase               perform a chip erase (implied with -f)
#   -f FLASH, --flash FLASH   write BIN or HEX file to flash and verify
#   -l, --lfuse VALUE         write low fuse byte
#   -H, --hfuse VALUE         write high fuse byte
#   -E, --efuse VALUE         write extended fuse byte
#   -L, --lock VALUE          write lock byte (after all other actions)
#   -r, --read                read and show fuses, lock bits and calibration
#   -F, --force               allow fuse settings that disable ISP (RSTDISBL, DWEN, SPIEN)
#   --list                    list supported chips
#   Without action arguments the tool shows programmer, chip and fuses.
#
# - Example:
#   python3 avrprog.py -f firmware.hex -l 0xe2 -H 0xdf -E 0xff


import sys
import time
import argparse

# ===================================================================================
# Main Function
# ===================================================================================

def _main():
    # Parse command line arguments
    num = lambda x: int(x, 0)
    parser = argparse.ArgumentParser(description='Minimal command line interface for AVR ISP programming with USBasp and USBtinyISP')
    parser.add_argument('-t', '--programmer', choices=('usbasp', 'usbtiny'), help='programmer type (default: auto-detect)')
    parser.add_argument('-p', '--part',     help='chip type, e.g. m328p (default: auto-detect by signature)')
    parser.add_argument('-B', '--bitclock', help='ISP clock: period in us (e.g. 10) or frequency (e.g. 125kHz)')
    parser.add_argument('-e', '--erase',    action='store_true', help='perform a chip erase (implied with -f)')
    parser.add_argument('-f', '--flash',    help='write BIN or HEX file to flash and verify')
    parser.add_argument('-l', '--lfuse',    type=num, metavar='VALUE', help='write low fuse byte')
    parser.add_argument('-H', '--hfuse',    type=num, metavar='VALUE', help='write high fuse byte')
    parser.add_argument('-E', '--efuse',    type=num, metavar='VALUE', help='write extended fuse byte')
    parser.add_argument('-L', '--lock',     type=num, metavar='VALUE', help='write lock byte (after all other actions)')
    parser.add_argument('-r', '--read',     action='store_true', help='read and show fuses, lock bits and calibration')
    parser.add_argument('-F', '--force',    action='store_true', help='allow fuse settings that disable ISP (RSTDISBL, DWEN, SPIEN)')
    parser.add_argument('--list',           action='store_true', help='list supported chips')
    args = parser.parse_args(sys.argv[1:])

    if args.list:
        for p in AVR_PARTS:
            print('%-8s %-12s signature %02x %02x %02x, %6d bytes flash' % (p[0], p[1], *p[2], p[6]))
        sys.exit(0)

    fuses = [(n, getattr(args, n)) for n in ('lfuse', 'hfuse', 'efuse', 'lock') if getattr(args, n) is not None]
    for n, v in fuses:
        if not 0 <= v <= 0xff:
            sys.stderr.write('ERROR: %s value 0x%x is not a byte!\n' % (n, v))
            sys.exit(1)
    showinfo = args.read or not any((args.erase, args.flash, fuses))

    # Read firmware file first
    firmware = None
    if args.flash is not None:
        try:
            firmware = read_firmware(args.flash)
        except Exception as ex:
            sys.stderr.write('ERROR: %s!\n' % str(ex))
            sys.exit(1)

    # Establish connection to programmer
    try:
        print('Searching for USBasp or USBtinyISP ...')
        isp = connect_programmer(args.programmer, parse_bitclock(args.bitclock))
        print('SUCCESS: Found %s.' % isp.name)
    except Exception as ex:
        sys.stderr.write('ERROR: %s!\n' % str(ex))
        sys.exit(1)

    # Performing actions
    try:
        # Connect to chip and detect it
        print('Connecting to AVR ...')
        part = isp.connect(args.part, args.force)
        print('SUCCESS: Found %s (signature %02x %02x %02x) with %d bytes of flash.' %
              (part.name, *isp.signature, part.flash.size))
        if len(isp.candidates) > 1 and args.part is None:
            print('INFO: Chips with this signature: %s (choose with -p).' % ', '.join(isp.candidates))

        # Check fuse arguments before changing anything
        for n, v in fuses:
            isp.check_fuse(n, v, args.force)

        # Prepare firmware for this chip
        image = None
        if firmware is not None:
            image = FlashImage(firmware, part.flash.size)
            for w in image.warnings:
                print('WARNING: %s.' % w)

        # Perform chip erase
        if args.erase or image is not None:
            print('Performing chip erase ...')
            isp.erase()
            print('SUCCESS: Chip is erased.')

        # Flash firmware
        if image is not None:
            if image.size == 0:
                print('INFO: The file only holds 0xff bytes, nothing to write.')
            else:
                print('Flashing %s to %s ...' % (args.flash, part.name))
                isp.write_flash(image, Progress('Writing'))
                print('Verifying ...')
                isp.verify_flash(image, Progress('Verifying'))
                print('SUCCESS: %d bytes written and verified.' % image.nbytes)

        # Write fuses (lock bits last)
        if fuses:
            print('Writing fuses ...')
            for n, v in fuses:
                isp.write_fuse(n, v)
                print('SUCCESS: %s = 0x%02x written and verified.' % (n, v))

        # Show chip info
        if showinfo:
            for n, v in isp.read_fuses():
                print('%-12s 0x%02x' % (n + ':', v))
            cal = isp.read_calibration()
            if cal:
                print('%-12s %s' % ('calibration:', ' '.join('0x%02x' % x for x in cal)))

    except Exception as ex:
        sys.stderr.write('ERROR: %s!\n' % str(ex))
        isp.close()
        sys.exit(1)

    isp.close()
    print('DONE.')
    sys.exit(0)

# ===================================================================================
# Helper
# ===================================================================================

class AVRError(Exception):
    pass

# Simple progress display
class Progress:
    def __init__(self, label):
        self.label = label
        self.shown = -1

    def __call__(self, done, total):
        pct = 100 * done // total if total else 100
        if pct != self.shown:
            self.shown = pct
            bar = '#' * (pct // 4)
            sys.stdout.write('\r%-9s |%-25s| %3d%%' % (self.label, bar, pct))
            if done >= total:
                sys.stdout.write('\n')
            sys.stdout.flush()

def usleep(us):
    time.sleep(us / 1000000)

# -B option as avrdude: number = period in us, or frequency with Hz/kHz/MHz
def parse_bitclock(s):
    if s is None:
        return 0.0
    t = s.strip().lower()
    try:
        for unit, f in (('mhz', 1e6), ('khz', 1e3), ('hz', 1)):
            if t.endswith(unit):
                return 1 / (float(t[:-len(unit)]) * f)
        if t.endswith('us'):
            t = t[:-2]
        return float(t) / 1e6
    except (ValueError, ZeroDivisionError):
        raise Exception('Invalid bitclock %s' % s) from None

# ===================================================================================
# Firmware Files
# ===================================================================================

# Read BIN or Intel HEX file; returns list of (address, data) segments
def read_firmware(filename):
    with open(filename, 'rb') as f:
        data = f.read()
    if filename.lower().endswith(('.hex', '.ihx', '.ihex')):
        return parse_hex(data.decode('ascii', errors='replace'))
    if not data:
        raise Exception('File %s is empty' % filename)
    return [(0, data)]

def parse_hex(text):
    segs = []
    base = 0
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if not line.startswith(':'):
            raise Exception('HEX line %d does not start with ":"' % n)
        try:
            rec = bytes.fromhex(line[1:])
        except ValueError:
            raise Exception('HEX line %d has invalid characters' % n) from None
        if len(rec) < 5 or len(rec) != rec[0] + 5 or sum(rec) & 0xff:
            raise Exception('HEX line %d is corrupt (length or checksum)' % n)
        length, addr, rtype, payload = rec[0], (rec[1] << 8) | rec[2], rec[3], rec[4:-1]
        if rtype == 0x00:
            segs.append((base + addr, payload))
        elif rtype == 0x01:
            break
        elif rtype == 0x02:
            base = ((payload[0] << 8) | payload[1]) << 4
        elif rtype == 0x04:
            base = ((payload[0] << 8) | payload[1]) << 16
    if not segs:
        raise Exception('HEX file has no data')
    return segs

# Flash image with avrdude's allocation tags
class FlashImage:
    def __init__(self, segs, flashsize):
        self.buf = bytearray(b'\xff' * flashsize)
        self.tags = bytearray(flashsize)
        self.warnings = []
        other = None
        beyond = 0
        for addr, data in segs:
            for i, b in enumerate(data):
                a = addr + i
                if a >= 0x800000:           # avr-gcc: EEPROM 0x810000, fuses 0x820000, lock 0x830000
                    other = a if other is None else min(other, a)
                elif a >= flashsize:
                    beyond = max(beyond, a + 1)
                else:
                    self.buf[a] = b
                    self.tags[a] = 1
        if other is not None:
            self.warnings.append('The file holds EEPROM, fuse or lock data (from 0x%06x) which is not written' % other)
        if beyond:
            raise AVRError('The firmware needs %d bytes, but the chip has only %d bytes of flash' % (beyond, flashsize))
        # avr_mem_hiaddr(): skip trailing 0xff (even size)
        self.size = 0
        for i in range(flashsize - 1, -1, -1):
            if self.buf[i] != 0xff:
                self.size = i + 1 + (0 if i & 1 else 1)
                break
        self.nbytes = sum(self.tags)
        self.lastaddr = max((i for i in range(flashsize) if self.tags[i]), default=-1)
        if not self.nbytes:
            raise AVRError('The file has no data for the flash')

# ===================================================================================
# AVR Parts and SPI Instructions (avrpart.c)
# ===================================================================================

class Op:
    # Instruction pattern of 32 chars, bit 31 first: 0/1 fixed, a address, i input,
    # o output, x ignored (sent as 0)
    def __init__(self, pattern, ext=False):
        self.bits = []
        for k, c in enumerate(pattern):
            pos = 31 - k
            if c == 'a':
                n = 0 if (pos < 8 or pos > 23) else (pos + 8 if ext else pos - 8)
            else:
                n = pos % 8
            self.bits.append((pos, c, n))

    def cmd(self, addr=0, data=0):
        cmd = bytearray(4)
        for pos, c, n in self.bits:
            if c == '1' or (c == 'a' and (addr >> n) & 1) or (c == 'i' and (data >> n) & 1):
                cmd[3 - (pos >> 3)] |= 1 << (pos & 7)
        return cmd

    def output(self, res):
        d = 0
        for pos, c, n in self.bits:
            if c == 'o' and (res[3 - (pos >> 3)] >> (pos & 7)) & 1:
                d |= 1 << n
        return d

def _op(i, ext=False):
    return None if i is None else Op(AVR_OPS[i], ext)

class Memory:
    pass

class Part:
    def __init__(self, entry):
        (self.id, self.name, self.sig, self.chip_erase_delay, pe, ce, size, ps, wd,
         (rl, rh, ll, lh, wp, ext), sigr, cal, fuses, danger) = entry
        self.pgm_enable = _op(pe)
        self.chip_erase = _op(ce)
        f = self.flash = Memory()
        f.name, f.size, f.page_size, f.paged, f.max_write_delay = 'flash', size, ps, True, wd
        f.read_lo, f.read_hi, f.load_lo, f.load_hi, f.write_page, f.ext = _op(rl), _op(rh), _op(ll), _op(lh), _op(wp), _op(ext, True)
        f.read = None
        self.signature = Memory()
        self.signature.name, self.signature.read, self.signature.read_lo, self.signature.ext = 'signature', _op(sigr), None, None
        self.calibration = None
        if cal is not None:
            c = self.calibration = Memory()
            c.name, c.size, c.read, c.read_lo, c.ext = 'calibration', cal[0], _op(cal[1]), None, None
        self.fuses = []
        for name, r, w, fwd, init, mask in fuses:
            m = Memory()
            m.name, m.read, m.write, m.max_write_delay, m.initval, m.bitmask = name, _op(r), _op(w), fwd, init, mask
            m.paged, m.read_lo, m.ext = False, None, None
            self.fuses.append(m)
        self.danger = danger

    def fuse(self, name):
        for m in self.fuses:
            if m.name == name:
                return m
        return None

def find_parts(sig):
    return [p[0] for p in AVR_PARTS if tuple(p[2]) == tuple(sig)]

def get_part(pid):
    for p in AVR_PARTS:
        if p[0] == pid.lower():
            return Part(p)
    return None

# ===================================================================================
# USB Programmers
# ===================================================================================

USBASP_IDS  = ((0x16c0, 0x05dc), (0x03eb, 0xc7b4))   # VOTI shared PID, old fischl.de
USBTINY_IDS = ((0x1781, 0x0c9f),)

def connect_programmer(kind, bitclock):
    try:
        import usb.core
        import usb.util
    except ImportError:
        raise Exception('PyUSB is not installed (pip install pyusb)') from None
    backend = None
    try:                                    # libusb DLL for Windows: pip install libusb-package
        import libusb_package
        backend = libusb_package.get_libusb1_backend()
    except ImportError:
        pass
    found = []
    for k, ids in (('usbasp', USBASP_IDS), ('usbtiny', USBTINY_IDS)):
        if kind not in (None, k):
            continue
        for vid, pid in ids:
            dev = usb.core.find(idVendor=vid, idProduct=pid, backend=backend)
            if dev is not None:
                found.append((k, dev))
                break
    if not found:
        raise Exception('No %s found' % {None: 'USBasp or USBtinyISP', 'usbasp': 'USBasp', 'usbtiny': 'USBtinyISP'}[kind])
    if len(found) > 1:
        print('INFO: USBasp and USBtinyISP found, using the USBasp (choose with -t).')
    k, dev = found[0]
    try:
        dev.set_configuration()
    except usb.core.USBError as ex:
        if ex.errno == 13:
            raise Exception('No access to the programmer (Linux: add the udev rules)') from None
        if ex.errno != 16:   # busy: already configured
            raise Exception('Cannot open the programmer: %s' % str(ex)) from None
    except NotImplementedError:
        raise Exception('Cannot open the programmer: no libusb compatible driver') from None
    usbdev = UsbDevice(dev)
    return USBasp(usbdev, bitclock) if k == 'usbasp' else USBtiny(usbdev, bitclock)

# Vendor control transfers to the device, like usb_control_msg()
class UsbDevice:
    def __init__(self, dev):
        self.dev = dev

    def ctrl_in(self, request, value, index, length, timeout=5000):
        import usb.core
        try:
            data = self.dev.ctrl_transfer(0xc0, request, value & 0xffff, index & 0xffff, length, int(timeout))
            return len(data), bytes(data)
        except usb.core.USBError:
            return -1, b''

    def ctrl_out(self, request, value, index, data, timeout=5000):
        import usb.core
        try:
            return self.dev.ctrl_transfer(0x40, request, value & 0xffff, index & 0xffff, bytes(data), int(timeout))
        except usb.core.USBError:
            return -1

    def close(self):
        import usb.util
        try:
            usb.util.dispose_resources(self.dev)
        except Exception:
            pass

# -----------------------------------------------------------------------------------
# Common part of both programmers: signature, fuses, flash (avr.c, main.c)
# -----------------------------------------------------------------------------------

class ISP:
    def connect(self, partid=None, force=False):
        self.part = get_part('m328p')   # program enable and signature read are the same for all
        self.opened = True
        self.initialize()
        usleep(10000)
        self.signature = tuple(self.read_byte(self.part.signature, i) for i in range(3))
        if all(b == 0xff for b in self.signature) or all(b == 0x00 for b in self.signature):
            raise AVRError('Invalid device signature %02x %02x %02x: check wiring, power and clock of the chip or use a slower bitclock (-B)' % self.signature)
        self.candidates = find_parts(self.signature)
        if partid is not None:
            p = get_part(partid)
            if p is None:
                raise AVRError('Unknown chip %s (see --list)' % partid)
            if p.id not in self.candidates and not force:
                raise AVRError('The signature %02x %02x %02x of the connected chip does not match the %s (use -F to override)' % (*self.signature, p.name))
            self.part = p
        elif not self.candidates:
            raise AVRError('Unsupported chip with signature %02x %02x %02x' % self.signature)
        else:
            self.part = get_part(self.candidates[0])
        return self.part

    def close(self):
        if getattr(self, 'opened', False):
            self.opened = False
            try:
                self.powerdown()
            except Exception:
                pass
        try:
            self.disconnect()
        except Exception:
            pass

    # avr_read_byte_default()
    def read_byte(self, m, addr):
        op = m.read
        if m.read_lo is not None:
            op = m.read_hi if addr & 1 else m.read_lo
            addr //= 2
        if op is None:
            raise AVRError('Reading %s is not supported' % m.name)
        if m.ext is not None:
            self.cmd(m.ext.cmd(addr))
        return op.output(self.cmd(op.cmd(addr)))

    # avr_write_page()
    def write_page(self, m, addr):
        addr //= 2
        if m.ext is not None:
            self.cmd(m.ext.cmd(addr))
        self.cmd(m.write_page.cmd(addr))
        usleep(m.max_write_delay)

    # avr_bitmask_data(): unused bits from the factory value
    def bitmask_data(self, m, data):
        if m.bitmask and m.bitmask != 0xff:
            was = m.initval
            if was == -1:
                try:
                    was = self.read_byte(m, 0)
                except AVRError:
                    was = 0xff
            data = (was & ~m.bitmask & 0xff) | (data & m.bitmask)
        return data

    # avr_can_skip_write_byte(): returns (skip, read_ok)
    def can_skip(self, m, data):
        try:
            value = self.read_byte(m, 0)
        except AVRError:
            return False, False
        return (value & m.bitmask) == (data & m.bitmask), True

    # avr_write_byte_default() for fuses and lock bits
    def write_byte_default(self, m, data):
        data = self.bitmask_data(m, data)
        skip, readok = self.can_skip(m, data)
        if skip:
            return
        if m.write is None:
            raise AVRError('Writing %s is not supported' % m.name)
        self.cmd(m.write.cmd(0, data))
        if not readok:
            usleep(m.max_write_delay)
            return
        tries = 0
        while True:
            usleep(m.max_write_delay)
            r = self.read_byte(m, 0)
            if (r & m.bitmask) == (data & m.bitmask):
                return
            tries += 1
            if tries > 5:
                raise AVRError('Writing %s failed: reads back 0x%02x instead of 0x%02x' % (m.name, r, data))

    # avr_update_byte() as used by -U <fuse>:w:<value>:m
    def update_byte(self, m, data):
        if not self.write_byte_is_default:   # USBasp: usbasp_write_byte() wraps the default
            skip, readok = self.can_skip(m, data)
            if skip:
                return
            data = self.bitmask_data(m, data)
        self.write_byte_default(m, data)

    # Check a fuse argument before anything is written
    def check_fuse(self, name, value, force):
        if self.part.fuse(name) is None:
            raise AVRError('The %s has no %s (it has %s)' % (self.part.name, name, ', '.join(m.name for m in self.part.fuses)))
        for mem, mask, lsh, bad, field in self.part.danger:
            if mem == name and ((value & mask) >> lsh) == bad:
                text = {'RSTDISBL': 'turns the reset pin into an I/O pin', 'DWEN': 'enables debugWIRE',
                        'SPIEN': 'disables serial programming'}[field]
                if not force:
                    raise AVRError('%s = 0x%02x %s (%s), after which ISP no longer works; use -F to write it anyway' % (name, value, text, field))
                print('WARNING: %s = 0x%02x %s (%s); ISP will no longer work!' % (name, value, text, field))

    # -U <fuse>:w:<value>:m with verify
    def write_fuse(self, name, value):
        m = self.part.fuse(name)
        self.update_byte(m, value)
        r = self.read_byte(m, 0)
        if (r & m.bitmask) != (value & m.bitmask):
            raise AVRError('%s verification failed: reads 0x%02x instead of 0x%02x' % (name, r, value))

    def read_fuses(self):
        return [(m.name, self.read_byte(m, 0)) for m in self.part.fuses if m.read is not None]

    def read_calibration(self):
        c = self.part.calibration
        return [self.read_byte(c, i) for i in range(c.size)] if c else None

    def erase(self):
        self.chip_erase()

    # avr_write_mem() for flash with paged writes
    def write_flash(self, image, progress=None):
        m = self.part.flash
        ps = m.page_size
        buf = bytearray(image.buf)
        tags = bytearray(image.tags)
        wsize = min(image.size, m.size)
        cw = (wsize + ps - 1) // ps * ps
        # Fill holes in partly used pages with what the chip holds
        for pa in range(0, cw, ps):
            nset = sum(tags[pa:pa + ps])
            if nset and nset != ps:
                try:
                    d = self.paged_load(m, pa, ps)
                    for i in range(ps):
                        if not tags[pa + i]:
                            tags[pa + i] = 1
                            buf[pa + i] = d[i]
                except AVRError:
                    pass
        pages = [pa for pa in range(0, cw, ps) if any(tags[pa:pa + ps])]
        for n, pa in enumerate(pages, 1):
            self.paged_write(m, pa, buf[pa:pa + ps])
            if progress:
                progress(n, len(pages))
        return len(pages)

    # avr_read_mem() with verify part, then avr_verify_mem()
    def verify_flash(self, image, progress=None):
        m = self.part.flash
        ps = m.page_size
        pages = [pa for pa in range(0, m.size, ps) if any(image.tags[pa:pa + ps])]
        read = bytearray(b'\xff' * m.size)
        for n, pa in enumerate(pages, 1):
            read[pa:pa + ps] = self.paged_load(m, pa, ps)
            if progress:
                progress(n, len(pages))
        bad = [i for i in range(image.lastaddr + 1) if image.tags[i] and read[i] != image.buf[i]]
        if bad:
            i = bad[0]
            raise AVRError('Verification failed at 0x%04x: chip 0x%02x, file 0x%02x (%d bytes differ)' % (i, read[i], image.buf[i], len(bad)))

# -----------------------------------------------------------------------------------
# USBasp (usbasp.c, SPI only)
# -----------------------------------------------------------------------------------

USBASP_FUNC_CONNECT         = 1
USBASP_FUNC_DISCONNECT      = 2
USBASP_FUNC_TRANSMIT        = 3
USBASP_FUNC_READFLASH       = 4
USBASP_FUNC_ENABLEPROG      = 5
USBASP_FUNC_WRITEFLASH      = 6
USBASP_FUNC_SETLONGADDRESS  = 9
USBASP_FUNC_SETISPSCK       = 10
USBASP_FUNC_GETCAPABILITIES = 127
USBASP_CAP_3MHZ             = 1 << 24
USBASP_SCK_OPTIONS = ((13, 3000000), (12, 1500000), (11, 750000), (10, 375000), (9, 187500), (8, 93750),
                      (7, 32000), (6, 16000), (5, 8000), (4, 4000), (3, 2000), (2, 1000), (1, 500))

class USBasp(ISP):
    def __init__(self, usbdev, bitclock):
        self.usb = usbdev
        self.name = 'USBasp'
        self.bitclock = bitclock                # SCK period in seconds, 0 = automatic
        self.write_byte_is_default = False
        self.sckfreq = 0

    def transmit(self, receive, function, send, length=4, data=b''):
        value = (send[1] << 8) | send[0]
        index = (send[3] << 8) | send[2]
        if receive:
            return self.usb.ctrl_in(function, value, index, length)
        return self.usb.ctrl_out(function, value, index, data), b''

    def initialize(self):
        n, res = self.transmit(1, USBASP_FUNC_GETCAPABILITIES, b'\0\0\0\0')
        caps = int.from_bytes(res[:4], 'little') if n == 4 else 0
        self.sck_3mhz = bool(caps & USBASP_CAP_3MHZ)
        self.set_sck_period(self.bitclock)
        self.transmit(1, USBASP_FUNC_CONNECT, b'\0\0\0\0')
        usleep(100000)
        self.program_enable()

    def set_sck_period(self, period):
        option = 0
        self.sckfreq = 0
        if period:
            freq = int(1 / period)
            i = 0 if self.sck_3mhz else 1
            if freq >= USBASP_SCK_OPTIONS[i][1]:
                option, self.sckfreq = USBASP_SCK_OPTIONS[i]
            else:
                for opt, f in USBASP_SCK_OPTIONS[i:]:
                    if freq >= f - 1:
                        option, self.sckfreq = opt, f
                        break
        n, res = self.transmit(1, USBASP_FUNC_SETISPSCK, bytes([option, 0, 0, 0]))
        if n != 1 or res[0] != 0:
            raise AVRError('Cannot set SCK period, please check for USBasp firmware update')

    def program_enable(self):
        n, res = self.transmit(1, USBASP_FUNC_ENABLEPROG, b'\0\0\0\0')
        if n != 1 or res[0] != 0:
            raise AVRError('Target does not answer (0x%02x): check wiring and power or use a slower bitclock (-B)' % (res[0] if n == 1 else 0))

    def cmd(self, cmd):
        n, res = self.transmit(1, USBASP_FUNC_TRANSMIT, cmd)
        if n != 4:
            raise AVRError('USBasp: wrong response size')
        return res

    def chip_erase(self):
        self.transmit(1, USBASP_FUNC_TRANSMIT, self.part.chip_erase.cmd())
        usleep(self.part.chip_erase_delay)
        self.initialize()

    def blocksize(self):
        return 20 if 0 < self.sckfreq < 10000 else 200

    def setaddress(self, addr):
        self.transmit(1, USBASP_FUNC_SETLONGADDRESS, addr.to_bytes(4, 'little'))

    def paged_load(self, m, addr, n):
        out = bytearray()
        block = self.blocksize()
        while n:
            if n <= block:
                block = n
            n -= block
            self.setaddress(addr)
            cnt, data = self.transmit(1, USBASP_FUNC_READFLASH, bytes([addr & 0xff, (addr >> 8) & 0xff, 0, 0]), block)
            if cnt != block:
                raise AVRError('USBasp: wrong number of bytes read (%d)' % cnt)
            out += data
            addr += block
        return out

    def paged_write(self, m, addr, data):
        ps = m.page_size
        block = self.blocksize()
        flags = 1                                # USBASP_BLOCKFLAG_FIRST
        pos = 0
        n = len(data)
        while n:
            if n <= block:
                block = n
            n -= block
            self.setaddress(addr)
            send = bytes([addr & 0xff, (addr >> 8) & 0xff, ps & 0xff, (flags & 0x0f) + ((ps & 0xf00) >> 4)])
            cnt, _ = self.transmit(0, USBASP_FUNC_WRITEFLASH, send, data=data[pos:pos + block])
            flags = 0
            if cnt != block:
                raise AVRError('USBasp: wrong number of bytes written (%d)' % cnt)
            pos += block
            addr += block

    def powerdown(self):
        pass

    def disconnect(self):
        self.transmit(1, USBASP_FUNC_DISCONNECT, b'\0\0\0\0')
        self.usb.close()

# -----------------------------------------------------------------------------------
# USBtinyISP (usbtiny.c, SPI only)
# -----------------------------------------------------------------------------------

USBTINY_POWERUP     = 5
USBTINY_POWERDOWN   = 6
USBTINY_SPI         = 7
USBTINY_FLASH_READ  = 9
USBTINY_FLASH_WRITE = 10
USBTINY_TIMEOUT     = 500

class USBtiny(ISP):
    def __init__(self, usbdev, bitclock):
        self.usb = usbdev
        self.name = 'USBtinyISP'
        self.bitclock = bitclock                # SCK period in seconds, 0 = default 10 us
        self.write_byte_is_default = True

    def control(self, request, value, index):
        n, _ = self.usb.ctrl_in(request, value, index, 0, USBTINY_TIMEOUT)
        if n < 0:
            raise AVRError('USBtinyISP: USB transfer failed')

    def usb_in(self, request, value, index, length, bitclk):
        timeout = USBTINY_TIMEOUT + length * bitclk // 1000
        for _ in range(10):
            n, data = self.usb.ctrl_in(request, value, index, length, timeout)
            if n == length:
                return data
        raise AVRError('USBtinyISP: USB transfer failed (expected %d, got %d)' % (length, n))

    def usb_out(self, request, value, index, data, bitclk):
        n = self.usb.ctrl_out(request, value, index, data, USBTINY_TIMEOUT + len(data) * bitclk // 1000)
        if n != len(data):
            raise AVRError('USBtinyISP: USB transfer failed (expected %d, got %d)' % (len(data), n))

    def initialize(self):
        if self.bitclock > 0:
            self.sck = min(250, max(1, int(self.bitclock * 1e6 + 0.5)))
        else:
            self.sck = 10
        self.control(USBTINY_POWERUP, self.sck, 0)
        self.chunk = 128
        period = self.sck
        while self.chunk > 8 and period > 16:
            self.chunk >>= 1
            period >>= 1
        usleep(50000)
        for _ in range(4):
            try:
                self.cmd(self.part.pgm_enable.cmd())
                return
            except AVRError:
                pass
            self.control(USBTINY_POWERUP, self.sck, 1)
            self.control(USBTINY_POWERUP, self.sck, 0)
            usleep(50000)
        raise AVRError('Target does not answer: check wiring and power or use a slower bitclock (-B)')

    # 4-byte SPI instruction; the chip echoes byte 2 in byte 3 when in sync
    def cmd(self, cmd):
        res = self.usb_in(USBTINY_SPI, (cmd[1] << 8) | cmd[0], (cmd[3] << 8) | cmd[2], 4, 8 * self.sck)
        if res[2] != cmd[1]:
            raise AVRError('Chip does not answer in sync')
        return res

    def chip_erase(self):
        self.cmd(self.part.chip_erase.cmd())
        usleep(self.part.chip_erase_delay)
        self.initialize()

    def paged_load(self, m, addr, n):
        if m.ext is not None:
            self.cmd(m.ext.cmd(addr // 2))
        out = bytearray()
        if addr >= 0x10000:                      # byte access above 64 KiB
            for a in range(addr, addr + n):
                op = m.read_hi if a & 1 else m.read_lo
                out.append(op.output(self.cmd(op.cmd(a // 2))))
            return out
        end = addr + n
        while addr < end:
            chunk = min(self.chunk, end - addr)
            out += self.usb_in(USBTINY_FLASH_READ, 0, addr, chunk, 32 * self.sck)
            addr += chunk
        return out

    def paged_write(self, m, addr, data):
        end = addr + len(data)
        pos = 0
        while addr < end:
            chunk = min(self.chunk, end - addr, m.page_size)
            self.usb_out(USBTINY_FLASH_WRITE, 0, addr, data[pos:pos + chunk], 32 * self.sck)
            nxt = addr + chunk
            if nxt % m.page_size == 0 or nxt == end:
                self.write_page(m, addr)
            pos += chunk
            addr = nxt

    def powerdown(self):
        self.usb.ctrl_in(USBTINY_POWERDOWN, 0, 0, 0, USBTINY_TIMEOUT)

    def disconnect(self):
        self.usb.close()

# ===================================================================================
# Part Data (generated from avrdude.conf of avrdude 8.3)
# ===================================================================================
# AVR_OPS: SPI instruction patterns. AVR_PARTS entries:
# (id, name, signature, chip erase delay [us], pgm_enable, chip_erase,
#  flash size, page size, write delay [us], (read_lo, read_hi, loadpage_lo,
#  loadpage_hi, writepage, load_ext_addr), signature read, (calibration size, read),
#  [(fuse, read, write, write delay [us], factory value, bitmask), ...],
#  [(fuse, mask, shift, dangerous value, field), ...])

AVR_OPS = [
    '0101000000000000xxxxxxxxoooooooo',
    '1010110010100000xxxxxxxxiiiiiiii',
    '0101100000001000xxxxxxxxoooooooo',
    '1010110010101000xxxxxxxxiiiiiiii',
    '010110000000000000000000oooooooo',
    '10101100111000000000000011iiiiii',
    '00111000000xxxxx0000000aoooooooo',
    '10101100010100110000000000000000',
    '10101100100000000000000000000000',
    '001000000000000aaaaaaaaaoooooooo',
    '001010000000000aaaaaaaaaoooooooo',
    '01000000000xxxxxxxxxaaaaiiiiiiii',
    '01001000000xxxxxxxxxaaaaiiiiiiii',
    '010011000000000aaaaaxxxxxxxxxxxx',
    '0011000000000000000000aaoooooooo',
    '0101000000001000xxxxxxxxoooooooo',
    '1010110010100100xxxxxxxxxxxxxxxi',
    '10101100111xxxxxxxxxxxxxxxxxxxii',
    '001110000000000000000000oooooooo',
    '00100000000000aaaaaaaaaaoooooooo',
    '00101000000000aaaaaaaaaaoooooooo',
    '01001100000000aaaaaaxxxxxxxxxxxx',
    '0010000000000aaaaaaaaaaaoooooooo',
    '0010100000000aaaaaaaaaaaoooooooo',
    '01000000000xxxxxxxxaaaaaiiiiiiii',
    '01001000000xxxxxxxxaaaaaiiiiiiii',
    '0100110000000aaaaaaxxxxxxxxxxxxx',
    '001000000000aaaaaaaaaaaaoooooooo',
    '001010000000aaaaaaaaaaaaoooooooo',
    '010011000000aaaaaaaxxxxxxxxxxxxx',
    '01011000xxxxxxxxxxxxxxxxxxxxxxoo',
    '10101100111111iixxxxxxxxxxxxxxxx',
    '00100000xxxxxxaaaaaaaaaaoooooooo',
    '00101000xxxxxxaaaaaaaaaaoooooooo',
    '01000000xxxxxxxxxxxxaaaaiiiiiiii',
    '01001000xxxxxxxxxxxxaaaaiiiiiiii',
    '01001100xxxxxxaaaaaaxxxxxxxxxxxx',
    '00100000xxxxxaaaaaaaaaaaoooooooo',
    '00101000xxxxxaaaaaaaaaaaoooooooo',
    '01000000xxxxxxxxxxxaaaaaiiiiiiii',
    '01001000xxxxxxxxxxxaaaaaiiiiiiii',
    '01001100xxxxxaaaaaaxxxxxxxxxxxxx',
    '00100000xxxxaaaaaaaaaaaaoooooooo',
    '00101000xxxxaaaaaaaaaaaaoooooooo',
    '01001100xxxxaaaaaaaxxxxxxxxxxxxx',
    '1010110010100100xxxxxxxxiiiiiiii',
    '01000000000xxxxxxxxxxaaaiiiiiiii',
    '01001000000xxxxxxxxxxaaaiiiiiiii',
    '0100110000000aaaaaaaaxxxxxxxxxxx',
    '010011000000aaaaaaaaaxxxxxxxxxxx',
    '1010110010100100xxxxxxxxxxxiiiii',
    '10101100111xxxxxxxxxxxxx111111ii',
    '0010000000aaaaaaaaaaaaaaoooooooo',
    '0010100000aaaaaaaaaaaaaaoooooooo',
    '0100110000aaaaaaaaaaxxxxxxxxxxxx',
    '00100000000aaaaaaaaaaaaaoooooooo',
    '00101000000aaaaaaaaaaaaaoooooooo',
    '01000000000xxxxxxxaaaaaaiiiiiiii',
    '01001000000xxxxxxxaaaaaaiiiiiiii',
    '01001100000aaaaaaaxxxxxxxxxxxxxx',
    '0011100000xxxxxx000000aaoooooooo',
    '010000000000xxxxxxxaaaaaiiiiiiii',
    '010010000000xxxxxxxaaaaaiiiiiiii',
    '0100000000xxxxxxxxaaaaaaiiiiiiii',
    '0100100000xxxxxxxxaaaaaaiiiiiiii',
    '0100110000aaaaaaaaxxxxxxxxxxxxxx',
    '1010110010100100xxxxxxxxxxxxxiii',
    '1010110010100100xxxxxxxxxxxxiiii',
    '1010110010100100xxxxxxxxxxxxxxii',
    '00100000xaaaaaaaaaaaaaaaoooooooo',
    '00101000xaaaaaaaaaaaaaaaoooooooo',
    '01000000xxxxxxxxxaaaaaaaiiiiiiii',
    '01001000xxxxxxxxxaaaaaaaiiiiiiii',
    '01001100xaaaaaaaaxxxxxxxxxxxxxxx',
    '00100000aaaaaaaaaaaaaaaaoooooooo',
    '00101000aaaaaaaaaaaaaaaaoooooooo',
    '01001100aaaaaaaaaxxxxxxxxxxxxxxx',
    '1010110010100100xxxxxxxx111iiii1',
    '1010110010100100xxxxxxxx11111iii',
    '001000000aaaaaaaaaaaaaaaoooooooo',
    '001010000aaaaaaaaaaaaaaaoooooooo',
    '010011000aaaaaaaaaxxxxxxxxxxxxxx',
    '0100000000xxxxxxxaaaaaaaiiiiiiii',
    '0100100000xxxxxxxaaaaaaaiiiiiiii',
    '01001101000000000000000a00000000',
    '010011000aaaaaaaaxxxxxxxxxxxxxxx',
    '1010110010100100xxxxxxxx1111iiii',
    '0101100000000000xxxxxxxxoooooooo',
    '01000000xxxxxxxxxxaaaaaaiiiiiiii',
    '01001000xxxxxxxxxxaaaaaaiiiiiiii',
    '01001100aaaaaaaaaaxxxxxxxxxxxxxx',
]

AVR_PARTS = [
    ('t13', 'ATtiny13', (0x1e, 0x90, 0x07), 4000, 7, 8,
     0x00400, 32, 4500, (9, 10, 11, 12, 13, None), 14, (2, 6),
     [('lfuse', 0, 1, 4500, 0x6a, 0xff), ('hfuse', 2, 3, 4500, 0xff, 0x1f), ('lock', 4, 5, 4500, 0xff, 0x03)],
     [('lfuse', 0x80, 7, 1, 'SPIEN'), ('hfuse', 0x01, 0, 0, 'RSTDISBL'), ('hfuse', 0x08, 3, 0, 'DWEN')]),
    ('t13a', 'ATtiny13A', (0x1e, 0x90, 0x07), 4000, 7, 8,
     0x00400, 32, 4500, (9, 10, 11, 12, 13, None), 14, (2, 6),
     [('lfuse', 0, 1, 4500, 0x6a, 0xff), ('hfuse', 2, 3, 4500, 0xff, 0x1f), ('lock', 4, 5, 4500, 0xff, 0x03)],
     [('lfuse', 0x80, 7, 1, 'SPIEN'), ('hfuse', 0x01, 0, 0, 'RSTDISBL'), ('hfuse', 0x08, 3, 0, 'DWEN')]),
    ('t24a', 'ATtiny24A', (0x1e, 0x91, 0x0b), 4500, 7, 8,
     0x00800, 32, 4500, (19, 20, 11, 12, 21, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0xdf, 0xff), ('efuse', 15, 16, 9000, 0xff, 0x01), ('lock', 4, 17, 9000, 0xff, 0x03)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('t25', 'ATtiny25', (0x1e, 0x91, 0x08), 4500, 7, 8,
     0x00800, 32, 4500, (19, 20, 11, 12, 21, None), 14, (2, 6),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0xdf, 0xff), ('efuse', 15, 16, 9000, 0xff, 0x01), ('lock', 4, 5, 9000, 0xff, 0x03)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('t44a', 'ATtiny44A', (0x1e, 0x92, 0x07), 4500, 7, 8,
     0x01000, 64, 4500, (22, 23, 24, 25, 26, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0xdf, 0xff), ('efuse', 15, 16, 9000, 0xff, 0x01), ('lock', 4, 17, 9000, 0xff, 0x03)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('t45', 'ATtiny45', (0x1e, 0x92, 0x06), 4500, 7, 8,
     0x01000, 64, 4500, (22, 23, 24, 25, 26, None), 14, (2, 6),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0xdf, 0xff), ('efuse', 15, 16, 9000, 0xff, 0x01), ('lock', 4, 5, 9000, 0xff, 0x03)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('t84a', 'ATtiny84A', (0x1e, 0x93, 0x0c), 4500, 7, 8,
     0x02000, 64, 4500, (27, 28, 24, 25, 29, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0xdf, 0xff), ('efuse', 15, 16, 9000, 0xff, 0x01), ('lock', 4, 17, 9000, 0xff, 0x03)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('t85', 'ATtiny85', (0x1e, 0x93, 0x0b), 4500, 7, 8,
     0x02000, 64, 4500, (27, 28, 24, 25, 29, None), 14, (2, 6),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0xdf, 0xff), ('efuse', 15, 16, 9000, 0xff, 0x01), ('lock', 4, 5, 9000, 0xff, 0x03)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('t2313', 'ATtiny2313', (0x1e, 0x91, 0x0a), 9000, 7, 8,
     0x00800, 32, 4500, (19, 20, 11, 12, 21, None), 14, (2, 6),
     [('lfuse', 0, 1, 9000, 0x64, 0xff), ('hfuse', 2, 3, 9000, 0xdf, 0xff), ('efuse', 15, 16, 9000, 0xff, 0x01), ('lock', 4, 5, 9000, 0xff, 0x03)],
     [('hfuse', 0x01, 0, 0, 'RSTDISBL'), ('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x80, 7, 0, 'DWEN')]),
    ('t2313a', 'ATtiny2313A', (0x1e, 0x91, 0x0a), 9000, 7, 8,
     0x00800, 32, 4500, (19, 20, 11, 12, 21, None), 14, (2, 6),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0xdf, 0xff), ('efuse', 15, 16, 9000, 0xff, 0x01), ('lock', 4, 5, 9000, 0xff, 0x03)],
     [('hfuse', 0x01, 0, 0, 'RSTDISBL'), ('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x80, 7, 0, 'DWEN')]),
    ('t4313', 'ATtiny4313', (0x1e, 0x92, 0x0d), 9000, 7, 8,
     0x01000, 64, 4500, (22, 23, 24, 25, 26, None), 14, (2, 6),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0xdf, 0xff), ('efuse', 15, 16, 9000, 0xff, 0x01), ('lock', 4, 5, 9000, 0xff, 0x03)],
     [('hfuse', 0x01, 0, 0, 'RSTDISBL'), ('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x80, 7, 0, 'DWEN')]),
    ('t261a', 'ATtiny261A', (0x1e, 0x91, 0x0c), 4000, 7, 8,
     0x00800, 32, 4500, (32, 33, 34, 35, 36, None), 14, (1, 18),
     [('lfuse', 0, 1, 4500, 0x62, 0xff), ('hfuse', 2, 3, 4500, 0xdf, 0xff), ('efuse', 15, 16, 4500, 0xff, 0x01), ('lock', 30, 31, 4500, 0xff, 0x03)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('t461a', 'ATtiny461A', (0x1e, 0x92, 0x08), 4000, 7, 8,
     0x01000, 64, 4500, (37, 38, 39, 40, 41, None), 14, (1, 18),
     [('lfuse', 0, 1, 4500, 0x62, 0xff), ('hfuse', 2, 3, 4500, 0xdf, 0xff), ('efuse', 15, 16, 4500, 0xff, 0x01), ('lock', 30, 31, 4500, 0xff, 0x03)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('t861a', 'ATtiny861A', (0x1e, 0x93, 0x0d), 4000, 7, 8,
     0x02000, 64, 4500, (42, 43, 39, 40, 44, None), 14, (1, 18),
     [('lfuse', 0, 1, 4500, 0x62, 0xff), ('hfuse', 2, 3, 4500, 0xdf, 0xff), ('efuse', 15, 16, 4500, 0xff, 0x01), ('lock', 30, 31, 4500, 0xff, 0x03)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('t441', 'ATtiny441', (0x1e, 0x92, 0x15), 4500, 7, 8,
     0x01000, 16, 4500, (22, 23, 46, 47, 48, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x62, 0xdf), ('hfuse', 2, 3, 9000, 0xdf, 0xff), ('efuse', 15, 45, 9000, 0xff, 0xff), ('lock', 4, 17, 9000, 0xff, 0x03)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('t841', 'ATtiny841', (0x1e, 0x93, 0x15), 4500, 7, 8,
     0x02000, 16, 4500, (27, 28, 46, 47, 49, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x62, 0xdf), ('hfuse', 2, 3, 9000, 0xdf, 0xff), ('efuse', 15, 45, 9000, 0xff, 0xff), ('lock', 4, 17, 9000, 0xff, 0x03)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('t1634', 'ATtiny1634', (0x1e, 0x94, 0x12), 9000, 7, 8,
     0x04000, 32, 4500, (52, 53, 11, 12, 54, None), 14, (1, 18),
     [('lfuse', 0, 1, 4500, 0x62, 0xdf), ('hfuse', 2, 3, 4500, 0xdf, 0xff), ('efuse', 15, 50, 4500, 0xff, 0x1f), ('lock', 4, 51, 4500, 0xff, 0x03)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('t167', 'ATtiny167', (0x1e, 0x94, 0x87), 15000, 7, 8,
     0x04000, 128, 4500, (55, 56, 57, 58, 59, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0xdf, 0xff), ('efuse', 15, 16, 9000, 0xff, 0x01), ('lock', 4, 17, 9000, 0xff, 0x03)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('m8', 'ATmega8', (0x1e, 0x93, 0x07), 9000, 7, 8,
     0x02000, 64, 4500, (27, 28, 61, 62, 29, None), 14, (4, 60),
     [('lfuse', 0, 1, 4500, 0xe1, 0xff), ('hfuse', 2, 3, 4500, 0xd9, 0xff), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('m8a', 'ATmega8A', (0x1e, 0x93, 0x07), 9000, 7, 8,
     0x02000, 64, 4500, (27, 28, 61, 62, 29, None), 14, (4, 60),
     [('lfuse', 0, 1, 4500, 0xe1, 0xff), ('hfuse', 2, 3, 4500, 0xd9, 0xff), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('m16', 'ATmega16', (0x1e, 0x94, 0x03), 9000, 7, 8,
     0x04000, 128, 4500, (52, 53, 63, 64, 65, None), 14, (4, 60),
     [('lfuse', 0, 1, 4500, 0xe1, 0xff), ('hfuse', 2, 3, 4500, 0x99, 0xff), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m16a', 'ATmega16A', (0x1e, 0x94, 0x03), 9000, 7, 8,
     0x04000, 128, 4500, (52, 53, 63, 64, 65, None), 14, (4, 60),
     [('lfuse', 0, 1, 4500, 0xe1, 0xff), ('hfuse', 2, 3, 4500, 0x99, 0xff), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m32', 'ATmega32', (0x1e, 0x95, 0x02), 9000, 7, 8,
     0x08000, 128, 4500, (52, 53, 63, 64, 65, None), 14, (4, 60),
     [('lfuse', 0, 1, 4500, 0xe1, 0xff), ('hfuse', 2, 3, 4500, 0x99, 0xff), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m32a', 'ATmega32A', (0x1e, 0x95, 0x02), 9000, 7, 8,
     0x08000, 128, 4500, (52, 53, 63, 64, 65, None), 14, (4, 60),
     [('lfuse', 0, 1, 4500, 0xe1, 0xff), ('hfuse', 2, 3, 4500, 0x99, 0xff), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m48pa', 'ATmega48PA', (0x1e, 0x92, 0x0a), 45000, 7, 8,
     0x01000, 64, 4500, (22, 23, 24, 25, 26, None), 14, (1, 18),
     [('lfuse', 0, 1, 4500, 0x62, 0xff), ('hfuse', 2, 3, 4500, 0xdf, 0xff), ('efuse', 15, 16, 4500, 0xff, 0x01), ('lock', 4, 5, 4500, 0xff, 0x03)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('m88pa', 'ATmega88PA', (0x1e, 0x93, 0x0f), 9000, 7, 8,
     0x02000, 64, 4500, (27, 28, 24, 25, 29, None), 14, (1, 18),
     [('lfuse', 0, 1, 4500, 0x62, 0xff), ('hfuse', 2, 3, 4500, 0xdf, 0xff), ('efuse', 15, 66, 4500, 0xf9, 0x07), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('m168', 'ATmega168', (0x1e, 0x94, 0x06), 9000, 7, 8,
     0x04000, 128, 4500, (55, 56, 57, 58, 59, None), 14, (1, 18),
     [('lfuse', 0, 1, 4500, 0x62, 0xff), ('hfuse', 2, 3, 4500, 0xdf, 0xff), ('efuse', 15, 66, 4500, 0xf9, 0x07), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('m168p', 'ATmega168P', (0x1e, 0x94, 0x0b), 9000, 7, 8,
     0x04000, 128, 4500, (55, 56, 57, 58, 59, None), 14, (1, 18),
     [('lfuse', 0, 1, 4500, 0x62, 0xff), ('hfuse', 2, 3, 4500, 0xdf, 0xff), ('efuse', 15, 66, 4500, 0xf9, 0x07), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('m168pa', 'ATmega168PA', (0x1e, 0x94, 0x0b), 9000, 7, 8,
     0x04000, 128, 4500, (55, 56, 57, 58, 59, None), 14, (1, 18),
     [('lfuse', 0, 1, 4500, 0x62, 0xff), ('hfuse', 2, 3, 4500, 0xdf, 0xff), ('efuse', 15, 66, 4500, 0xf9, 0x07), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('m328', 'ATmega328', (0x1e, 0x95, 0x14), 9000, 7, 8,
     0x08000, 128, 4500, (52, 53, 57, 58, 65, None), 14, (1, 18),
     [('lfuse', 0, 1, 4500, 0x62, 0xff), ('hfuse', 2, 3, 4500, 0xd9, 0xff), ('efuse', 15, 66, 4500, 0xff, 0x07), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('m328p', 'ATmega328P', (0x1e, 0x95, 0x0f), 9000, 7, 8,
     0x08000, 128, 4500, (52, 53, 57, 58, 65, None), 14, (1, 18),
     [('lfuse', 0, 1, 4500, 0x62, 0xff), ('hfuse', 2, 3, 4500, 0xd9, 0xff), ('efuse', 15, 66, 4500, 0xff, 0x07), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('m328pb', 'ATmega328PB', (0x1e, 0x95, 0x16), 10500, 7, 8,
     0x08000, 128, 4500, (52, 53, 57, 58, 65, None), 14, (1, 18),
     [('lfuse', 0, 1, 4500, 0x62, 0xff), ('hfuse', 2, 3, 4500, 0xd9, 0xff), ('efuse', 15, 67, 4500, 0xf7, 0x0f), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'DWEN'), ('hfuse', 0x80, 7, 0, 'RSTDISBL')]),
    ('m64', 'ATmega64', (0x1e, 0x96, 0x02), 9000, 7, 8,
     0x10000, 256, 4500, (69, 70, 71, 72, 73, None), 14, (4, 60),
     [('lfuse', 0, 1, 4500, 0xe1, 0xff), ('hfuse', 2, 3, 4500, 0x99, 0xff), ('efuse', 15, 68, 4500, 0xfd, 0x03), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m128', 'ATmega128', (0x1e, 0x97, 0x02), 10000, 7, 8,
     0x20000, 256, 5000, (74, 75, 71, 72, 76, None), 14, (4, 60),
     [('lfuse', 0, 1, 4500, 0xe1, 0xff), ('hfuse', 2, 3, 4500, 0x99, 0xff), ('efuse', 15, 68, 4500, 0xfd, 0x03), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m162', 'ATmega162', (0x1e, 0x94, 0x04), 9000, 7, 8,
     0x04000, 128, 4500, (52, 53, 63, 64, 65, None), 14, (1, 18),
     [('lfuse', 0, 1, 16000, 0x62, 0xff), ('hfuse', 2, 3, 16000, 0x99, 0xff), ('efuse', 15, 77, 16000, 0xff, 0x1e), ('lock', 4, 5, 16000, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m164pa', 'ATmega164PA', (0x1e, 0x94, 0x0a), 55000, 7, 8,
     0x04000, 128, 4500, (79, 80, 63, 64, 81, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0x99, 0xff), ('efuse', 15, 78, 9000, 0xff, 0x07), ('lock', 4, 5, 9000, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m324pa', 'ATmega324PA', (0x1e, 0x95, 0x11), 55000, 7, 8,
     0x08000, 128, 4500, (79, 80, 63, 64, 81, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0x99, 0xff), ('efuse', 15, 78, 9000, 0xff, 0x07), ('lock', 4, 5, 9000, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m644pa', 'ATmega644PA', (0x1e, 0x96, 0x0a), 55000, 7, 8,
     0x10000, 256, 4500, (74, 75, 82, 83, 76, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0x99, 0xff), ('efuse', 15, 78, 9000, 0xff, 0x07), ('lock', 4, 5, 9000, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m1284', 'ATmega1284', (0x1e, 0x97, 0x06), 55000, 7, 8,
     0x20000, 256, 4500, (74, 75, 82, 83, 76, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0x99, 0xff), ('efuse', 15, 78, 9000, 0xff, 0x07), ('lock', 4, 5, 9000, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m1284p', 'ATmega1284P', (0x1e, 0x97, 0x05), 55000, 7, 8,
     0x20000, 256, 4500, (74, 75, 82, 83, 76, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0x99, 0xff), ('efuse', 15, 78, 9000, 0xff, 0x07), ('lock', 4, 5, 9000, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m1280', 'ATmega1280', (0x1e, 0x97, 0x03), 9000, 7, 8,
     0x20000, 256, 4500, (74, 75, 71, 72, 76, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0x99, 0xff), ('efuse', 15, 66, 9000, 0xff, 0x07), ('lock', 4, 5, 9000, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m2560', 'ATmega2560', (0x1e, 0x98, 0x01), 9000, 7, 8,
     0x40000, 256, 4500, (74, 75, 71, 72, 76, 84), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0x99, 0xff), ('efuse', 15, 66, 9000, 0xff, 0x07), ('lock', 4, 5, 9000, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m2561', 'ATmega2561', (0x1e, 0x98, 0x02), 9000, 7, 8,
     0x40000, 256, 4500, (74, 75, 71, 72, 76, 84), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0x99, 0xff), ('efuse', 15, 66, 9000, 0xff, 0x07), ('lock', 4, 5, 9000, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m640', 'ATmega640', (0x1e, 0x96, 0x08), 9000, 7, 8,
     0x10000, 256, 4500, (79, 80, 71, 72, 85, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x62, 0xff), ('hfuse', 2, 3, 9000, 0x99, 0xff), ('efuse', 15, 66, 9000, 0xff, 0x07), ('lock', 4, 5, 9000, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m8515', 'ATmega8515', (0x1e, 0x93, 0x06), 9000, 7, 8,
     0x02000, 64, 4500, (27, 28, 61, 62, 29, None), 14, (4, 60),
     [('lfuse', 0, 1, 4500, 0xe1, 0xff), ('hfuse', 2, 3, 4500, 0xd9, 0xff), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m8535', 'ATmega8535', (0x1e, 0x93, 0x08), 9000, 7, 8,
     0x02000, 64, 4500, (27, 28, 61, 62, 29, None), 14, (4, 60),
     [('lfuse', 0, 1, 4500, 0xe1, 0xff), ('hfuse', 2, 3, 4500, 0xd9, 0xff), ('lock', 4, 5, 4500, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m32u4', 'ATmega32U4', (0x1e, 0x95, 0x87), 9000, 7, 8,
     0x08000, 128, 4500, (79, 80, 88, 89, 90, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x52, 0xff), ('hfuse', 2, 3, 9000, 0x99, 0xff), ('efuse', 15, 86, 9000, 0xfb, 0x0f), ('lock', 87, 5, 9000, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
    ('m16u2', 'ATmega16U2', (0x1e, 0x94, 0x89), 9000, 7, 8,
     0x04000, 128, 4500, (74, 75, 88, 89, 90, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x5e, 0xff), ('hfuse', 2, 3, 9000, 0xd9, 0xff), ('efuse', 15, 45, 9000, 0xf4, 0x0f), ('lock', 4, 5, 9000, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'RSTDISBL'), ('hfuse', 0x80, 7, 0, 'DWEN')]),
    ('m8u2', 'ATmega8U2', (0x1e, 0x93, 0x89), 9000, 7, 8,
     0x02000, 128, 4500, (74, 75, 88, 89, 90, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x5e, 0xff), ('hfuse', 2, 3, 9000, 0xd9, 0xff), ('efuse', 15, 45, 9000, 0xf4, 0x0f), ('lock', 4, 5, 9000, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN'), ('hfuse', 0x40, 6, 0, 'RSTDISBL'), ('hfuse', 0x80, 7, 0, 'DWEN')]),
    ('usb1286', 'AT90USB1286', (0x1e, 0x97, 0x82), 9000, 7, 8,
     0x20000, 256, 4500, (74, 75, 71, 72, 76, None), 14, (1, 18),
     [('lfuse', 0, 1, 9000, 0x5e, 0xff), ('hfuse', 2, 3, 9000, 0x99, 0xff), ('efuse', 15, 67, 9000, 0xf3, 0x0f), ('lock', 4, 5, 9000, 0xff, 0x3f)],
     [('hfuse', 0x20, 5, 1, 'SPIEN')]),
]

# ===================================================================================

if __name__ == "__main__":
    _main()
