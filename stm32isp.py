#!/usr/bin/env python3
# ===================================================================================
# Project:   stm32isp - Programming Tool for STM32 Microcontrollers
# Version:   v1.0
# Year:      2023
# Author:    Stefan Wagner
# Github:    https://github.com/wagiminator
# License:   MIT License
# ===================================================================================
#
# Description:
# ------------
# Python tool for flashing STM32 microcontrollers via USB-to-serial converter
# utilizing the factory built-in USART boot loader (protocol: ST AN3155).
# The chip is identified by the product ID reported by the bootloader.
# Supported devices (bootloader with USART interface according to ST AN2606):
# - STM32C0:  C011, C031, C051, C071, C091/092
# - STM32F0:  F03x, F04x, F05x, F07x, F09x
# - STM32F1:  F10x low/medium/high/XL-density, value line, connectivity line
# - STM32F2:  F20x/21x
# - STM32F3:  F301/302/303/318/328/334/358/373/378/398
# - STM32F4:  F401/405/407/410/411/412/413/415/417/42x/43x/446/469/479
# - STM32F7:  F72x/73x/74x/75x/76x/77x
# - STM32G0:  G03x/04x/05x/06x/07x/08x/0Bx/0C1
# - STM32G4:  G431/441/47x/48x/491/4A1
# - STM32H5:  H503/563/573
# - STM32H7:  H72x/73x/74x/75x/7A3/7B3
# - STM32L0:  L01x/02x/031/041/05x/06x/07x/08x
# - STM32L1:  all categories
# - STM32L4:  L41x/42x/43x/44x/45x/46x/47x/48x/49x/4Ax/4Px/4Qx/4Rx/4Sx
# - STM32L5:  L552/562
# - STM32U5:  U535/545/575/585/595/599/5A9
# - STM32WB:  WB10/15/30/35/50/55
# - STM32WL:  WLE5/WL55
#
# Dependencies:
# -------------
# - pyserial
#
# Operating Instructions:
# -----------------------
# You need to install PySerial to use stm32isp.
# Install it via "python3 -m pip install pyserial".
# You may need to install a driver for your USB-to-serial converter.
#
# On some STM32 (C0, G0), the BOOT0 pin is disabled by default. As soon as the chip
# is brand new and/or the main flash memory is deleted, this is not a problem, the
# embedded bootloader will automatically start. Using this stm32isp tool will
# automatically activate the BOOT0 pin so that it can also be used in the following.
# However, if the chip has already been written to before using a different software
# tool, it is likely that the bootloader can no longer be activated via the BOOT0
# pin. In this case, the bit nBOOT_SEL in the User Option Bytes must be deleted (set
# to 0) using an SWD programmer (e.g. ST-Link) and appropriate software.
#
# Connect your USB-to-serial converter to the bootloader USART of your MCU
# (USART1 on all supported devices, see ST AN2606 for further USARTs):
# USB2SERIAL      STM32
#        RXD <--- PA9  (TX)  (PA11 on small STM32C0/G0 packages)
#        TXD ---> PA10 (RX)  (PA12 on small STM32C0/G0 packages)
#        VCC ---> VCC
#        GND ---> GND
# Further bootloader USARTs, e.g.:
# - STM32F03xx4/6: PA14/PA15
# - STM32G03x/04x, STM32L01x/02x: PA2/PA3
#
# Set your MCU to boot mode by using the following method:
# - Connect your USB-to-serial converter to your USB port. Pull BOOT0 pin to VCC,
#   then pull nRST shortly to GND (or press and hold the BOOT button, then press
#   and release the RESET button and then release the BOOT button, if your board
#   has them).
#
# Run "python3 stm32isp.py -f firmware.bin".

# If the PID/VID of the USB-to-Serial converter is known, it can be defined here,
# which can make the auto-detection a lot faster. If not, comment out or delete.
#ST_VID  = '1A86'
#ST_PID  = '7523'

# Define BAUD rate here, range: 1200 - 115200, default: 115200
ST_BAUD = 115200

# Libraries
import sys
import time
import argparse
import serial
from serial import Serial
from serial.tools.list_ports import comports

# ===================================================================================
# Main Function
# ===================================================================================

def _main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Minimal command line interface for STM32 ISP')
    parser.add_argument('-u', '--unlock',   action='store_true', help='unlock chip (remove read protection)')
    parser.add_argument('-l', '--lock',     action='store_true', help='lock chip (set read protection)')
    parser.add_argument('-e', '--erase',    action='store_true', help='perform a chip erase (implied with -f)')
    parser.add_argument('-f', '--flash',    help='write BIN file to flash and verify')
    args = parser.parse_args(sys.argv[1:])

    # Check arguments
    if not any( (args.unlock, args.lock, args.erase, args.flash) ):
        print('No arguments - no action!')
        sys.exit(0)

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
        print('Connecting to MCU via USB-to-serial converter ...')
        isp = Programmer()
        print('SUCCESS: Connection established via', isp.port + '.')
    except Exception as ex:
        sys.stderr.write('ERROR: ' + str(ex) + '!\n')
        sys.exit(1)

    # Performing actions
    try:
        # Get chip info
        print('Getting chip info ...')
        isp.readinfo()
        print('SUCCESS: Found', isp.chipname, 'with bootloader v' + isp.verstr + '.')

        # Check if chip is locked, unlock if so (this erases the chip)
        unlocked = False
        if isp.checklocked():
            if not any( (args.unlock, args.erase, data) ):
                print('INFO: Chip is already locked.')
                isp.close()
                print('DONE.')
                sys.exit(0)
            print('Chip is locked, unlocking and erasing ...')
            isp.unlock()
            print('SUCCESS: Chip is unlocked and erased.')
            unlocked = True
            if not any( (data, args.lock) ):
                isp.close()
                print('DONE.')
                sys.exit(0)
            isp.reconnect()
            if isp.checklocked():
                raise Exception('Chip is still locked')
        elif args.unlock:
            print('INFO: Chip is already unlocked.')

        # Read OPTION bytes and flash size
        isp.readdetails()
        if data is not None and isp.flashsize and len(data) > isp.flashsize:
            raise Exception('Not enough memory (file: %d bytes, flash: %d bytes)' % (len(data), isp.flashsize))

        # Erase chip
        if args.erase and not unlocked:
            print('Performing chip erase ...')
            isp.erase()
            print('SUCCESS: Chip is erased.')
        elif data is not None and not unlocked:
            print('Performing chip erase ...')
            isp.erase(len(data))
            print('SUCCESS: Chip is erased.')

        # Flash binary file
        if data is not None:
            print('Flashing', args.flash, 'to', isp.chipname, '...')
            data = isp.paddata(data, isp.family['align'])
            isp.writeflash(ST_CODE_ADDR, data, skipempty=True)
            print('Verifying ...')
            isp.verifyflash(ST_CODE_ADDR, data)
            print('SUCCESS:', len(data), 'bytes written and verified.')

        # Enable BOOT0 pin in OPTION bytes (nBOOT_SEL = 0) for STM32C0/G0
        if isp.family['bootsel'] and isp.option and isp.checkbootpin():
            print('Enabling BOOT0 pin in OPTION bytes ...')
            isp.enablebootpin()
            print('SUCCESS: Modified OPTION bytes written.')
            if args.lock:
                isp.reconnect()
            else:
                isp.close()

        # Lock chip (set readout protection)
        if args.lock:
            print('Locking chip ...')
            isp.lock()
            print('SUCCESS: Chip is locked.')
            print('INFO: A power-on reset may need to be performed.')
            isp.close()

        # Run firmware
        if isp.is_open:
            isp.run()

    except Exception as ex:
        sys.stderr.write('ERROR: ' + str(ex) + '!\n')
        try:
            isp.close()
        except:
            pass
        sys.exit(1)

    print('DONE.')
    sys.exit(0)

# ===================================================================================
# Programmer Class
# ===================================================================================

class Programmer(Serial):
    def __init__(self):
        # BAUD rate:  1200 - 115200bps (default: 115200), will be auto-detected
        # Data frame: 1 start bit, 8 data bit, 1 parity bit set to even, 1 stop bit
        super().__init__(baudrate = ST_BAUD, parity = serial.PARITY_EVEN, timeout = ST_TIMEOUT)
        self.identify()

    # Identify port of programmer and enter programming mode
    def identify(self):
        for p in comports():
            if (('ST_VID' not in globals()) or (ST_VID in p.hwid)) and (('ST_PID' not in globals()) or (ST_PID in p.hwid)):
                self.port = p.device
                try:
                    self.open()
                except:
                    continue
                if self.synch():
                    return
                self.close()
        raise Exception('No MCU in boot mode found')

    # Synchronize with the bootloader (NACK: bootloader was already synchronized)
    def synch(self):
        self.reset_input_buffer()
        self.write([ST_SYNCH])
        return self.getreply() in (ST_REPLY_ACK, ST_REPLY_NACK)

    # Reconnect after the chip has performed a system reset
    def reconnect(self):
        timeout = self.timeout
        self.timeout = 0.2
        time.sleep(0.2)
        try:
            for x in range(20):
                if self.synch():
                    self.timeout = timeout
                    self.readinfo()
                    return
        finally:
            self.timeout = timeout
        raise Exception('Chip did not restart the bootloader, put it into boot mode again')

    # Send command
    def sendcommand(self, command):
        self.write([command, command ^ 0xff])
        reply = self.getreply()
        if reply != ST_REPLY_ACK:
            raise CommandError('Device has not acknowledged the command 0x%02x' % command, reply)

    # Send address
    def sendaddress(self, addr):
        stream = addr.to_bytes(4, byteorder='big')
        parity = 0x00
        for x in range(4):
            parity ^= stream[x]
        self.write(stream + bytes([parity]))
        reply = self.getreply()
        if reply != ST_REPLY_ACK:
            raise CommandError('Failed to send address 0x%08x' % addr, reply)

    # Get reply byte (None on timeout), optionally with a longer timeout
    def getreply(self, timeout=None):
        if timeout is not None:
            saved = self.timeout
            self.timeout = timeout
        try:
            reply = self.read(1)
        finally:
            if timeout is not None:
                self.timeout = saved
        return reply[0] if len(reply) == 1 else None

    # Check if device acknowledged
    def checkreply(self, timeout=None):
        return self.getreply(timeout) == ST_REPLY_ACK

    #--------------------------------------------------------------------------------

    # Read info stream
    def readinfostream(self, command):
        self.sendcommand(command)
        size = self.read(1)
        if len(size) != 1:
            raise Exception('Failed to read info')
        stream = self.read(size[0] + 1)
        if len(stream) != size[0] + 1 or not self.checkreply():
            raise Exception('Failed to read info')
        return stream

    # Get chip info
    def readinfo(self):
        self.info   = self.readinfostream(ST_CMD_GET)
        self.ver    = self.info[0]
        self.verstr = '%x.%x' % (self.ver >> 4, self.ver & 0x0f)
        self.cmds   = list(self.info[1:])
        self.pid    = int.from_bytes(self.readinfostream(ST_CMD_PID), byteorder='big')
        self.device = None

        # Find device in dictionary
        for d in DEVICES:
            if d['id'] == self.pid:
                self.device = d
                break
        if self.device is None:
            raise Exception('Unsupported chip (ID: 0x%03x)' % self.pid)

        # Set parameters according to dictionary
        self.family    = FAMILIES[self.device['family']]
        self.chipname  = self.device['name']
        self.flashsize = self.device['flash'] * 1024
        self.pagesize  = self.device.get('page', self.family['page'])
        self.option    = None

    # Check if chip is locked (bootloader refuses to read the flash)
    def checklocked(self):
        try:
            self.readflash(ST_CODE_ADDR, 4)
        except CommandError as ex:
            if ex.reply != ST_REPLY_NACK:
                raise
            return True
        return False

    # Read OPTION bytes (STM32C0/G0) and flash size register
    def readdetails(self):
        if self.family['bootsel']:
            try:
                self.option = list(self.readflash(self.family['opt_addr'], 8))
            except CommandError as ex:
                if ex.reply != ST_REPLY_NACK:
                    raise
        fsize = self.device.get('fsize', self.family['fsize'])
        if fsize is not None:
            try:
                size = int.from_bytes(self.readflash(fsize, 2), byteorder='little')
                if 4 <= size <= 4096:
                    self.flashsize = size * 1024
            except CommandError as ex:
                if ex.reply != ST_REPLY_NACK:
                    raise

    # Check if BOOT0 pin ist disabled in OPTION bytes (STM32C0/G0 only)
    def checkbootpin(self):
        return ((self.option[3] & 0x01) == 0x01)

    # Enable BOOT0 pin in OPTION bytes (nBOOT_SEL = 0), STM32C0/G0 only
    def enablebootpin(self):
        if self.family['bootsel']:
            option = list(self.option)
            option[3] = (option[3] & 0b11111000) | 0b00000110
            for x in range(4):
                option[x+4] = option[x] ^ 0xff
            self.writeflash(self.family['opt_addr'], option)
            self.option = option

    # Unlock chip (remove readout protection), erase and reset
    def unlock(self):
        self.sendcommand(ST_CMD_R_UNLOCK)
        if not self.checkreply(ST_ERASE_TIMEOUT):
            raise Exception('Failed to unlock chip')

    # Lock chip (set readout protection) and reset
    def lock(self):
        self.sendcommand(ST_CMD_R_LOCK)
        if not self.checkreply(ST_ERASE_TIMEOUT):
            raise Exception('Failed to lock chip')

    # Start firmware and disconnect
    def run(self):
        self.sendcommand(ST_CMD_GO)
        self.sendaddress(ST_CODE_ADDR)
        self.close()

    #--------------------------------------------------------------------------------

    # Erase whole chip (mass erase) or the pages needed for size bytes
    def erase(self, size=None):
        if self.family['masserase']:
            if ST_CMD_ERASE_X in self.cmds:
                self.sendcommand(ST_CMD_ERASE_X)
                self.write(b'\xff\xff\x00')
            elif ST_CMD_ERASE in self.cmds:
                self.sendcommand(ST_CMD_ERASE)
                self.write(b'\xff\x00')
            else:
                raise Exception('Bootloader has no erase command')
            reply = self.getreply(ST_ERASE_TIMEOUT)
            if reply == ST_REPLY_ACK:
                return
            if reply != ST_REPLY_NACK or not self.pagesize:
                raise Exception('Failed to erase chip')
        if not self.pagesize:
            raise Exception('Chip cannot be erased page by page')
        if size is None:
            size = self.flashsize
        self.erasepages((size + self.pagesize - 1) // self.pagesize)

    # Erase number of pages
    def erasepages(self, pagecount):
        extended = ST_CMD_ERASE_X in self.cmds
        if not extended and (ST_CMD_ERASE not in self.cmds or pagecount > 256):
            raise Exception('Failed to erase pages')
        group = 64 if extended else 128
        for first in range(0, pagecount, group):
            pages = range(first, min(first + group, pagecount))
            if extended:
                self.sendcommand(ST_CMD_ERASE_X)
                stream = [(len(pages) - 1) >> 8, (len(pages) - 1) & 0xff]
                for x in pages:
                    stream += [x >> 8, x & 0xff]
            else:
                self.sendcommand(ST_CMD_ERASE)
                stream = [len(pages) - 1] + list(pages)
            parity = 0x00
            for x in stream:
                parity ^= x
            self.write(bytes(stream + [parity]))
            if not self.checkreply(ST_ERASE_TIMEOUT):
                raise Exception('Failed to erase pages')

    # Read flash
    def readflash(self, addr, size):
        data = bytearray()
        while size > 0:
            blocksize = min(size, ST_PAGE_SIZE)
            self.sendcommand(ST_CMD_READ)
            self.sendaddress(addr)
            self.sendcommand(blocksize - 1)
            block = self.read(blocksize)
            if len(block) != blocksize:
                raise Exception('Failed to read from address 0x%08x' % addr)
            data += block
            addr += blocksize
            size -= blocksize
        return bytes(data)

    # Write to flash (skipempty: skip blocks with 0xff only on erased flash)
    def writeflash(self, addr, data, skipempty=False):
        data = bytes(data)
        for offset in range(0, len(data), ST_PAGE_SIZE):
            block = data[offset:offset + ST_PAGE_SIZE]
            if skipempty and block == b'\xff' * len(block):
                continue
            parity = len(block) - 1
            for x in block:
                parity ^= x
            self.sendcommand(ST_CMD_WRITE)
            self.sendaddress(addr + offset)
            self.write(bytes([len(block) - 1]) + block + bytes([parity]))
            if not self.checkreply(ST_WRITE_TIMEOUT):
                raise Exception('Failed to write to address 0x%08x' % (addr + offset))

    # Verify flash
    def verifyflash(self, addr, data):
        flash = self.readflash(addr, len(data))
        if flash != bytes(data):
            for i in range(len(data)):
                if flash[i] != data[i]: break
            raise Exception('Verification failed at address 0x%08x' % (addr + i))

    # Pad data
    def paddata(self, data, pagesize):
        if (len(data) % pagesize) > 0:
            data += b'\xff' * (pagesize - (len(data) % pagesize))
        return data

# Exception for not acknowledged commands
class CommandError(Exception):
    def __init__(self, message, reply):
        super().__init__(message)
        self.reply = reply

# ===================================================================================
# Device Constants
# ===================================================================================

# Device and Memory constants
ST_PAGE_SIZE    = 256
ST_FLASH_ADDR   = 0x08000000
ST_CODE_ADDR    = 0x08000000
ST_SRAM_ADDR    = 0x20000000

# Timeouts in seconds
ST_TIMEOUT       = 1
ST_WRITE_TIMEOUT = 2
ST_ERASE_TIMEOUT = 60

# Command codes
ST_CMD_GET      = 0x00
ST_CMD_VER      = 0x01
ST_CMD_PID      = 0x02
ST_CMD_READ     = 0x11
ST_CMD_WRITE    = 0x31
ST_CMD_ERASE    = 0x43
ST_CMD_ERASE_X  = 0x44
ST_CMD_GO       = 0x21
ST_CMD_W_LOCK   = 0x63
ST_CMD_W_UNLOCK = 0x73
ST_CMD_R_LOCK   = 0x82
ST_CMD_R_UNLOCK = 0x92

# Reply codes
ST_REPLY_ACK    = 0x79
ST_REPLY_NACK   = 0x1f
ST_REPLY_BUSY   = 0xaa

# Other codes
ST_SYNCH        = 0x7f

# ===================================================================================
# Device definitions
# ===================================================================================

# Device families
# opt_addr:  address of the OPTION bytes (only used for the BOOT0 pin on STM32C0/G0)
# fsize:     address of the flash size register (KB, 16 bit)
# page:      page size for page erase (0: sectors of different size, no page erase)
# align:     data is padded to a multiple of this (flash programming width)
# masserase: bootloader supports mass erase
# bootsel:   BOOT0 pin can be disabled by nBOOT_SEL in the OPTION bytes
FAMILIES = {
    'C0': {'opt_addr': 0x1fff7800, 'fsize': 0x1fff75a0, 'page':   2048, 'align':  8, 'masserase': True,  'bootsel': True },
    'F0': {'opt_addr': 0x1ffff800, 'fsize': 0x1ffff7cc, 'page':   1024, 'align':  8, 'masserase': True,  'bootsel': False},
    'F1': {'opt_addr': 0x1ffff800, 'fsize': 0x1ffff7e0, 'page':   1024, 'align':  8, 'masserase': True,  'bootsel': False},
    'F2': {'opt_addr': 0x1fffc000, 'fsize': 0x1fff7a22, 'page':      0, 'align':  8, 'masserase': True,  'bootsel': False},
    'F3': {'opt_addr': 0x1ffff800, 'fsize': 0x1ffff7cc, 'page':   2048, 'align':  8, 'masserase': True,  'bootsel': False},
    'F4': {'opt_addr': 0x1fffc000, 'fsize': 0x1fff7a22, 'page':      0, 'align':  8, 'masserase': True,  'bootsel': False},
    'F7': {'opt_addr': 0x1fff0000, 'fsize': None,       'page':      0, 'align':  8, 'masserase': True,  'bootsel': False},
    'G0': {'opt_addr': 0x1fff7800, 'fsize': 0x1fff75e0, 'page':   2048, 'align':  8, 'masserase': True,  'bootsel': True },
    'G4': {'opt_addr': 0x1fff7800, 'fsize': 0x1fff75e0, 'page':   2048, 'align':  8, 'masserase': True,  'bootsel': False},
    'H5': {'opt_addr': None,       'fsize': 0x08fff80c, 'page':      0, 'align': 16, 'masserase': True,  'bootsel': False},
    'H7': {'opt_addr': None,       'fsize': None,       'page':      0, 'align': 32, 'masserase': True,  'bootsel': False},
    'L0': {'opt_addr': 0x1ff80000, 'fsize': 0x1ff8007c, 'page':    128, 'align':  8, 'masserase': False, 'bootsel': False},
    'L1': {'opt_addr': 0x1ff80000, 'fsize': 0x1ff800cc, 'page':    256, 'align':  8, 'masserase': False, 'bootsel': False},
    'L4': {'opt_addr': 0x1fff7800, 'fsize': 0x1fff75e0, 'page':   2048, 'align':  8, 'masserase': True,  'bootsel': False},
    'L5': {'opt_addr': None,       'fsize': 0x0bfa05e0, 'page':      0, 'align':  8, 'masserase': True,  'bootsel': False},
    'U5': {'opt_addr': None,       'fsize': 0x0bfa07a0, 'page':      0, 'align': 16, 'masserase': True,  'bootsel': False},
    'WB': {'opt_addr': 0x1fff8000, 'fsize': 0x1fff75e0, 'page':   4096, 'align':  8, 'masserase': True,  'bootsel': False},
    'WL': {'opt_addr': 0x1fff7800, 'fsize': 0x1fff75e0, 'page':   2048, 'align':  8, 'masserase': True,  'bootsel': False},
}

# Devices by bootloader product ID (ST AN2606), flash: largest device of the line in KB
DEVICES = [
    {'name': 'STM32C011xx',             'id': 0x443, 'family': 'C0', 'flash':   32},
    {'name': 'STM32C031xx',             'id': 0x453, 'family': 'C0', 'flash':   32},
    {'name': 'STM32C051xx',             'id': 0x44c, 'family': 'C0', 'flash':   64},
    {'name': 'STM32C071xx',             'id': 0x493, 'family': 'C0', 'flash':  128},
    {'name': 'STM32C091xx/092xx',       'id': 0x44d, 'family': 'C0', 'flash':  256},

    {'name': 'STM32F03xx4/6',           'id': 0x444, 'family': 'F0', 'flash':   32},
    {'name': 'STM32F030x8/05x',         'id': 0x440, 'family': 'F0', 'flash':   64},
    {'name': 'STM32F04x/070x6',         'id': 0x445, 'family': 'F0', 'flash':   32},
    {'name': 'STM32F07x/070xB',         'id': 0x448, 'family': 'F0', 'flash':  128, 'page': 2048},
    {'name': 'STM32F030xC/09x',         'id': 0x442, 'family': 'F0', 'flash':  256, 'page': 2048},

    {'name': 'STM32F10x low-density',   'id': 0x412, 'family': 'F1', 'flash':   32},
    {'name': 'STM32F10x medium-density','id': 0x410, 'family': 'F1', 'flash':  128},
    {'name': 'STM32F10x high-density',  'id': 0x414, 'family': 'F1', 'flash':  512, 'page': 2048},
    {'name': 'STM32F10x XL-density',    'id': 0x430, 'family': 'F1', 'flash': 1024, 'page': 2048},
    {'name': 'STM32F100 low/med-density','id':0x420, 'family': 'F1', 'flash':  128},
    {'name': 'STM32F100 high-density',  'id': 0x428, 'family': 'F1', 'flash':  512, 'page': 2048},
    {'name': 'STM32F105/107',           'id': 0x418, 'family': 'F1', 'flash':  256, 'page': 2048},

    {'name': 'STM32F2xx',               'id': 0x411, 'family': 'F2', 'flash': 1024},

    {'name': 'STM32F301/302x4/6/8/318', 'id': 0x439, 'family': 'F3', 'flash':   64},
    {'name': 'STM32F302/303xB/C/358',   'id': 0x422, 'family': 'F3', 'flash':  256},
    {'name': 'STM32F302/303xD/E/398',   'id': 0x446, 'family': 'F3', 'flash':  512},
    {'name': 'STM32F303x4/6/8/328/334', 'id': 0x438, 'family': 'F3', 'flash':   64},
    {'name': 'STM32F373/378',           'id': 0x432, 'family': 'F3', 'flash':  256},

    {'name': 'STM32F401xB/C',           'id': 0x423, 'family': 'F4', 'flash':  256},
    {'name': 'STM32F401xD/E',           'id': 0x433, 'family': 'F4', 'flash':  512},
    {'name': 'STM32F405/407/415/417',   'id': 0x413, 'family': 'F4', 'flash': 1024},
    {'name': 'STM32F410',               'id': 0x458, 'family': 'F4', 'flash':  128},
    {'name': 'STM32F411',               'id': 0x431, 'family': 'F4', 'flash':  512},
    {'name': 'STM32F412',               'id': 0x441, 'family': 'F4', 'flash': 1024},
    {'name': 'STM32F413/423',           'id': 0x463, 'family': 'F4', 'flash': 1536},
    {'name': 'STM32F42x/43x',           'id': 0x419, 'family': 'F4', 'flash': 2048},
    {'name': 'STM32F446',               'id': 0x421, 'family': 'F4', 'flash':  512},
    {'name': 'STM32F469/479',           'id': 0x434, 'family': 'F4', 'flash': 2048},

    {'name': 'STM32F72x/73x',           'id': 0x452, 'family': 'F7', 'flash':  512},
    {'name': 'STM32F74x/75x',           'id': 0x449, 'family': 'F7', 'flash': 1024},
    {'name': 'STM32F76x/77x',           'id': 0x451, 'family': 'F7', 'flash': 2048},

    {'name': 'STM32G03x/04x',           'id': 0x466, 'family': 'G0', 'flash':   64},
    {'name': 'STM32G05x/061',           'id': 0x456, 'family': 'G0', 'flash':   64},
    {'name': 'STM32G07x/08x',           'id': 0x460, 'family': 'G0', 'flash':  128},
    {'name': 'STM32G0B0/0B1/0C1',       'id': 0x467, 'family': 'G0', 'flash':  512},

    {'name': 'STM32G431/441',           'id': 0x468, 'family': 'G4', 'flash':  128},
    {'name': 'STM32G47x/48x',           'id': 0x469, 'family': 'G4', 'flash':  512, 'page': 0},
    {'name': 'STM32G491/4A1',           'id': 0x479, 'family': 'G4', 'flash':  512},

    {'name': 'STM32H503',               'id': 0x474, 'family': 'H5', 'flash':  128},
    {'name': 'STM32H563/573',           'id': 0x484, 'family': 'H5', 'flash': 2048},

    {'name': 'STM32H72x/73x',           'id': 0x483, 'family': 'H7', 'flash': 1024},
    {'name': 'STM32H74x/75x',           'id': 0x450, 'family': 'H7', 'flash': 2048},
    {'name': 'STM32H7A3/7B3',           'id': 0x480, 'family': 'H7', 'flash': 2048},

    {'name': 'STM32L01x/02x',           'id': 0x457, 'family': 'L0', 'flash':   16},
    {'name': 'STM32L031/041',           'id': 0x425, 'family': 'L0', 'flash':   32},
    {'name': 'STM32L05x/06x',           'id': 0x417, 'family': 'L0', 'flash':   64},
    {'name': 'STM32L07x/08x',           'id': 0x447, 'family': 'L0', 'flash':  192},

    {'name': 'STM32L1 Cat.1',           'id': 0x416, 'family': 'L1', 'flash':  128, 'fsize': 0x1ff8004c},
    {'name': 'STM32L1 Cat.2',           'id': 0x429, 'family': 'L1', 'flash':  128, 'fsize': 0x1ff8004c},
    {'name': 'STM32L1 Cat.3',           'id': 0x427, 'family': 'L1', 'flash':  256},
    {'name': 'STM32L1 Cat.4/Cat.3',     'id': 0x436, 'family': 'L1', 'flash':  384, 'fsize': None},
    {'name': 'STM32L1 Cat.5/Cat.6',     'id': 0x437, 'family': 'L1', 'flash':  512},

    {'name': 'STM32L412/422',           'id': 0x464, 'family': 'L4', 'flash':  128},
    {'name': 'STM32L43x/44x',           'id': 0x435, 'family': 'L4', 'flash':  256},
    {'name': 'STM32L45x/46x',           'id': 0x462, 'family': 'L4', 'flash':  512},
    {'name': 'STM32L47x/48x',           'id': 0x415, 'family': 'L4', 'flash': 1024, 'page': 0},
    {'name': 'STM32L496/4A6',           'id': 0x461, 'family': 'L4', 'flash': 1024, 'page': 0},
    {'name': 'STM32L4Rx/4Sx',           'id': 0x470, 'family': 'L4', 'flash': 2048, 'page': 0},
    {'name': 'STM32L4P5/4Q5',           'id': 0x471, 'family': 'L4', 'flash': 1024, 'page': 0},

    {'name': 'STM32L552/562',           'id': 0x472, 'family': 'L5', 'flash':  512},

    {'name': 'STM32U535/545',           'id': 0x455, 'family': 'U5', 'flash':  512},
    {'name': 'STM32U575/585',           'id': 0x482, 'family': 'U5', 'flash': 2048},
    {'name': 'STM32U595/599/5A9',       'id': 0x481, 'family': 'U5', 'flash': 4096},

    {'name': 'STM32WB10/15',            'id': 0x494, 'family': 'WB', 'flash':  320, 'page': 2048},
    {'name': 'STM32WB30/35/50/55',      'id': 0x495, 'family': 'WB', 'flash': 1024},

    {'name': 'STM32WLE5/WL55',          'id': 0x497, 'family': 'WL', 'flash':  256},
]

# ===================================================================================

if __name__ == "__main__":
    _main()
