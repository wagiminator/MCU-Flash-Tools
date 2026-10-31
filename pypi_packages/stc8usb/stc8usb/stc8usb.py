#!/usr/bin/env python3
# ===================================================================================
# Project:   stc8usb - USB Programming Tool for STC8H8KxxU Microcontrollers
# Version:   v1.0
# Year:      2023
# Author:    Stefan Wagner
# Github:    https://github.com/wagiminator
# License:   MIT License
# ===================================================================================
#
# Description:
# ------------
# Simple Python tool for flashing STC8H8KxxU microcontrollers via USB utilizing the 
# factory built-in embedded USB boot loader ("STC USB Writer", HID, VID:PID 34BF:1001).
# Supported devices: STC8H8K16U, STC8H8K32U, STC8H8K48U, STC8H8K60U, STC8H8K64U
#
# Dependencies:
# -------------
# - pyhidapi
#
# Operating Instructions:
# -----------------------
# You need to install pyhidapi to use stc8usb.
# Install it via "python3 -m pip install hid".
#
# By default Linux will not expose enough permission to access the USB bootloader.
# In order to fix this, open a terminal and run the following commands:
# echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="34bf", ATTR{idProduct}=="1001", MODE="666"' | sudo tee /etc/udev/rules.d/99-STC-ISP.rules
# sudo udevadm control --reload-rules
#
# The bootloader must be started manually for new uploads. To do this, the board must
# first be disconnected from the USB port and all voltage sources. Now press the BOOT
# button and keep it pressed while reconnecting the board to the USB port of your PC.
# The chip now starts in bootloader mode, the BOOT button can be released and new
# firmware can be uploaded via USB. If there is no BOOT button on the board, you have
# to short pin P3.2 to ground while connecting.
#
# Run "python3 stc8usb.py -t 24000000 -f firmware.bin".

# ===================================================================================
# Libraries
# ===================================================================================

import sys
import hid
import argparse

# ===================================================================================
# Main Function
# ===================================================================================

def _main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Minimal command line interface for stc8usb')
    parser.add_argument('-t', '--trim',  type=int, help='set MCU system frequency in Hz')
    parser.add_argument('-e', '--erase', action='store_true', help='perform chip erase (implied with -f)')
    parser.add_argument('-f', '--flash', help='write BIN file to flash')
    args = parser.parse_args(sys.argv[1:])

    # Check frequency
    if args.trim is not None and gettrim(args.trim) is None:
        sys.stderr.write('ERROR: Unsupported frequency, possible values (Hz):\n')
        sys.stderr.write(', '.join(str(f['freq']) for f in sorted(STC_FREQUENCIES, key=lambda f: f['freq'])) + '\n')
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

    # Establish connection to MCU
    try:
        print('Connecting to MCU via USB ...')
        isp = Programmer()
    except Exception as ex:
        sys.stderr.write('ERROR: ' + str(ex) + '!\n')
        sys.exit(1)

    # Performing actions
    try:
        # Connect to and identify MCU
        isp.connect()
        print('SUCCESS: Found %s v%s @ %s.' % (isp.chipname, isp.chipverstr, isp.foscstr))

        # Check if binary fits into flash
        if data is not None and len(data) > isp.flash_size:
            raise Exception('Not enough memory (file: %d bytes, flash: %d bytes)' % (len(data), isp.flash_size))

        # Perform chip erase
        if (args.erase) or (data is not None) or (args.trim is not None):
            print('Performing chip erase ...')
            isp.erase()
            print('SUCCESS: Chip is erased.')

        # Flash binary file
        if data is not None:
            print('Flashing %s to %s ...' % (args.flash, isp.chipname))
            isp.writeflash(0, data)
            print('SUCCESS: %d bytes written.' % len(data))

        # Set frequency
        if args.trim is not None:
            print('Setting frequency ...')
            isp.setfreq(args.trim)
            print('SUCCESS: Frequency set to %s Hz.' % args.trim)

        # Close connection
        isp.disconnect()

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

class Programmer:
    # Init programmer
    def __init__(self):
        # Find programmer
        try:
            self.dev = hid.Device(STC_VID, STC_PID)
        except:
            raise Exception('No STC USB bootloader found (VID:PID %04x:%04x)' % (STC_VID, STC_PID))
        self.is_open = True

    # Close connection   
    def close(self):
        if self.is_open:
            self.is_open = False
            self.dev.close()

    #--------------------------------------------------------------------------------

    # Transmit data block
    def transmit(self, data):
        size   = len(data) + 6
        parity = STC_TX_CODE + (size >> 8) + (size & 0xff)
        for x in range(len(data)):
            parity += data[x]
        block  = [STC_PREFIX, STC_PREFIX ^ 0xff, STC_TX_CODE]
        block += size.to_bytes(2, byteorder='big')
        block += data
        block += (parity & 0xffff).to_bytes(2, byteorder='big')
        block += [STC_SUFFIX]
        block  = self.paddata(bytes(block), STC_HID_SIZE, 0x00)
        self.dev.write(block)

    # Receive and check data block
    def receive(self, timeout=None):
        reply = self.dev.read(STC_HID_SIZE, STC_TIMEOUT if timeout is None else timeout)
        if len(reply) != STC_HID_SIZE:
            raise Exception('No response from device')
        if reply[0] != STC_PREFIX or reply[1] != (STC_PREFIX ^ 0xff) or reply[2] != STC_RX_CODE:
            raise Exception('Invalid data prefix from device')
        size = int.from_bytes(reply[3:5], byteorder='big')
        if size < 7 or size + 2 > len(reply):
            raise Exception('Invalid data size from device')
        data   = reply[5:size-1]
        check  = int.from_bytes(reply[size-1:size+1], byteorder='big')
        parity = STC_RX_CODE + (size >> 8) + (size & 0xff) + sum(data)
        if (parity & 0xffff) != check or reply[size+1] != STC_SUFFIX:
            raise Exception('Invalid data checksum from device')
        return data

    #--------------------------------------------------------------------------------

    # Connect to and identify MCU
    def connect(self):
        self.transmit([STC_CMD_INIT])
        reply = self.receive()
        if len(reply) < 23 or reply[0] != STC_RPL_INFO:
            raise Exception('Invalid response from MCU')

        # Get chip ID
        self.chipid = int.from_bytes(reply[20:22], byteorder='big')
        
        # Find chip in dictionary
        self.device = None
        for d in STC_DEVICES:
            if d['id'] == self.chipid:
                self.device = d
                break
        if self.device is None:
            raise Exception('Unsupported chip (ID: 0x%04x)' % self.chipid)
        self.chipname   = self.device['name']
        self.flash_size = self.device['flash_size']

        # Get chip version
        self.chipversion  = reply[17]
        self.chipverstr   = '%d.%d.%d%c' % (reply[17] >> 4, reply[17] & 0x0f, \
                                            reply[22] & 0x0f, reply[18])

        # Get USER-IRC oscillator frequency
        self.fosc = int.from_bytes(reply[1:5], byteorder='big')
        if self.fosc == 0xffffffff:
            self.foscstr = 'untrimmed frequency'
        else:
            self.foscstr = str(self.fosc) + ' Hz'

        # Get option bytes (MCS register values)
        self.options = reply[9:12] + reply[15:17]
        
        # Set BAUD (dummy)
        self.transmit([STC_CMD_BAUD_SET, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x80])
        reply = self.receive()
        if len(reply) < 1 or reply[0] != STC_CMD_BAUD_SET:
            raise Exception('Failed to prepare MCU')
        self.transmit([STC_CMD_BAUD_CHECK, 0x00, 0x00, 0x5a, 0xa5])
        reply = self.receive()
        if len(reply) == 1 and reply[0] == STC_RPL_LOCKED:
            raise Exception('MCU is locked')
        if len(reply) < 1 or reply[0] != STC_CMD_BAUD_CHECK:
            raise Exception('Failed to prepare MCU')

    # Disconnect from MCU
    def disconnect(self):
        self.transmit([STC_CMD_EXIT])
        self.close()

    #--------------------------------------------------------------------------------

    # Erase flash
    def erase(self):
        self.transmit([STC_CMD_ERASE, 0, 0, STC_BREAK, STC_BREAK ^ 0xff])
        reply = self.receive(STC_ERASE_TIMEOUT)
        if len(reply) < 1 or reply[0] != STC_CMD_ERASE:
            raise Exception('Failed to erase flash')

    # Write data to flash
    def writeflash(self, addr, data):
        if len(data) > (self.flash_size - addr):
            raise Exception('Not enough memory')
        data = self.paddata(bytes(data), STC_PAGE_SIZE, 0xff)
        cmd = STC_CMD_WRITE
        for offset in range(0, len(data), STC_PAGE_SIZE):
            block  = [cmd]
            block += (addr + offset).to_bytes(2, byteorder='big')
            block += [STC_BREAK, STC_BREAK ^ 0xff]
            block += data[offset:offset + STC_PAGE_SIZE]
            self.transmit(block)
            reply = self.receive()
            if len(reply) < 1 or reply[0] != STC_CMD_WRITE_CONT or (len(reply) >= 2 and reply[1] != STC_OK):
                raise Exception('Failed to write to address 0x%04x' % (addr + offset))
            cmd = STC_CMD_WRITE_CONT

    # Set frequency by writing option bytes (keeps the MCS register values of the MCU)
    def setfreq(self, freq):
        trim = gettrim(freq)
        if trim is None:
            raise Exception('Unsupported frequency')
        block  = [STC_CMD_OPTIONS, 0, 0, STC_BREAK, STC_BREAK ^ 0xff]
        block += STC_BLOCK_OPTIONS1
        block += freq.to_bytes(4, byteorder='big')
        block += trim
        block += [0xff, self.options[0], 0xff, 0xff, STC_BLOCK_OPTIONS2[4]]
        block += list(self.options[1:5])
        self.transmit(block)
        reply = self.receive()
        if len(reply) < 1 or reply[0] != STC_CMD_OPTIONS or (len(reply) >= 2 and reply[1] != STC_OK):
            raise Exception('Failed to write option bytes')

    # Pad data
    def paddata(self, data, pagesize, filler):
        if (len(data) % pagesize) > 0:
            data += bytes([filler]) * (pagesize - (len(data) % pagesize))
        return data

# Get trim values for frequency
def gettrim(freq):
    for f in STC_FREQUENCIES:
        if f['freq'] == freq:
            return f['trim']
    return None

# ===================================================================================
# Device Constants
# ===================================================================================

STC_VID            = 0x34bf
STC_PID            = 0x1001
STC_HID_SIZE       = 64
STC_PAGE_SIZE      = 128
STC_TIMEOUT        = 1000
STC_ERASE_TIMEOUT  = 10000

STC_PREFIX         = 0x46
STC_BREAK          = 0x5a
STC_SUFFIX         = 0x16
STC_TX_CODE        = 0x6a
STC_RX_CODE        = 0x68
STC_RPL_INFO       = 0x50
STC_RPL_LOCKED     = 0x0f
STC_OK             = 0x54

STC_CMD_INIT       = 0x00
STC_CMD_BAUD_SET   = 0x01
STC_CMD_BAUD_CHECK = 0x05
STC_CMD_ERASE      = 0x03
STC_CMD_OPTIONS    = 0x04
STC_CMD_WRITE      = 0x32
STC_CMD_WRITE_CONT = 0x02
STC_CMD_EXIT       = 0xff

STC_BLOCK_OPTIONS1 = [0xff, 0xff, 0xff, 0x00, 0xff, 0xff, 0x00, 0xff, 
                      0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 
                      0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x00, 0xff]
STC_BLOCK_OPTIONS2 = [0xff, 0xff, 0xff, 0xff, 0x3e, 0xbf, 0xaf, 0xf7, 0xfe]

# ===================================================================================
# Device Dictionary
# ===================================================================================

STC_DEVICES = [
    {'name': 'STC8H8K16U', 'id': 0xF781, 'flash_size':  16384},
    {'name': 'STC8H8K32U', 'id': 0xF782, 'flash_size':  32768},
    {'name': 'STC8H8K60U', 'id': 0xF783, 'flash_size':  61440},
    {'name': 'STC8H8K64U', 'id': 0xF784, 'flash_size':  65024},
    {'name': 'STC8H8K48U', 'id': 0xF785, 'flash_size':  49152}
]

STC_FREQUENCIES = [
    {'freq':   250000, 'trim': [0x48, 0x20, 96]},
    {'freq':   500000, 'trim': [0x48, 0x20, 48]},
    {'freq':  1000000, 'trim': [0x48, 0x20, 24]},
    {'freq':  2000000, 'trim': [0x48, 0x20, 12]},
    {'freq':  3000000, 'trim': [0x48, 0x20,  8]},
    {'freq':  4000000, 'trim': [0x48, 0x20,  6]},
    {'freq':  5000000, 'trim': [0x73, 0x30,  8]},
    {'freq':  6000000, 'trim': [0x48, 0x20,  4]},
    {'freq':  8000000, 'trim': [0x48, 0x20,  3]},
    {'freq': 10000000, 'trim': [0x73, 0x30,  4]},
    {'freq': 12000000, 'trim': [0x48, 0x20,  2]},
    {'freq': 16000000, 'trim': [0xc6, 0x30,  3]},
    {'freq': 20000000, 'trim': [0x73, 0x30,  2]},
    {'freq': 24000000, 'trim': [0x48, 0x20,  1]},
    {'freq': 27000000, 'trim': [0x7a, 0x20,  1]},
    {'freq': 30000000, 'trim': [0xb1, 0x20,  1]},
    {'freq': 35000000, 'trim': [0x44, 0x30,  1]},
    {'freq': 40000000, 'trim': [0x73, 0x30,  1]},
    {'freq': 48000000, 'trim': [0xc6, 0x30,  1]},

    {'freq':  1382400, 'trim': [0x28, 0x20, 16]},
    {'freq':  2764800, 'trim': [0x28, 0x20,  8]},
    {'freq':  5529600, 'trim': [0x28, 0x20,  4]},
    {'freq': 11059200, 'trim': [0x28, 0x20,  2]},
    {'freq': 18432000, 'trim': [0x56, 0x30,  2]},
    {'freq': 22118400, 'trim': [0x28, 0x20,  1]},
    {'freq': 33177600, 'trim': [0xe9, 0x20,  1]},
    {'freq': 36864000, 'trim': [0x56, 0x30,  1]},
    {'freq': 44236800, 'trim': [0x9f, 0x30,  1]}
]

# ===================================================================================

if __name__ == "__main__":
    _main()
