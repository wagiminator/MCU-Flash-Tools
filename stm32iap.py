#!/usr/bin/env python3
# ===================================================================================
# Project:   stm32iap - IAP Programming Tool for STM32G03x/04x Microcontrollers
# Version:   v0.1
# Year:      2023
# Author:    Stefan Wagner
# Github:    https://github.com/wagiminator
# License:   MIT License
# ===================================================================================
#
# Description:
# ------------
# Python tool for flashing STM32G03x/04x (and maybe other STM32) microcontrollers
# via USB-to-serial converter utilizing the factory built-in embedded boot loader.
# !!! THIS TOOL IS IN AN EARLY STAGE OF DEVELOPMENT !!!
#
# Dependencies:
# -------------
# - pyserial
#
# Operating Instructions:
# -----------------------
# You need to install PySerial to use stm32iap.
# Install it via "python3 -m pip install pyserial".
# You may need to install a driver for your USB-to-serial converter.
#
# On the STM32, the BOOT0 pin is disabled by default. As soon as the chip is brand 
# new and/or the main flash memory is deleted, this is not a problem, the embedded 
# bootloader will automatically start. Using this stm32iap tool will automatically 
# activate the BOOT0 pin so that it can also be used in the following. However, if 
# the chip has already been written to before using a different software tool, it 
# is likely that the bootloader can no longer be activated via the BOOT0 pin. In 
# this case, the bit nBOOT_SEL in the User Option Bytes must be deleted (set to 0) 
# using an SWD programmer (e.g. ST-Link) and appropriate software.
#
# Connect your USB-to-serial converter to your MCU:
# USB2SERIAL      STM32G03x/04x
#        RXD <--- PA2 or PA9
#        TXD ---> PA3 or PA10
#        VCC ---> VCC
#        GND ---> GND
#
# Set your MCU to boot mode by using ONE of the following methods:
# - Disconnect your USB-to-serial converter, pull BOOT0 pin (PA14) to VCC (or press
#   and hold the BOOT button, if your board has one), then connect the converter to
#   your USB port. BOOT0 pin (or BOOT button) can be released now.
# - Connect your USB-to-serial converter to your USB port. Pull BOOT0 pin (PA14)
#   to VCC, then pull nRST shortly to GND (or press and hold the BOOT button,
#   then press and release the RESET button and then release the BOOT button, if
#   your board has them).
#
# Run "python3 stm32iap.py -f firmware.bin".

# If the PID/VID of the USB-to-Serial converter is known, it can be defined here,
# which can make the auto-detection a lot faster. If not, comment out or delete.
#ST_VID  = '1A86'
#ST_PID  = '7523'

# Define BAUD rate here, range: 1200 - 115200, default: 115200
ST_BAUD = 115200

# Libraries
import sys
import argparse
import serial
from serial import Serial
from serial.tools.list_ports import comports

# ===================================================================================
# Main Function
# ===================================================================================

def _main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Minimal command line interface for STM32 IAP')
    parser.add_argument('-u', '--unlock',   action='store_true', help='unlock chip (remove read protection)')
    parser.add_argument('-l', '--lock',     action='store_true', help='lock chip (set read protection)')
    parser.add_argument('-e', '--erase',    action='store_true', help='perform a chip erase (implied with -f)')
    parser.add_argument('-o', '--rstoption',action='store_true', help='reset option bytes')
    parser.add_argument('-f', '--flash',    help='write BIN file to flash and verify')
    args = parser.parse_args(sys.argv[1:])

    # Check arguments
    if not any( (args.rstoption, args.unlock, args.lock, args.erase, args.flash) ):
        print('No arguments - no action!')
        sys.exit(0)

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
        if isp.pid == ST_CHIP_PID:
            print('SUCCESS: Found STM32G03x/04x with bootloader v' + isp.verstr + '.')
        else:
            print('WARNING: Chip with PID 0x%04x is not an STM32G03x/04x!' % isp.pid)

        # Unlock chip
        if args.unlock:
            print('Unlocking chip ...')
            isp.unlock()
            print('SUCCESS: Chip is unlocked.')
            print('INFO: Other options are ignored!')
            isp.close()
            print('DONE.')
            sys.exit(0)

        # Read option bytes and check, if chip is locked
        print('Reading OPTION bytes ...')
        isp.readoption()
        print('SUCCESS: User OPTION bytes: 0x%08x.' % isp.useroption)

        # Perform chip erase
        if (args.erase) or (args.flash is not None):
            print('Performing chip erase ...')
            isp.erase()
            print('SUCCESS: Chip is erased.')

        # Flash binary file
        if args.flash is not None:
            print('Flashing', args.flash, 'to MCU ...')
            with open(args.flash, 'rb') as f: data = f.read()
            isp.writeflash(ST_CODE_ADDR, data)
            print('Verifying ...')
            isp.verifyflash(ST_CODE_ADDR, data)
            print('SUCCESS:', len(data), 'bytes written and verified.')

        # Manipulate OPTION bytes
        if isp.pid == ST_CHIP_PID and any( (args.rstoption, args.lock, isp.checkbootpin()) ):
            if args.rstoption:
                print('Setting OPTION bytes to default values ...')
                isp.resetoption()
            if args.lock:
                print('Setting read protection in OPTION bytes...')
                isp.lock()
            if isp.checkbootpin():
                print('Enabling BOOT0 pin in OPTION bytes ...')
                isp.enablebootpin()
            print('Writing OPTION bytes ...')
            isp.writeoption()
            print('SUCCESS: OPTION bytes written.')
            isp.close()
        else:
            isp.run()

    except Exception as ex:
        sys.stderr.write('ERROR: ' + str(ex) + '!\n')
        isp.close()
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
        super().__init__(baudrate = ST_BAUD, parity = serial.PARITY_EVEN, timeout = 1)
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
                self.reset_input_buffer()
                self.write([ST_SYNCH])
                if not self.checkreply():
                    self.close()
                    continue
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
        self.write(stream)
        self.write([parity])
        if not self.checkreply():
            raise Exception('Failed to send address')

    # Check if device acknowledged
    def checkreply(self):
        reply = self.read(1)
        return (len(reply) == 1 and reply[0] == ST_REPLY_ACK)

    #--------------------------------------------------------------------------------

    # Unlock (clear) chip and reset
    def unlock(self):
        self.sendcommand(ST_CMD_R_UNLOCK)
        if not self.checkreply():
            raise Exception('Failed to unlock chip')

    # Read info stream
    def readinfostream(self, command):
        self.sendcommand(command)
        size = self.read(1)[0]
        stream = self.read(size + 1)
        if not self.checkreply():
            raise Exception('Failed to read info')
        return stream

    # Get chip info
    def readinfo(self):
        self.ver    = self.readinfostream(ST_CMD_GET)[0]
        self.verstr = '%x.%x' % (self.ver >> 4, self.ver & 7)
        self.pid    = int.from_bytes(self.readinfostream(ST_CMD_PID), byteorder='big')

    # Read flash size in KB
    def readflashsize(self):
        return int.from_bytes(self.readflash(ST_FSIZE_ADDR, 2), byteorder='little')

    # Read OPTION bytes
    def readoption(self):
        try:
            self.option = list(self.readflash(ST_OPTION_ADDR, 8))
        except:
            raise Exception('Chip is locked')
        self.useroption = int.from_bytes(self.option[:4], byteorder='little')

    # Write OPTION bytes
    def writeoption(self):
        self.writeflash(ST_OPTION_ADDR, self.option)

    # Reset OPTION bytes
    def resetoption(self):
        self.option = list(ST_OPTION_DEFAULT)

    # Set read protection in OPTION bytes
    def lock(self):
        self.option[0] = 0x55
        self.option[4] = 0xaa

    # Enable BOOT0 pin (nBOOT_SEL = 0)
    def enablebootpin(self):
        self.option[3] = 0xde
        self.option[7] = 0x21

    # Disable BOOT0 pin (nBOOT_SEL = 1)
    def disablebootpin(self):
        self.option[3] = 0xdf
        self.option[7] = 0x20

    # Check if BOOT0 pin ist disabled
    def checkbootpin(self):
        return ((self.option[3] & 0x01) == 0x01)

    #--------------------------------------------------------------------------------

    # Erase whole chip
    def erase(self):
        self.sendcommand(ST_CMD_ERASE)
        self.write(b'\xff\xff\x00')
        if not self.checkreply():
            raise Exception('Failed to erase chip')

    # Read flash
    def readflash(self, addr, size):
        data = bytes()
        while size > 0:
            blocksize = size
            if blocksize > ST_PAGE_SIZE: blocksize = ST_PAGE_SIZE
            self.sendcommand(ST_CMD_READ)
            self.sendaddress(addr)
            self.sendcommand(blocksize - 1)
            data += self.read(blocksize)
            addr += blocksize
            size -= blocksize
        return data

    # Write to flash
    def writeflash(self, addr, data):
        size = len(data)
        while size > 0:
            blocksize = size
            if blocksize > ST_PAGE_SIZE: blocksize = ST_PAGE_SIZE
            block = data[:blocksize]
            parity = blocksize - 1
            for x in range(blocksize):
                parity ^= block[x]
            self.sendcommand(ST_CMD_WRITE)
            self.sendaddress(addr)
            self.write([blocksize - 1])
            self.write(block)
            self.write([parity])
            if not self.checkreply():
                raise Exception('Failed to write to address 0x%08x' % addr)
            data  = data[blocksize:]
            addr += blocksize
            size -= blocksize

    # Verify flash
    def verifyflash(self, addr, data):
        flash = self.readflash(addr, len(data))
        if set(flash) != set(data):
            raise Exception('Verification failed')

    # Pad data
    def paddata(self, data, pagesize):
        if (len(data) % pagesize) > 0:
            data += b'\xff' * (pagesize - (len(data) % pagesize))
        return data

    #--------------------------------------------------------------------------------

    # Jump to address
    def gotoaddress(self, addr):
        self.sendcommand(ST_CMD_GO)
        self.sendaddress(addr)

    # Start firmware
    def run(self):
        self.gotoaddress(ST_CODE_ADDR)

# ===================================================================================
# Device Constants
# ===================================================================================

# Device and Memory constants
ST_CHIP_PID     = 0x466
ST_PAGE_SIZE    = 256
ST_FLASH_ADDR   = 0x08000000
ST_CODE_ADDR    = 0x08000000
ST_SRAM_ADDR    = 0x20000000
ST_BOOT_ADDR    = 0x1fff0000
ST_OTP_ADDR     = 0x1fff7000
ST_ENG_ADDR     = 0x1fff7500
ST_OPTION_ADDR  = 0x1fff7800
ST_FSIZE_ADDR   = 0x1fff75e0

# Command codes
ST_CMD_GET      = 0x00
ST_CMD_VER      = 0x01
ST_CMD_PID      = 0x02
ST_CMD_READ     = 0x11
ST_CMD_WRITE    = 0x31
ST_CMD_ERASE    = 0x44
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

# Default user option bytes
ST_OPTION_DEFAULT = b'\xaa\xe1\xff\xdf\x55\x1e\x00\x20'

# ===================================================================================

if __name__ == "__main__":
    _main()
