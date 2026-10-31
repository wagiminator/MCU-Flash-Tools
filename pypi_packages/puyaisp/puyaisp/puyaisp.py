#!/usr/bin/env python3
# ===================================================================================
# Project:   puyaisp - Programming Tool for PUYA PY32 Microcontrollers
# Version:   v1.5
# Year:      2023
# Author:    Stefan Wagner
# Github:    https://github.com/wagiminator
# License:   MIT License
# ===================================================================================
#
# Description:
# ------------
# Simple Python tool for flashing PY32 microcontrollers via USB-to-serial converter
# (or USB HID) utilizing the factory built-in embedded boot loader.
#
# Supported microcontrollers (identified by the bootloader PID):
# - PID 0x440: PY32F002A, PY32F003, PY32F030
# - PID 0x448: PY32F071, PY32F072, PY32F040
# - PID 0x413: PY32F403, PY32F303
# Other PY32 with the same bootloader protocol can be flashed as well, but their
# option bytes are not touched.
# PY32F002B and PY32L020 have no UART bootloader in system memory and are therefore
# not supported.
#
# Dependencies:
# -------------
# - pyserial
# - hidapi
# - tqdm
#
# Operating Instructions:
# -----------------------
# You need to install PySerial, hidapi and tqdm to use puyaisp.
# Install them via "python3 -m pip install pyserial hidapi tqdm".
# You may need to install a driver for your USB-to-serial converter.
#
# Connect your USB-to-serial converter to your MCU:
# USB2SERIAL      PY32F002A/F003/F030    PY32F07x/F040    PY32F403/F303
#        RXD <--- PA2 or PA9  or PA14    PA9  or PA14     PA9  or PB10
#        TXD ---> PA3 or PA10 or PA15    PA10 or PA15     PA10 or PB11
#        VCC ---> VCC                    VCC              VCC
#        GND ---> GND                    GND              GND
#
# Set your MCU to bootloader mode by using ONE of the following methods:
# - Disconnect your USB-to-serial converter, pull BOOT0 pin (PF4) to VCC (or press
#   and hold the BOOT button, if your board has one), then connect the converter to
#   your USB port. BOOT0 pin (or BOOT button) can be released now.
# - Connect your USB-to-serial converter to your USB port. Pull BOOT0 pin (PF4)
#   to VCC, then pull nRST (PF2) shortly to GND (or press and hold the BOOT button,
#   then press and release the RESET button and then release the BOOT button, if
#   your board has them).
# These steps are not necessary when using a CH340X USB-to-serial converter with
# control lines for nRST and BOOT0. In this case, the software automatically puts
# the MCU into bootloader mode.
# Unused RX pins of the bootloader UARTs should not float (use pull-up resistors).
#
# Run "python3 puyaisp.py -f firmware.bin".

# If the PID/VID of the USB-to-Serial converter is known, it can be defined here,
# which can make the auto-detection a lot faster. If not, comment out or delete.
#PY_VID  = '1A86'
#PY_PID  = '7523'

# Define BAUD rate here, range: 4800 - 1000000, default and recommended: 115200
PY_BAUD = 115200

# USB HID bootloader defaults
PY_HID_VID = 0xffff
PY_HID_PID = 0x0448
PY_HID_REPORT_SIZE = 64

# Libraries
import sys
import time
import argparse
import serial
import hid
from tqdm import tqdm
from serial import Serial
from serial.tools.list_ports import comports

# ===================================================================================
# Main Function
# ===================================================================================

def _main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Minimal command line interface for PY32 IAP')
    parser.add_argument('-u', '--unlock',   action='store_true', help='unlock chip (remove read protection)')
    parser.add_argument('-l', '--lock',     action='store_true', help='lock chip (set read protection)')
    parser.add_argument('-e', '--erase',    action='store_true', help='perform chip erase (implied with -f)')
    parser.add_argument('-o', '--rstoption',action='store_true', help='reset option bytes')
    parser.add_argument('-G', '--nrstgpio', action='store_true', help='make nRST pin a GPIO pin')
    parser.add_argument('-R', '--nrstreset',action='store_true', help='make nRST pin a RESET pin')
    parser.add_argument('-t', '--transport', choices=('serial', 'hid'), default='serial', help='bootloader transport')
    parser.add_argument('-f', '--flash',    help='write BIN file to flash and verify')
    parser.add_argument('--vid',       type=lambda x: int(x, 0), default=PY_HID_VID, help='HID VID')
    parser.add_argument('--pid',       type=lambda x: int(x, 0), default=PY_HID_PID, help='HID PID')
    parser.add_argument('--path',      help='hidapi device path')
    parser.add_argument('--timeout',   type=int, default=1000, help='read timeout in ms')
    args = parser.parse_args(sys.argv[1:])

    # Check arguments
    if not any( (args.rstoption, args.unlock, args.lock, args.erase, args.nrstgpio, args.nrstreset, args.flash) ):
        print('No arguments - no action!')
        sys.exit(0)
    if args.nrstgpio and args.nrstreset:
        sys.stderr.write('ERROR: Options -G and -R exclude each other!\n')
        sys.exit(1)

    # Read binary file
    data = None
    if args.flash is not None:
        try:
            with open(args.flash, 'rb') as f: data = f.read()
        except Exception as ex:
            sys.stderr.write('ERROR: ' + str(ex) + '!\n')
            sys.exit(1)
        if len(data) == 0:
            sys.stderr.write('ERROR: BIN file is empty!\n')
            sys.exit(1)

    # Establish connection to MCU via USB-to-serial converter
    try:
        if args.transport == 'hid':
            print('Connecting to MCU via USB HID ...')
            isp = HIDProgrammer(args.vid, args.pid, args.path, args.timeout)
        else:
            print('Connecting to MCU via USB-to-serial converter ...')
            isp = Programmer(args.timeout)
        print('SUCCESS: Connection established via', isp.port + '.')
    except Exception as ex:
        sys.stderr.write('ERROR: ' + str(ex) + '!\n')
        sys.exit(1)

    # Performing actions
    try:
        # Get chip info
        print('Getting chip info ...')
        isp.readinfo()
        if isp.chip_known:
            print('SUCCESS: Found ' + isp.chip_options['name'] + ' with bootloader v' + isp.verstr + '.')
        else:
            print('WARNING: Chip with PID 0x%04x is not a known PY32!' % isp.pid)

        # Unlock chip
        if args.unlock:
            print('Unlocking chip ...')
            isp.unlock()
            print('SUCCESS: Chip is unlocked.')
            print('INFO: Other options are ignored!')
            isp.reset()
            print('DONE.')
            sys.exit(0)

        # Read option bytes and check, if chip is locked
        if isp.chip_known:
            print('Reading OPTION bytes ...')
            isp.readoption()
            print('SUCCESS:', isp.optionstr + '.')

        # Check if binary fits into flash
        if isp.chip_known and data is not None and len(data) > isp.chip_options['flash_size']:
            raise Exception('Not enough memory (file: %d bytes, flash: %d bytes)' % \
                            (len(data), isp.chip_options['flash_size']))

        # Perform chip erase
        if (args.erase) or (data is not None):
            print('Performing chip erase ...')
            isp.erase()
            print('SUCCESS: Chip is erased.')

        # Flash binary file
        if data is not None:
            print('Flashing', args.flash, 'to MCU ...')
            data = isp.paddata(data)
            with tqdm(total=len(data), desc='Writing', unit='B', unit_scale=True) as progress:
                isp.writeflash(PY_CODE_ADDR, data, progress.update)
            print('Verifying ...')
            with tqdm(total=len(data), desc='Verifying', unit='B', unit_scale=True) as progress:
                isp.verifyflash(PY_CODE_ADDR, data, progress.update)
            print('SUCCESS:', len(data), 'bytes written and verified.')

        # Manipulate OPTION bytes (only for identified chips)
        if any( (args.rstoption, args.nrstgpio, args.nrstreset, args.lock) ):
            if not isp.chip_known:
                raise Exception('OPTION bytes of unknown chips cannot be changed')
            if args.rstoption:
                print('Setting OPTION bytes to default values ...')
                isp.resetoption()
            if args.nrstgpio:
                print('Setting nRST pin as GPIO in OPTION bytes ...')
                isp.nrst2gpio()
            if args.nrstreset:
                print('Setting nRST pin as RESET in OPTION bytes ...')
                isp.nrst2reset()
            if args.lock:
                print('Setting read protection in OPTION BYTES ...')
                isp.lock()
            print('Writing OPTION bytes ...')
            isp.writeoption()
            print('SUCCESS: OPTION bytes written.')
            isp.reset()
        else:
            isp.run()

    except Exception as ex:
        sys.stderr.write('ERROR: ' + str(ex) + '!\n')
        try:
            isp.reset()
        except:
            pass
        sys.exit(1)

    print('DONE.')
    sys.exit(0)

# ===================================================================================
# Programmer Class
# ===================================================================================

class Programmer(Serial):
    def __init__(self, timeout=1000):
        # BAUD rate:  4800 - 1000000bps (default: 115200), will be auto-detected
        # Data frame: 1 start bit, 8 data bit, 1 parity bit set to even, 1 stop bit
        super().__init__(baudrate = PY_BAUD, parity = serial.PARITY_EVEN, timeout = timeout / 1000)
        self.initoptions()
        self.identify()

    # Initialize OPTION byte layout
    def initoptions(self):
        self.chip_options = PY_CHIP_OPTIONS[PY_CHIP_PID]
        self.chip_known   = False

    # Identify port of programmer and enter programming mode
    def identify(self):
        for p in comports():
            if (('PY_VID' not in globals()) or (PY_VID in p.hwid)) and (('PY_PID' not in globals()) or (PY_PID in p.hwid)):
                self.port = p.device
                try:
                    self.open()
                except:
                    continue
                self.boot()
                self.reset_input_buffer()
                self.write([PY_SYNCH])
                # NACK: bootloader was already synchronized before
                if self.getreply() not in (PY_REPLY_ACK, PY_REPLY_NACK):
                    self.close()
                    continue
                self.reset_input_buffer()
                return
        raise Exception('No MCU in boot mode found')

    # Send command
    def sendcommand(self, command):
        self.write([command, command ^ 0xff])
        if not self.checkreply():
            raise Exception('Device has not acknowledged the command 0x%02x' % command)

    # Send address
    def sendaddress(self, addr):
        stream = addr.to_bytes(4, byteorder='big')
        parity = 0x00
        for x in range(4):
            parity ^= stream[x]
        self.write(stream + bytes([parity]))
        if not self.checkreply():
            raise Exception('Failed to send address 0x%08x' % addr)

    # Get reply byte, None on timeout
    def getreply(self):
        reply = self.read(1)
        if len(reply) != 1:
            return None
        return reply[0]

    # Check if device acknowledged
    def checkreply(self):
        return self.getreply() == PY_REPLY_ACK

    # Wait for reply of a long lasting operation (e.g. erase), skip BUSY bytes
    def waitreply(self, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            reply = self.getreply()
            if reply == PY_REPLY_BUSY or reply is None:
                continue
            return reply == PY_REPLY_ACK
        return False

    #--------------------------------------------------------------------------------

    # Start bootloader
    def boot(self):
        self.rts = False
        self.dtr = False
        self.rts = True
        time.sleep(0.01)
        self.rts = False
        time.sleep(0.01)

    # Reset and disconnect
    def reset(self):
        self.disconnect(True)

    # Start firmware and disconnect
    def run(self):
        self.sendcommand(PY_CMD_GO)
        self.sendaddress(PY_CODE_ADDR)
        self.disconnect(False)

    # Disconnect from MCU, optionally resetting it
    def disconnect(self, reset):
        if not self.is_open:
            return
        self.dtr = True
        if reset:
            self.rts = True
            time.sleep(0.01)
            self.rts = False
        self.close()

    #--------------------------------------------------------------------------------

    # Read info stream
    def readinfostream(self, command):
        self.sendcommand(command)
        response = self.readinforesponse()
        size = response[0]
        stream = response[1:1 + size + 1]
        if len(response) <= size + 2 or response[size + 2] != PY_REPLY_ACK:
            raise Exception('Failed to read info')
        return stream

    # Read a complete info response
    def readinforesponse(self):
        size = self.read(1)
        if not size:
            raise Exception('Failed to read info')
        return size + self.read(size[0] + 1) + self.read(1)

    # Get chip info
    def readinfo(self):
        self.ver    = self.readinfostream(PY_CMD_GET)[0]
        self.verstr = '%x.%x' % (self.ver >> 4, self.ver & 0x0f)
        self.pid    = int.from_bytes(self.readinfostream(PY_CMD_PID), byteorder='big')
        self.setoptionprofile()

    # Select OPTION byte layout
    def setoptionprofile(self):
        self.chip_known = self.pid in PY_CHIP_OPTIONS
        if self.chip_known:
            self.chip_options = PY_CHIP_OPTIONS[self.pid]

    # Read UID
    def readuid(self):
        return self.readflash(self.chip_options['uid_addr'], 128)

    # Read OPTION bytes
    def readoption(self):
        try:
            self.sendcommand(PY_CMD_READ)
        except:
            raise Exception('Chip is locked')
        self.sendaddress(self.chip_options['option_addr'])
        size = self.chip_options['option_size']
        self.sendcommand(size - 1)
        self.option = list(self.read(size))
        if len(self.option) != size:
            raise Exception('Failed to read OPTION bytes')
        self.optionstr = ', '.join('%s: 0x%04x' % (name, self.getoptword(offset)) \
                                   for name, offset in self.chip_options['option_words'])

    # Write OPTION bytes
    def writeoption(self):
        self.writeflash(self.chip_options['option_addr'], self.option)

    # Get 16-bit value of an OPTION word (lower half of the 32-bit word)
    def getoptword(self, offset):
        return self.option[offset] + (self.option[offset + 1] << 8)

    # Set 16-bit value of an OPTION word together with its complement (upper half)
    def setoptword(self, offset, value):
        self.option[offset    ] =   value       & 0xff
        self.option[offset + 1] =  (value >> 8) & 0xff
        self.option[offset + 2] = (~value)      & 0xff
        self.option[offset + 3] = (~value >> 8) & 0xff

    # Get offset of the OPTR word (user options)
    def optroffset(self):
        return self.chip_options['option_words'][0][1]

    # Reset OPTION bytes (only the defined words, reserved bytes are kept)
    def resetoption(self):
        for offset, value in self.chip_options['option_default']:
            self.setoptword(offset, value)

    # Set read protection in OPTION bytes
    def lock(self):
        optr = self.optroffset()
        self.setoptword(optr, (self.getoptword(optr) & 0xff00) | 0x55)

    # Set nRST pin as GPIO in OPTION bytes
    def nrst2gpio(self):
        if not self.chip_options['option_nrst']:
            raise Exception('nRST pin of this chip cannot be configured')
        optr = self.optroffset()
        self.setoptword(optr, self.getoptword(optr) | self.chip_options['option_nrst'])

    # Set nRST pin as RESET in OPTION bytes
    def nrst2reset(self):
        if not self.chip_options['option_nrst']:
            raise Exception('nRST pin of this chip cannot be configured')
        optr = self.optroffset()
        self.setoptword(optr, self.getoptword(optr) & ~self.chip_options['option_nrst'])

    # Unlock (clear) chip and reset
    def unlock(self):
        self.sendcommand(PY_CMD_R_UNLOCK)
        if not self.waitreply(PY_ERASE_TIMEOUT):
            raise Exception('Failed to unlock chip')

    #--------------------------------------------------------------------------------

    # Erase whole chip
    def erase(self):
        self.sendcommand(PY_CMD_ERASE)
        self.write(b'\xff\xff')
        self.write(b'\x00')
        if not self.waitreply(PY_ERASE_TIMEOUT):
            raise Exception('Failed to erase chip')

    # Pad data with 0xff to a multiple of 4 bytes
    def paddata(self, data):
        if len(data) % 4:
            data = bytes(data) + b'\xff' * (4 - len(data) % 4)
        return data

    # Read flash
    def readflash(self, addr, size, progress=None):
        data = bytearray()
        while size > 0:
            blocksize = min(size, PY_BLOCKSIZE)
            self.sendcommand(PY_CMD_READ)
            self.sendaddress(addr)
            self.sendcommand(blocksize - 1)
            block = self.read(blocksize)
            if len(block) != blocksize:
                raise Exception('Failed to read from address 0x%08x' % addr)
            data += block
            if progress is not None:
                progress(len(block))
            addr += blocksize
            size -= blocksize
        return bytes(data)

    # Write flash
    def writeflash(self, addr, data, progress=None):
        data = bytes(data)
        for offset in range(0, len(data), PY_BLOCKSIZE):
            block = data[offset:offset + PY_BLOCKSIZE]
            blocksize = len(block)
            parity = blocksize - 1
            for x in block:
                parity ^= x
            self.sendcommand(PY_CMD_WRITE)
            self.sendaddress(addr + offset)
            self.write([blocksize - 1])
            self.write(block + bytes([parity]))
            if not self.checkreply():
                raise Exception('Failed to write to address 0x%08x' % (addr + offset))
            if progress is not None:
                progress(blocksize)

    # Verify flash
    def verifyflash(self, addr, data, progress=None):
        flash = self.readflash(addr, len(data), progress)
        if flash != bytes(data):
            for i in range(len(data)):
                if flash[i] != data[i]: break
            raise Exception('Verification failed at address 0x%08x' % (addr + i))

# ===================================================================================
# HID Programmer Class
# ===================================================================================

class HIDProgrammer(Programmer):
    def __init__(self, vid, pid, path, timeout):
        self.is_open = False
        self.dev = None
        self.usb_vid = vid
        self.usb_pid = pid
        self.path = path
        self.hid_timeout = timeout
        self.initoptions()
        self.dev = hid.device()
        self.open()
        self.boot()
        self.port = 'USB HID %04x:%04x' % (vid, pid)

    # Open HID device
    def open(self):
        if self.path:
            path = self.path.encode() if isinstance(self.path, str) else self.path
            self.dev.open_path(path)
        else:
            self.dev.open(self.usb_vid, self.usb_pid)
        try:
            self.dev.set_nonblocking(False)
        except:
            pass
        self.is_open = True

    # Close HID device
    def close(self):
        if self.dev and self.is_open:
            self.dev.close()
        self.is_open = False

    # Write one or more HID output reports
    def write(self, data):
        data = bytes(data)
        while data:
            block = data[:PY_HID_REPORT_SIZE]
            self.writereport(block)
            data = data[PY_HID_REPORT_SIZE:]

    # Write a single HID output report
    def writereport(self, data):
        report = bytes(data) + bytes(PY_HID_REPORT_SIZE - len(data))
        written = self.dev.write(bytes([0]) + report)
        if written < PY_HID_REPORT_SIZE:
            raise Exception('Short HID write')

    # Read bytes from one or more HID input reports
    def read(self, size):
        data = bytes()
        while len(data) < size:
            report = bytes(self.dev.read(PY_HID_REPORT_SIZE, self.hid_timeout))
            if not report:
                break
            data += report[:size - len(data)]
        return data

    # Flush pending HID input reports
    def drain(self):
        for _ in range(8):
            try:
                if not self.dev.read(PY_HID_REPORT_SIZE, 10):
                    break
            except:
                break

    # Start bootloader
    def boot(self):
        self.drain()
        self.writereport(bytes([PY_SYNCH]) * PY_HID_REPORT_SIZE)
        if self.getreply() in (PY_REPLY_ACK, PY_REPLY_NACK):
            return
        raise Exception('No MCU in HID boot mode found')

    # Disconnect from MCU
    def disconnect(self, reset):
        self.close()

    # Read a complete info response
    def readinforesponse(self):
        report = bytes(self.dev.read(PY_HID_REPORT_SIZE, self.hid_timeout))
        if not report:
            raise Exception('Failed to read info')
        return report

# ===================================================================================
# Device Constants
# ===================================================================================

# Device and Memory constants
PY_CHIP_PID      = 0x440
PY_BLOCKSIZE     = 128
PY_FLASH_ADDR    = 0x08000000
PY_CODE_ADDR     = 0x08000000
PY_SRAM_ADDR     = 0x20000000
PY_BOOT_ADDR     = 0x1fff0000
PY_ERASE_TIMEOUT = 10

# Command codes
PY_CMD_GET      = 0x00
PY_CMD_VER      = 0x01
PY_CMD_PID      = 0x02
PY_CMD_READ     = 0x11
PY_CMD_WRITE    = 0x31
PY_CMD_ERASE    = 0x44
PY_CMD_GO       = 0x21
PY_CMD_W_LOCK   = 0x63
PY_CMD_W_UNLOCK = 0x73
PY_CMD_R_LOCK   = 0x82
PY_CMD_R_UNLOCK = 0x92

# Reply codes
PY_REPLY_ACK    = 0x79
PY_REPLY_NACK   = 0x1f
PY_REPLY_BUSY   = 0xaa

# Other codes
PY_SYNCH        = 0x7f

# Chip profiles by bootloader PID
# option_words:   (name, byte offset) of the 32-bit OPTION words, OPTR first
#                 (lower half: value, upper half: complement)
# option_default: (byte offset, 16-bit production value) of the OPTION words
# option_nrst:    NRST_MODE bit in OPTR (None: not configurable)
PY_CHIP_OPTIONS = {
    0x440: {
        'name':           'PY32F002A/F003/F030',
        'flash_size':     64 * 1024,
        'uid_addr':       0x1fff0e00,
        'option_addr':    0x1fff0e80,
        'option_size':    16,
        'option_words':   (('OPTR', 0), ('SDKR', 4), ('WRPR', 12)),
        'option_default': ((0, 0xbeaa), (4, 0x00ff), (12, 0xffff)),
        'option_nrst':    0x4000,
    },
    0x448: {
        'name':           'PY32F07x/F040',
        'flash_size':     128 * 1024,
        'uid_addr':       0x1fff3000,
        'option_addr':    0x1fff3100,
        'option_size':    32,
        'option_words':   (('OPTR', 0), ('SDKR', 8), ('WRPR', 24)),
        'option_default': ((0, 0xd8aa), (8, 0x001f), (24, 0xffff)),
        'option_nrst':    0x2000,
    },
    0x413: {
        'name':           'PY32F403/F303',
        'flash_size':     512 * 1024,
        'uid_addr':       0x1fff5800,
        'option_addr':    0x1fff5000,
        'option_size':    16,
        'option_words':   (('OPTR', 0), ('WRPR', 12)),
        'option_default': ((0, 0x70aa), (12, 0x0fff)),
        'option_nrst':    None,
    },
}

# ===================================================================================

if __name__ == "__main__":
    _main()
