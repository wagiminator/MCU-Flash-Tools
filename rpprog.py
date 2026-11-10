#!/usr/bin/env python3
# ===================================================================================
# Project:   rpprog - USB Programming Tool for Raspberry Pi RP2040 and RP2350
# Version:   v1.0
# Year:      2026
# Author:    Stefan Wagner
# Github:    https://github.com/wagiminator
# License:   MIT License
# ===================================================================================
#
# Description:
# ------------
# Simple Python tool for flashing Raspberry Pi RP2040 and RP2350 microcontrollers
# (e.g. Raspberry Pi Pico, Pico W, Pico 2, Pico 2 W) via USB using the PICOBOOT
# interface of the factory built-in USB bootloader (BOOTSEL mode). No drive has to
# be mounted. Supported file formats: BIN, UF2, HEX (Intel HEX) and ELF.
#
# The tool can also restart a running firmware into BOOTSEL mode, either via the
# reset interface of the Raspberry Pi Pico SDK (stdio_usb) or via a "1200 baud
# touch" of a USB serial port (e.g. MCU-Templates usb_cdc library, Arduino cores).
#
# References:
# -----------
# - Raspberry Pi picotool: https://github.com/raspberrypi/picotool
# - RP2040 and RP2350 datasheets (chapter "USB Bootloader", "PICOBOOT Interface")
# - Microsoft UF2: https://github.com/microsoft/uf2
#
# Dependencies:
# -------------
# - PyUSB
# - PySerial (only for the 1200 baud touch)
# - libusb-package (Windows only, provides the libusb DLL)
#
# Operating Instructions:
# -----------------------
# You need to install PyUSB and PySerial to use rpprog. Install them via
# "pip install pyusb pyserial". On Windows, also install the libusb backend via
# "pip install libusb-package".
#
# Linux users need permission to access the device. Run:
# echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="2e8a", ATTR{idProduct}=="0003", MODE="666"' | sudo tee /etc/udev/rules.d/99-rp2-boot.rules
# echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="2e8a", ATTR{idProduct}=="000f", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-rp2-boot.rules
# sudo udevadm control --reload-rules
#
# On Windows, the PICOBOOT interface of the RP2040 needs the WinUSB driver. Install it
# with Zadig (https://zadig.akeo.ie/): click "Options" and "List All Devices", select
# "RP2 Boot (Interface 1)" and install the WinUSB driver. The RP2350 provides the
# Microsoft OS descriptors, so Windows usually installs the driver automatically.
#
# Hold the BOOTSEL button while connecting the board via USB (BOOTSEL mode). Run:
# - rpprog.py [-h] [-b] [-p PORT] [-e] [-f FLASH] [-a ADDR] [-r READ] [-s SIZE]
#             [-x] [-n]
#   -h, --help                show help message and exit
#   -b, --bootsel             restart running firmware into BOOTSEL mode first
#   -p PORT, --port PORT      serial port for the 1200 baud touch (with -b)
#   -e, --erase               perform a whole chip erase
#   -f FLASH, --flash FLASH   write BIN/UF2/HEX/ELF file to flash and verify
#   -a ADDR, --address ADDR   flash address for BIN files (default: 0x10000000)
#   -r READ, --read READ      read flash and save it as BIN file
#   -s SIZE, --size SIZE      size for -e and -r (default: detected flash size)
#   -x, --reboot              reboot and start firmware (implied with -e and -f)
#   -n, --noreboot            stay in BOOTSEL mode after -e or -f
#   Without action arguments, the chip and its bootloader are shown.
#
# - Example:
#   python3 rpprog.py -f firmware.uf2
#   python3 rpprog.py -b -f firmware.bin


import sys
import time
import struct
import argparse
import usb.core
import usb.util

# ===================================================================================
# Main Function
# ===================================================================================

def _main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Minimal command line interface for RP2040/RP2350 PICOBOOT')
    parser.add_argument('-b', '--bootsel',  action='store_true', help='restart running firmware into BOOTSEL mode first')
    parser.add_argument('-p', '--port',     help='serial port for the 1200 baud touch (with -b)')
    parser.add_argument('-e', '--erase',    action='store_true', help='perform a whole chip erase')
    parser.add_argument('-f', '--flash',    help='write BIN/UF2/HEX/ELF file to flash and verify')
    parser.add_argument('-a', '--address',  type=lambda x: int(x, 0), default=RP_FLASH_START, metavar='ADDR',
                                            help='flash address for BIN files (default: 0x10000000)')
    parser.add_argument('-r', '--read',     help='read flash and save it as BIN file')
    parser.add_argument('-s', '--size',     type=lambda x: int(x, 0), help='size for -e and -r (default: detected flash size)')
    parser.add_argument('-x', '--reboot',   action='store_true', help='reboot and start firmware (implied with -e and -f)')
    parser.add_argument('-n', '--noreboot', action='store_true', help='stay in BOOTSEL mode after -e or -f')
    args = parser.parse_args(sys.argv[1:])

    # Check arguments
    if args.reboot and args.noreboot:
        sys.stderr.write('ERROR: Options -x and -n exclude each other!\n')
        sys.exit(1)
    if args.size is not None and args.size <= 0:
        sys.stderr.write('ERROR: Invalid size!\n')
        sys.exit(1)

    # Read firmware file
    image = None
    if args.flash is not None:
        try:
            image = FirmwareImage(args.flash, args.address)
        except Exception as ex:
            sys.stderr.write('ERROR: ' + str(ex) + '!\n')
            sys.exit(1)

    # Restart running firmware into BOOTSEL mode
    if args.bootsel:
        try:
            if find_bootsel_device() is None:
                print('Restarting firmware into BOOTSEL mode ...')
                method = enter_bootsel(args.port)
                print('SUCCESS: Restart requested via %s.' % method)
                print('Waiting for USB bootloader ...')
                if not wait_bootsel_device(RP_BOOTSEL_TIMEOUT):
                    raise Exception('USB bootloader did not appear')
            else:
                print('INFO: Device is already in BOOTSEL mode.')
        except Exception as ex:
            sys.stderr.write('ERROR: ' + str(ex) + '!\n')
            sys.exit(1)

    # Establish connection to USB bootloader
    try:
        print('Connecting to USB bootloader ...')
        isp = Programmer()
        print('SUCCESS: Found %s with bootrom v%d.' % (isp.chipname, isp.romversion))
    except Exception as ex:
        sys.stderr.write('ERROR: ' + str(ex) + '!\n')
        sys.exit(1)

    # Performing actions
    try:
        # Show chip info only (no action arguments)
        if not any( (args.erase, args.flash, args.read, args.reboot) ):
            for name, value in isp.info():
                print('%-12s %s' % (name + ':', value))
            isp.close()
            print('DONE.')
            sys.exit(0)

        # Check image
        if image is not None:
            isp.checkimage(image)
            if image.family is not None and image.family not in isp.families:
                raise Exception('UF2 family %s does not match %s' % (uf2_family_name(image.family), isp.chipname))
            for msg in image.warnings(isp.chip):
                print('WARNING: ' + msg)

        # Determine flash size (if needed)
        size = args.size
        if size is None and (args.erase or args.read):
            print('Detecting flash size ...')
            size = isp.flashsize()
            if size:
                print('SUCCESS: Flash size is %s.' % format_size(size))
            else:
                size = isp.defaultsize
                print('INFO: Flash is empty, size cannot be detected, using %s (set size with -s).' % format_size(size))

        # Perform chip erase
        if args.erase:
            print('Erasing %s of flash ...' % format_size(size))
            with Progress(size, 'Erasing') as progress:
                isp.erase(RP_FLASH_START, size, progress.update)
            print('SUCCESS: Flash is erased.')

        # Flash firmware image
        if image is not None:
            print('Flashing %s to %s (%d bytes in %d sectors) ...' % \
                  (args.flash, isp.chipname, image.datasize, len(image.sectors)))
            total = len(image.sectors) * RP_SECTOR_SIZE
            with Progress(total, 'Writing') as progress:
                isp.writesectors(image.sectors, not args.erase, progress.update)
            with Progress(total, 'Verifying') as progress:
                isp.verifysectors(image.sectors, progress.update)
            print('SUCCESS: %d bytes written and verified.' % image.datasize)

        # Read flash
        if args.read is not None:
            print('Reading %s of flash ...' % format_size(size))
            with Progress(size, 'Reading') as progress:
                data = isp.read(RP_FLASH_START, size, progress.update)
            with open(args.read, 'wb') as f: f.write(data)
            print('SUCCESS: %d bytes written to %s.' % (len(data), args.read))

        # Reboot and start firmware or stay in bootloader
        if (args.reboot or args.erase or image is not None) and not args.noreboot:
            print('Rebooting and starting firmware ...')
            isp.reboot()
        else:
            isp.close()

    except Exception as ex:
        sys.stderr.write('ERROR: ' + str(ex) + '!\n')
        isp.close()
        sys.exit(1)

    print('DONE.')
    sys.exit(0)

# ===================================================================================
# Programmer Class
# ===================================================================================

class Programmer:
    # Find device and connect to PICOBOOT interface
    def __init__(self):
        self.dev = find_bootsel_device()
        if self.dev is None:
            raise Exception('No RP2040/RP2350 in BOOTSEL mode found')

        # Chip parameters
        if self.dev.idProduct == RP2040_PRODUCT_ID:
            self.chip = 'RP2040'
            self.families = (UF2_FAMILY_RP2040,)
            self.defaultsize = RP2040_DEFAULT_SIZE
        else:
            self.chip = 'RP2350'
            self.families = (UF2_FAMILY_RP2350_ARM_S, UF2_FAMILY_RP2350_ARM_NS, UF2_FAMILY_RP2350_RISCV,
                             UF2_FAMILY_ABSOLUTE, UF2_FAMILY_DATA)
            self.defaultsize = RP2350_DEFAULT_SIZE
        self.chipname = self.chip

        # Find PICOBOOT interface (vendor class, two bulk endpoints)
        try:
            cfg = self.dev.get_active_configuration()
        except usb.core.USBError:
            cfg = None
        try:
            if cfg is None:
                self.dev.set_configuration()
                cfg = self.dev.get_active_configuration()
        except Exception:
            raise Exception('Failed to access USB device. Check permissions')
        self.intf = None
        for intf in cfg:
            if intf.bInterfaceClass == 0xff and intf.bNumEndpoints == 2:
                self.intf = intf
        if self.intf is None:
            raise Exception('PICOBOOT interface not found (disabled by the firmware?)')
        self.ifnum  = self.intf.bInterfaceNumber
        self.ep_out = usb.util.find_descriptor(self.intf, custom_match = lambda e: \
                      usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
        self.ep_in  = usb.util.find_descriptor(self.intf, custom_match = lambda e: \
                      usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)

        # Claim interface
        try:
            if self.dev.is_kernel_driver_active(self.ifnum):
                self.dev.detach_kernel_driver(self.ifnum)
        except Exception:
            pass
        try:
            usb.util.claim_interface(self.dev, self.ifnum)
        except Exception:
            raise Exception('Failed to claim PICOBOOT interface. Check permissions/driver')

        # Reset interface and get bootrom version
        self.token  = 1
        self.xip    = None                                # XIP state (None: unknown)
        self.eject  = False                               # drive ejected (exclusive access)
        self.reset()
        rom = self.read(RP_ROM_START + 0x10, 4)
        if rom[0:2] != b'Mu':
            raise Exception('Invalid bootrom signature')
        self.romversion = rom[3]

        # RP2350: get chip info (package, chip ID)
        self.chipid = None
        if self.chip == 'RP2350':
            info = self.getsysinfo(SYS_INFO_CHIP_INFO)
            if info[0] & SYS_INFO_CHIP_INFO:
                self.chipname = 'RP2350' + ('A' if info[1] & 1 else 'B')
                self.chipid   = (info[3] << 32) | info[2]

    # -------------------------------------------------------------------------------
    # PICOBOOT Protocol
    # -------------------------------------------------------------------------------

    # Reset PICOBOOT interface (clear halt condition of the endpoints)
    def reset(self):
        for ep in (self.ep_in, self.ep_out):
            try:    self.dev.clear_halt(ep)
            except Exception: pass
        self.dev.ctrl_transfer(0x41, PICOBOOT_IF_RESET, 0, self.ifnum, None, RP_USB_TIMEOUT)

    # Get status of the last command (returns status code)
    def status(self):
        try:
            s = self.dev.ctrl_transfer(0xc1, PICOBOOT_IF_CMD_STATUS, 0, self.ifnum, 16, RP_USB_TIMEOUT)
            return struct.unpack('<IIBB', bytes(s[:10]))[1]
        except Exception:
            return None

    # Send command, transfer data and wait for acknowledge
    def command(self, cmdid, args=b'', data=None, length=0, timeout=None):
        if timeout is None: timeout = RP_USB_TIMEOUT
        if data is not None: length = len(data)
        cmd = struct.pack('<IIBBHI', PICOBOOT_MAGIC, self.token, cmdid, len(args), 0, length)
        cmd += args + bytes(16 - len(args))
        self.token += 1
        reply = None
        try:
            self.ep_out.write(cmd, RP_USB_TIMEOUT)
            if length:
                if cmdid & 0x80:
                    reply = bytes(self.ep_in.read(length, timeout))
                    if len(reply) != length:
                        raise Exception('Data transfer incomplete')
                else:
                    self.ep_out.write(data, timeout)
            # Acknowledge in opposite direction
            if cmdid & 0x80:
                self.ep_out.write(b'\x00', timeout)
            else:
                self.ep_in.read(64, timeout)
        except Exception as ex:
            code = self.status()
            try:    self.reset()
            except Exception: pass
            reason = PICOBOOT_STATUS.get(code, str(ex))
            raise Exception('PICOBOOT command 0x%02x failed (%s)' % (cmdid, reason))
        if cmdid not in (PC_READ, PC_WRITE, PC_EXIT_XIP):
            self.xip = None                               # other commands may change XIP state
        return reply

    # Exclusive access (0: not exclusive, 1: exclusive, 2: exclusive and eject drive)
    def exclusive(self, mode):
        if mode == EXCLUSIVE_AND_EJECT and self.eject:
            return
        self.command(PC_EXCLUSIVE_ACCESS, bytes((mode,)))
        self.eject = (mode == EXCLUSIVE_AND_EJECT)

    # Leave XIP mode (necessary before flash operations; the mass storage interface
    # may change the XIP state as long as the drive is not ejected)
    def exitxip(self):
        if self.xip is not False or not self.eject:
            self.command(PC_EXIT_XIP)
            self.xip = False

    # Get system info (RP2350 only), returns list of 32-bit words
    def getsysinfo(self, flags):
        reply = self.command(PC_GET_INFO, struct.pack('<BBHIII', PICOBOOT_GET_INFO_SYS, 0, 0, flags, 0, 0),
                             length=256)
        return list(struct.unpack('<64I', reply))

    # -------------------------------------------------------------------------------
    # Memory Operations
    # -------------------------------------------------------------------------------

    # Read memory (ROM, RAM or flash)
    def read(self, addr, size, progress=None):
        if is_flash(addr):
            self.exitxip()
        data = bytearray()
        while len(data) < size:
            chunk = min(RP_SECTOR_SIZE, size - len(data))
            data += self.command(PC_READ, struct.pack('<II', addr + len(data), chunk), length=chunk)
            if progress: progress(chunk)
        return bytes(data)

    # Erase flash (address and size are aligned to sectors)
    def erase(self, addr, size, progress=None):
        start = addr & ~(RP_SECTOR_SIZE - 1)
        end   = (addr + size + RP_SECTOR_SIZE - 1) & ~(RP_SECTOR_SIZE - 1)
        self.exclusive(EXCLUSIVE_AND_EJECT)
        self.exitxip()
        while start < end:
            if (start % RP_BLOCK_SIZE == 0) and (end - start >= RP_BLOCK_SIZE):
                chunk = RP_BLOCK_SIZE
            else:
                chunk = RP_SECTOR_SIZE
            self.command(PC_FLASH_ERASE, struct.pack('<II', start, chunk), timeout=RP_USB_TIMEOUT_ERASE)
            start += chunk
            if progress: progress(chunk)

    # Erase (optional) and write flash sectors (dict: address -> 4096 bytes)
    def writesectors(self, sectors, erase=True, progress=None):
        self.exclusive(EXCLUSIVE_AND_EJECT)
        self.exitxip()
        for addr in sorted(sectors):
            if erase:
                self.command(PC_FLASH_ERASE, struct.pack('<II', addr, RP_SECTOR_SIZE), timeout=RP_USB_TIMEOUT_ERASE)
            self.command(PC_WRITE, struct.pack('<II', addr, RP_SECTOR_SIZE), data=sectors[addr],
                         timeout=RP_USB_TIMEOUT_ERASE)
            if progress: progress(RP_SECTOR_SIZE)

    # Verify flash sectors
    def verifysectors(self, sectors, progress=None):
        for addr in sorted(sectors):
            if self.read(addr, RP_SECTOR_SIZE) != sectors[addr]:
                raise Exception('Verification failed at 0x%08x' % addr)
            if progress: progress(RP_SECTOR_SIZE)

    # Detect flash size by searching for mirrored data (returns 0 if flash is empty)
    def flashsize(self):
        first = self.read(RP_FLASH_START, 2 * RP_PAGE_SIZE)
        if first[:RP_PAGE_SIZE] == first[RP_PAGE_SIZE:]:
            return 0
        size = RP_FLASH_MAX_SIZE // 2
        while size >= RP_SECTOR_SIZE:
            if self.read(RP_FLASH_START + size, 2 * RP_PAGE_SIZE) != first:
                break
            size //= 2
        return size * 2

    # Check if firmware image fits into the XIP address range
    def checkimage(self, image):
        for addr in image.sectors:
            if not is_flash(addr) or not is_flash(addr + RP_SECTOR_SIZE - 1):
                raise Exception('Address 0x%08x is outside of the flash address range' % addr)

    # -------------------------------------------------------------------------------
    # Info, Reboot, Close
    # -------------------------------------------------------------------------------

    # Get chip info as list of (name, value)
    def info(self):
        result = [('Chip', self.chipname), ('Bootrom', 'v%d' % self.romversion)]
        if self.chipid is not None:
            result.append(('Chip ID', '%016X' % self.chipid))
        try:
            serial = usb.util.get_string(self.dev, self.dev.iSerialNumber)
            result.append(('USB serial', serial))
        except Exception:
            pass
        size = self.flashsize()
        result.append(('Flash', format_size(size) + ' (detected)' if size else 'empty (size cannot be detected)'))
        if size:
            result.append(('Firmware', describe_firmware(self.read(RP_FLASH_START, RP_SECTOR_SIZE), self.chip)))
        return result

    # Reboot and start firmware from flash
    def reboot(self):
        try:
            if self.chip == 'RP2040':
                self.command(PC_REBOOT, struct.pack('<III', 0, RP2040_SRAM_END, RP_REBOOT_DELAY))
            else:
                self.command(PC_REBOOT2, struct.pack('<IIII', REBOOT2_FLAG_REBOOT_TYPE_FLASH_UPDATE,
                                                     RP_REBOOT_DELAY, RP_FLASH_START, 0))
        except Exception:
            pass
        self.close()

    # Release USB device (and the drive, if exclusive access was requested)
    def close(self):
        try:    self.exclusive(NOT_EXCLUSIVE)
        except Exception: pass
        try:    usb.util.release_interface(self.dev, self.ifnum)
        except Exception: pass
        try:    usb.util.dispose_resources(self.dev)
        except Exception: pass

# ===================================================================================
# Firmware Image Class (BIN, UF2, HEX, ELF)
# ===================================================================================

class FirmwareImage:
    def __init__(self, filename, binaddr=None):
        if binaddr is None: binaddr = RP_FLASH_START
        with open(filename, 'rb') as f: raw = f.read()
        if len(raw) == 0:
            raise Exception('File is empty')
        self.family = None
        self.chunks = []                                  # list of (address, data)
        name = filename.lower()
        if raw[:4] == UF2_MAGIC_START0.to_bytes(4, 'little') or name.endswith('.uf2'):
            self.parseuf2(raw)
        elif raw[:4] == b'\x7fELF':
            self.parseelf(raw)
        elif name.endswith('.hex') or name.endswith('.ihex'):
            self.parsehex(raw)
        else:
            self.chunks.append((binaddr, raw))
        if not self.chunks:
            raise Exception('File contains no data for the flash')

        # Build sectors (4096 bytes, unused bytes are 0xff)
        self.sectors  = {}
        self.datasize = 0
        for addr, data in self.chunks:
            self.datasize += len(data)
            for i in range(len(data)):
                a = addr + i
                s = a & ~(RP_SECTOR_SIZE - 1)
                if s not in self.sectors:
                    self.sectors[s] = bytearray(b'\xff' * RP_SECTOR_SIZE)
                self.sectors[s][a - s] = data[i]
        for s in self.sectors:
            self.sectors[s] = bytes(self.sectors[s])

    # UF2 file: 512-byte blocks with 256 bytes payload each
    def parseuf2(self, raw):
        if len(raw) % 512:
            raise Exception('Invalid UF2 file size')
        for i in range(0, len(raw), 512):
            block = raw[i:i+512]
            m0, m1, flags, addr, size, blockno, numblocks, family = struct.unpack('<8I', block[:32])
            mend = struct.unpack('<I', block[508:512])[0]
            if m0 != UF2_MAGIC_START0 or m1 != UF2_MAGIC_START1 or mend != UF2_MAGIC_END:
                raise Exception('Invalid UF2 block %d' % (i // 512))
            if flags & UF2_FLAG_NOT_MAIN_FLASH:
                continue
            if flags & UF2_FLAG_FAMILY_ID_PRESENT:
                if family == UF2_FAMILY_ABSOLUTE and addr == UF2_ABS_BLOCK_ADDR:
                    continue                              # RP2350-E10 workaround block
                if self.family is None and family not in (UF2_FAMILY_ABSOLUTE, UF2_FAMILY_DATA):
                    self.family = family
            if size > 476:
                raise Exception('Invalid payload size in UF2 block %d' % (i // 512))
            self.chunks.append((addr, block[32:32+size]))

    # Intel HEX file (record types 00, 01, 02, 04; 03 and 05 are ignored)
    def parsehex(self, raw):
        base = 0
        for line in raw.decode('ascii', errors='replace').splitlines():
            line = line.strip()
            if not line: continue
            if line[0] != ':':
                raise Exception('Invalid HEX file')
            rec = bytes.fromhex(line[1:])
            if len(rec) < 5 or len(rec) != rec[0] + 5 or (sum(rec) & 0xff):
                raise Exception('Invalid HEX record: %s' % line)
            addr, rtype, data = (rec[1] << 8) | rec[2], rec[3], rec[4:-1]
            if   rtype == 0x00: self.chunks.append((base + addr, data))
            elif rtype == 0x01: break
            elif rtype == 0x02: base = ((data[0] << 8) | data[1]) << 4
            elif rtype == 0x04: base = ((data[0] << 8) | data[1]) << 16

    # ELF file (32-bit little endian, loadable segments at their physical address)
    def parseelf(self, raw):
        if raw[4] != 1 or raw[5] != 1:
            raise Exception('Only 32-bit little endian ELF files are supported')
        phoff, = struct.unpack('<I', raw[28:32])
        phentsize, phnum = struct.unpack('<HH', raw[42:46])
        for i in range(phnum):
            p = phoff + i * phentsize
            ptype, offset, vaddr, paddr, filesz = struct.unpack('<5I', raw[p:p+20])
            if ptype == 1 and filesz > 0:                 # PT_LOAD
                self.chunks.append((paddr, raw[offset:offset+filesz]))

    # Check for typical problems of the image
    def warnings(self, chip):
        result = []
        first = self.sectors.get(RP_FLASH_START)
        if first is None:
            result.append('Image does not start at 0x10000000, the chip may not boot')
        elif chip == 'RP2040' and not rp2040_boot2_valid(first):
            result.append('No valid second stage bootloader (boot2) found, the RP2040 will not boot')
        elif chip == 'RP2350' and RP2350_BLOCK_MARKER not in first:
            result.append('No IMAGE_DEF block found in the first 4KB, the RP2350 will not boot')
        return result

# ===================================================================================
# Helper Functions
# ===================================================================================

# Get libusb backend (libusb-package provides the libusb DLL on Windows)
def _backend():
    try:
        import libusb_package
        return libusb_package.get_libusb1_backend()
    except ImportError:
        return None

# Find device in BOOTSEL mode
def find_bootsel_device():
    for pid in (RP2040_PRODUCT_ID, RP2350_PRODUCT_ID):
        dev = usb.core.find(idVendor = RP_VENDOR_ID, idProduct = pid, backend = _backend())
        if dev is not None:
            return dev
    return None

# Wait for device in BOOTSEL mode
def wait_bootsel_device(timeout):
    end = time.time() + timeout
    while time.time() < end:
        if find_bootsel_device() is not None:
            time.sleep(0.5)                               # let the OS finish enumeration
            return True
        time.sleep(0.2)
    return False

# Restart running firmware into BOOTSEL mode, returns used method
def enter_bootsel(port=None):
    # Pico SDK reset interface (vendor class, subclass 0x00, protocol 0x01)
    if port is None:
        for dev in usb.core.find(find_all = True, backend = _backend()):
            try:
                for cfg in dev:
                    for intf in cfg:
                        if intf.bInterfaceClass == 0xff and intf.bInterfaceSubClass == RESET_INTERFACE_SUBCLASS \
                           and intf.bInterfaceProtocol == RESET_INTERFACE_PROTOCOL:
                            try:
                                dev.ctrl_transfer(0x21, RESET_REQUEST_BOOTSEL, 0, intf.bInterfaceNumber, None, 2000)
                            except Exception:
                                pass                      # device may reset before answering
                            return 'reset interface of %04x:%04x' % (dev.idVendor, dev.idProduct)
            except Exception:
                continue

    # 1200 baud touch on a USB serial port
    try:
        import serial
        from serial.tools.list_ports import comports
    except ImportError:
        raise Exception('No reset interface found and PySerial is not installed')
    if port is None:
        candidates = [p.device for p in comports() if (p.vid, p.pid) in RP_SERIAL_IDS or p.vid == RP_VENDOR_ID]
        if len(candidates) == 0:
            raise Exception('No running firmware with reset interface or USB serial port found (set port with -p)')
        if len(candidates) > 1:
            raise Exception('Several serial ports found (%s), select one with -p' % ', '.join(candidates))
        port = candidates[0]
    try:
        ser = serial.Serial(port, 1200)
        ser.dtr = False
        time.sleep(0.1)
        ser.close()
    except Exception as ex:
        raise Exception('Failed to open serial port %s (%s)' % (port, str(ex)))
    return '1200 baud touch on ' + port

# Check if address is in the XIP flash range
def is_flash(addr):
    return RP_FLASH_START <= addr < RP_FLASH_START + RP_FLASH_MAX_SIZE

# CRC-32/MPEG-2 (used by the RP2040 boot2 checksum)
def crc32_mpeg2(data):
    crc = 0xffffffff
    for b in data:
        crc ^= b << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04c11db7) & 0xffffffff if crc & 0x80000000 else (crc << 1) & 0xffffffff
    return crc

# Check boot2 checksum of the RP2040 (first 252 bytes, CRC in bytes 252..255)
def rp2040_boot2_valid(sector):
    return crc32_mpeg2(sector[:252]) == struct.unpack('<I', sector[252:256])[0]

# Short description of the firmware in the first flash sector
def describe_firmware(sector, chip):
    if sector == b'\xff' * len(sector):
        return 'none (first sector is empty)'
    if chip == 'RP2040':
        return 'valid boot2 found' if rp2040_boot2_valid(sector) else 'no valid boot2 (will not boot)'
    return 'IMAGE_DEF block found' if RP2350_BLOCK_MARKER in sector else 'no IMAGE_DEF block in the first 4KB'

# Format size in bytes as string
def format_size(size):
    if size >= 1024 * 1024 and size % (1024 * 1024) == 0: return '%d MB' % (size // (1024 * 1024))
    if size >= 1024 and size % 1024 == 0: return '%d KB' % (size // 1024)
    return '%d bytes' % size

# Name of UF2 family ID
def uf2_family_name(family):
    return UF2_FAMILY_NAMES.get(family, '0x%08x' % family)

# Simple progress bar
class Progress:
    def __init__(self, total, desc):
        self.total = max(total, 1)
        self.done  = 0
        self.desc  = desc
        self.show()
    def update(self, n):
        self.done = min(self.done + n, self.total)
        self.show()
    def show(self):
        pct = self.done * 100 // self.total
        bar = '#' * (pct // 4)
        sys.stdout.write('\r%-10s [%-25s] %3d%%' % (self.desc, bar, pct))
        sys.stdout.flush()
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        sys.stdout.write('\n')
        sys.stdout.flush()

# ===================================================================================
# Protocol Constants
# ===================================================================================

RP_VENDOR_ID         = 0x2e8a       # Raspberry Pi
RP2040_PRODUCT_ID    = 0x0003       # RP2040 USB bootloader
RP2350_PRODUCT_ID    = 0x000f       # RP2350 USB bootloader
RP_SERIAL_IDS        = ((0x16c0, 0x27dd),)  # USB CDC of the MCU-Templates (1200 baud touch)

RP_USB_TIMEOUT       = 3000         # timeout for USB operations (ms)
RP_USB_TIMEOUT_ERASE = 10000        # timeout for flash erase and write (ms)
RP_BOOTSEL_TIMEOUT   = 10           # time to wait for the USB bootloader after restart (s)
RP_REBOOT_DELAY      = 500          # delay before reboot (ms)

RP_ROM_START         = 0x00000000   # boot ROM
RP_FLASH_START       = 0x10000000   # flash (XIP)
RP_FLASH_MAX_SIZE    = 0x01000000   # max addressable flash size (16 MB)
RP2040_SRAM_END      = 0x20042000   # end of SRAM (RP2040)
RP_PAGE_SIZE         = 256          # flash page size (programming)
RP_SECTOR_SIZE       = 4096         # flash sector size (erasing)
RP_BLOCK_SIZE        = 65536        # flash block size (fast erase)
RP2040_DEFAULT_SIZE  = 2 * 1024 * 1024  # default flash size (Raspberry Pi Pico)
RP2350_DEFAULT_SIZE  = 4 * 1024 * 1024  # default flash size (Raspberry Pi Pico 2)
RP2350_BLOCK_MARKER  = b'\xd3\xde\xff\xff'  # PICOBIN_BLOCK_MARKER_START (0xffffded3)

PICOBOOT_MAGIC         = 0x431fd10b
PICOBOOT_IF_RESET      = 0x41
PICOBOOT_IF_CMD_STATUS = 0x42

PC_EXCLUSIVE_ACCESS  = 0x01
PC_REBOOT            = 0x02         # RP2040 only
PC_FLASH_ERASE       = 0x03
PC_READ              = 0x84
PC_WRITE             = 0x05
PC_EXIT_XIP          = 0x06
PC_ENTER_CMD_XIP     = 0x07
PC_REBOOT2           = 0x0a         # RP2350 only
PC_GET_INFO          = 0x8b         # RP2350 only

NOT_EXCLUSIVE        = 0
EXCLUSIVE            = 1
EXCLUSIVE_AND_EJECT  = 2

PICOBOOT_GET_INFO_SYS = 1
SYS_INFO_CHIP_INFO   = 0x0001
REBOOT2_FLAG_REBOOT_TYPE_FLASH_UPDATE = 0x4

RESET_INTERFACE_SUBCLASS = 0x00
RESET_INTERFACE_PROTOCOL = 0x01
RESET_REQUEST_BOOTSEL    = 0x01

PICOBOOT_STATUS = {
    0: 'ok', 1: 'unknown command', 2: 'invalid command length', 3: 'invalid transfer length',
    4: 'invalid address', 5: 'bad alignment', 6: 'interleaved write', 7: 'rebooting',
    8: 'unknown error', 9: 'invalid state', 10: 'not permitted', 11: 'invalid argument',
    12: 'buffer too small', 13: 'precondition not met', 14: 'modified data', 15: 'invalid data',
    16: 'not found', 17: 'unsupported modification'
}

UF2_MAGIC_START0     = 0x0a324655
UF2_MAGIC_START1     = 0x9e5d5157
UF2_MAGIC_END        = 0x0ab16f30
UF2_FLAG_NOT_MAIN_FLASH   = 0x00000001
UF2_FLAG_FAMILY_ID_PRESENT = 0x00002000
UF2_ABS_BLOCK_ADDR   = 0x10ffff00   # address of the RP2350-E10 workaround block

UF2_FAMILY_RP2040        = 0xe48bff56
UF2_FAMILY_ABSOLUTE      = 0xe48bff57
UF2_FAMILY_DATA          = 0xe48bff58
UF2_FAMILY_RP2350_ARM_S  = 0xe48bff59
UF2_FAMILY_RP2350_RISCV  = 0xe48bff5a
UF2_FAMILY_RP2350_ARM_NS = 0xe48bff5b

UF2_FAMILY_NAMES = {
    UF2_FAMILY_RP2040: 'rp2040', UF2_FAMILY_ABSOLUTE: 'absolute', UF2_FAMILY_DATA: 'data',
    UF2_FAMILY_RP2350_ARM_S: 'rp2350-arm-s', UF2_FAMILY_RP2350_RISCV: 'rp2350-riscv',
    UF2_FAMILY_RP2350_ARM_NS: 'rp2350-arm-ns'
}

# ===================================================================================

if __name__ == "__main__":
    _main()
