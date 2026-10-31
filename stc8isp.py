#!/usr/bin/env python3
# ===================================================================================
# Project:   stc8isp - Programming Tool for STC8G/8H Microcontrollers
# Version:   v1.0
# Year:      2023
# Author:    Stefan Wagner
# Github:    https://github.com/wagiminator
# License:   MIT License
# ===================================================================================
#
# Description:
# ------------
# Simple Python tool for flashing STC8G/8H microcontrollers via USB-to-serial
# converter utilizing the factory built-in embedded boot loader.
# Supported devices (bootloader v7.2 and later):
# - STC8G1K, STC8G2K
# - STC8H1K (incl. T versions), STC8H2K/4K TL/TLCD, STC8H3K, STC8H4K TLR/LCD, STC8H8K
# - STC8A8K/STC8A2K D4
#
# References:
# -----------
# - stcgal: https://github.com/grigorig/stcgal
#
# Dependencies:
# -------------
# - pyserial
#
# Operating Instructions:
# -----------------------
# You need to install PySerial to use stc8isp.
# Install it via "python3 -m pip install pyserial".
# You may need to install a driver for your USB-to-serial converter.
#
# Connect your USB-to-serial converter to your MCU:
# USB2SERIAL         STC8G/8H
#        VCC --/ --> VCC        interruptible (for power cycle)
#        RXD --|R|-- P3.1       resistor (100R - 1000R)
#        TXD --|<|-- P3.0       diode (e.g. 1N5819)
#        GND ------- GND        common ground
#
# Run "python3 stc8isp.py -p /dev/ttyUSB0 -t 24000000 -f firmware.bin".
# Perform a power cycle of your MCU (reconnect to power) when prompted.


# ===================================================================================
# Software Settings
# ===================================================================================

# If the PID/VID of the USB-to-Serial converter is known, it can be defined here.
# The specified COM port is then ignored, and all ports are automatically searched
# for the device. Comment the lines to ignore PID/VID.
#STC_VID = '1A86'
#STC_PID = '7523'

# Define the default COM port here. This will be used if no VID/PID is defined and
# no COM port is specified within the command line arguments.
STC_PORT = '/dev/ttyUSB0'

# Define the default BAUD rates here. The minimum BAUD rate is used to calibrate the
# oscillator and should be low to achieve higher accuracy. The maximum BAUD rate is
# used to transfer the firmware and should be high to achieve higher speed.
STC_BAUD_MIN = 2400
STC_BAUD_MAX = 115200

# Define time to wait for power cycle in seconds, default: 10
STC_WAIT = 10

# Define minimum and maximum IRC frequency in Hz, that can be specified by the
# respective command line argument. Expanding the limit values can lead to problems!
STC_FCPU_MIN =   128000
STC_FCPU_MAX = 36000000

# Maximum allowed deviation of the trimmed IRC frequency (0.02 = 2%)
STC_TRIM_TOLERANCE = 0.02

# ===================================================================================
# Libraries
# ===================================================================================

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
    parser = argparse.ArgumentParser(description='Minimal command line interface for stc8isp')
    parser.add_argument('-p', '--port',  default=STC_PORT, help='set COM port')
    parser.add_argument('-t', '--trim',  type=int, help='trim IRC to frequency in Hz')
    parser.add_argument('-e', '--erase', action='store_true', help='perform chip erase (implied with -f)')
    parser.add_argument('-f', '--flash', help='write BIN file to flash')
    args = parser.parse_args(sys.argv[1:])

    # Checking command line arguments
    if (args.trim is not None) and (args.trim < STC_FCPU_MIN or args.trim > STC_FCPU_MAX):
        sys.stderr.write('ERROR: Trim value out of range (%d - %d)!\n' % (STC_FCPU_MIN, STC_FCPU_MAX))
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

    # Establish connection to USB-to-serial converter
    try:
        print('Connecting to USB-to-serial converter ...')
        isp = Programmer(args.port)
        print('SUCCESS: Connected via', isp.port + '.')
    except Exception as ex:
        sys.stderr.write('ERROR: ' + str(ex) + '!\n')
        sys.exit(1)

    # Performing actions
    try:
        # Connect to and identify MCU
        print('Waiting for MCU power cycle ...')
        isp.connect()
        print('SUCCESS: Found %s v%s @ %s.' % (isp.chipname, isp.chipverstr, isp.foscstr))

        # Check if binary fits into flash
        if data is not None and len(data) > isp.flash_size:
            raise Exception('Not enough memory (file: %d bytes, flash: %d bytes)' % (len(data), isp.flash_size))

        # Calibrate user IRC oscillator frequency
        if args.trim is not None:
            print('Calibrating user IRC frequency to %d Hz ...' % args.trim)
            isp.trim(args.trim)
            print('SUCCESS: Trimmed to %d Hz (error %.2f%%).' % (isp.osc_freq, 100 * isp.osc_error))

        # Switch BAUD rate
        print('Switching BAUD rate ...')
        isp.setbaud(STC_BAUD_MAX)
        print('SUCCESS: BAUD rate set to %d.' % STC_BAUD_MAX)

        # Perform chip erase
        if (args.erase) or (data is not None) or (args.trim is not None):
            print('Performing chip erase ...')
            isp.erase()
            print('SUCCESS: Chip is erased.')

        # Flash binary file
        if data is not None:
            print('Flashing %s to MCU ...' % args.flash)
            isp.writeflash(0, data)
            print('SUCCESS: %d bytes written.' % len(data))

        # Write option bytes
        if args.trim is not None:
            print('Writing option bytes ...')
            isp.writeoptions()
            print('SUCCESS: Option bytes written.')

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

class Programmer(Serial):
    def __init__(self, port=STC_PORT, baud=STC_BAUD_MIN):
        # Data frame: 1 start bit, 8 data bit, 1 parity bit set to even, 1 stop bit
        super().__init__(baudrate = baud, parity = serial.PARITY_EVEN, timeout = 0.01)

        # Use COM port to define device
        if 'STC_VID' not in globals() or 'STC_PID' not in globals():
            self.port = port

        # Use VID/PID to find device
        else:
            for p in comports():
                if (STC_VID in p.hwid) and (STC_PID in p.hwid):
                    self.port = p.device
                    break
            else:
                raise Exception('No USB-to-serial converter with VID/PID %s/%s found' % (STC_VID, STC_PID))

        # Open connection
        try:
            self.open()
        except:
            raise Exception('Failed to connect to USB-to-serial converter')

    #--------------------------------------------------------------------------------

    # Transmit data block (followed by optional trim pulse characters)
    def transmit(self, data, epilogue=0):
        size   = len(data) + 6
        parity = STC_TX_CODE + (size >> 8) + (size & 0xff)
        for x in range(len(data)):
            parity += data[x]
        block  = [STC_PREFIX, STC_PREFIX ^ 0xff, STC_TX_CODE]
        block += size.to_bytes(2, byteorder='big')
        block += data
        block += (parity & 0xffff).to_bytes(2, byteorder='big')
        block += [STC_SUFFIX]
        block += [STC_CHAR_TRIM] * epilogue
        self.write(bytes(block))

    # Receive and check data block
    def receive(self, timeout=None):
        if timeout is not None:
            self.timeout = timeout
        reply = self.read(1)
        if len(reply) == 0:
            return None
        self.timeout = max(self.timeout, STC_TIMEOUT)
        # Some bootloaders omit the frame start (see stcgal)
        if reply[0] == STC_PREFIX:
            reply = self.read(2)
        elif reply[0] == STC_RX_CODE:
            reply = bytes([STC_PREFIX ^ 0xff, STC_RX_CODE])
        else:
            return None
        if len(reply) != 2 or reply[0] != (STC_PREFIX ^ 0xff) or reply[1] != STC_RX_CODE:
            raise Exception('Invalid data prefix from MCU')
        size = int.from_bytes(self.read(2), byteorder='big')
        if size < 7:
            raise Exception('Invalid data size from MCU')
        data = self.read(size - 6)
        if len(data) != size - 6:
            raise Exception('Missing data from MCU')
        check  = int.from_bytes(self.read(2), byteorder='big')
        suffix = self.read(1)
        if len(suffix) != 1 or suffix[0] != STC_SUFFIX:
            raise Exception('Invalid data suffix from MCU')
        parity = STC_RX_CODE + (size >> 8) + (size & 0xff)
        for x in range(len(data)):
            parity += data[x]
        if (parity & 0xffff) != check:
            raise Exception('Invalid data checksum from MCU')
        return data

    # Transmit command and check reply
    def command(self, data, error, timeout=None, ok=False):
        self.transmit(data)
        reply = self.receive(STC_TIMEOUT if timeout is None else timeout)
        self.timeout = STC_TIMEOUT
        if reply is None or len(reply) < 1 or reply[0] != data[0] or (ok and (len(reply) < 2 or reply[1] != STC_OK)):
            raise Exception(error)
        return reply

    # Repeat sending sync character until reply or timeout
    def pulse(self, char, pulsetime=0.01, timeout=10):
        counter = timeout
        while self.in_waiting == 0:
            self.write([char])
            time.sleep(pulsetime)
            counter -= pulsetime
            if counter <= 0:
                raise Exception('Timeout waiting for response')

    #--------------------------------------------------------------------------------

    # Connect to and identify MCU
    def connect(self):
        # Ping MCU, wait for power cycle, read info bytes
        self.reset_input_buffer()
        deadline = time.time() + STC_WAIT
        reply = None
        while reply is None:
            if time.time() > deadline:
                raise Exception('Timeout, failed to connect to MCU')
            self.write([STC_CHAR_SYNC])
            reply = self.receive(STC_SYNC_TIMEOUT)
        self.timeout = STC_TIMEOUT
        if len(reply) < 42 or reply[0] != STC_RPL_INFO:
            raise Exception('Invalid response from MCU')

        # Get chip ID
        self.chipid = int.from_bytes(reply[20:22], byteorder='big')

        # Find chip in dictionary
        self.device = None
        for d in DEVICES:
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

        # Get ISP-IRC and USER-IRC oscillator frequencies
        self.fisp = int.from_bytes(reply[13:15], byteorder='big') * self.baudrate
        self.fosc = int.from_bytes(reply[1:5], byteorder='big')
        if self.fosc == 0xffffffff:
            self.foscstr = 'untrimmed frequency'
        else:
            self.foscstr = str(self.fosc) + ' Hz'

        # Get option bytes (MCS register values)
        self.options = reply[9:12] + reply[15:17]

    # Disconnect from MCU and USB-to-serial converter
    def disconnect(self):
        self.transmit([STC_CMD_EXIT])
        self.close()

    #--------------------------------------------------------------------------------

    # Set and calibrate USER-IRC oscillator frequency
    def trim(self, freq):
        if self.device['cal'] == 'stc8d':
            self.trim_stc8d(freq)
        else:
            self.trim_stc8g(freq)
        if abs(self.osc_error) > STC_TRIM_TOLERANCE:
            raise Exception('Frequency trimming failed (%d Hz, error %.2f%%)' % (self.osc_freq, 100 * self.osc_error))

    # Send trim challenge and receive frequency counts
    def trimchallenge(self, block, char, epilogue=0):
        self.transmit(block, epilogue)
        self.pulse(char)
        reply = self.receive()
        if reply is None or len(reply) < 2 or reply[0] != STC_CMD_TRIM or len(reply) < 2 + 2 * reply[1]:
            raise Exception('Invalid response from MCU')
        return [int.from_bytes(reply[2*x+2:2*x+4], byteorder='big') * self.baudrate for x in range(reply[1])]

    # Calibration for STC8G and STC8H1K
    def trim_stc8g(self, freq):
        # Get global trim values
        freqs = self.trimchallenge(STC_BLOCK_TRIM, STC_CHAR_TRIM)
        freq1, freq2, freq3, freq4, freq5 = freqs[:5]

        # Calculate mean trim value for specified frequency
        self.osc_div = 1
        while freq * self.osc_div < freq1: self.osc_div += 1
        if freq * self.osc_div < freq5:
            self.osc_trimx = round( (freq * self.osc_div - freq1) *
                (STC_BLOCK_TRIM[4] - STC_BLOCK_TRIM[2]) / (freq2 - freq1) + STC_BLOCK_TRIM[2] )
            self.osc_bandx = STC_BLOCK_TRIM[3]
        else:
            self.osc_trimx = round( (freq * self.osc_div - freq3) *
                (STC_BLOCK_TRIM[8] - STC_BLOCK_TRIM[6]) / (freq4 - freq3) + STC_BLOCK_TRIM[6] )
            self.osc_bandx = STC_BLOCK_TRIM[7]
        self.osc_trimx = min(max(self.osc_trimx, 2), 252)

        # Get fine tuned trim values for specified frequency
        count = 24
        block = [0x00, count]
        for x in range(count):
            block += [self.osc_trimx - 2 + (x>>2), self.osc_bandx + (x & 0x03)]
        freqs = self.trimchallenge(block, STC_CHAR_TRIM)

        # Find optimal trim value
        best = sys.maxsize
        for x in range(min(count, len(freqs))):
            if abs(freq * self.osc_div - freqs[x]) < best:
                best = abs(freq * self.osc_div - freqs[x])
                self.osc_freq  = round(freqs[x] / self.osc_div)
                self.osc_trim  = block[2*x+2]
                self.osc_band  = block[2*x+3]
        self.osc_error = (self.osc_freq - freq) / freq

    # Calibration for STC8H (except STC8H1K) and STC8A D4 (according to stcgal)
    def trim_stc8d(self, freq):
        # Round 1: four ranges with trim values 0x00 and 0xff each
        block = [0x00, 0x08]
        for band in (0x00, 0x10, 0x20, 0x30):
            block += [0x00, band, 0xff, band]
        freqs = self.trimchallenge(block, STC_CHAR_TRIM_D)

        # Select range, divider and mean trim value
        self.osc_trimx = None
        for self.osc_div in range(1, 6):
            target = freq * self.osc_div
            for x in range(len(freqs) >> 1):
                freq_a, freq_b = freqs[2*x], freqs[2*x+1]
                trim_a, trim_b = block[4*x+2], block[4*x+4]
                if freq_a <= target <= freq_b and freq_b > freq_a:
                    trimx = round((target - freq_a) * (trim_b - trim_a) / (freq_b - freq_a) + trim_a)
                    if 6 <= trimx <= 250:
                        self.osc_trimx = trimx
                        self.osc_bandx = block[4*x+5]
                    break
            if self.osc_trimx is not None:
                break
        if self.osc_trimx is None:
            raise Exception('Frequency trimming failed')

        # Round 2: fine tuning around the mean trim value
        block = [0x00, 0x0c]
        for x in range(-6, 6):
            block += [self.osc_trimx + x, self.osc_bandx]
        freqs = self.trimchallenge(block, STC_CHAR_TRIM_D)

        # Find optimal trim value
        best = sys.maxsize
        for x in range(min(12, len(freqs))):
            if abs(freq * self.osc_div - freqs[x]) < best:
                best = abs(freq * self.osc_div - freqs[x])
                self.osc_freq  = round(freqs[x] / self.osc_div)
                self.osc_trim  = block[2*x+2]
                self.osc_band  = block[2*x+3]
        self.osc_error = (self.osc_freq - freq) / freq

    # Set/switch BAUD rate
    def setbaud(self, baud=STC_BAUD_MAX):
        # Set BAUD rate
        count  = round(65536 - (self.fisp / (4 * baud)))
        if not 0 < count < 65536:
            raise Exception('BAUD rate %d not possible' % baud)
        block  = [STC_CMD_BAUD_SET, self.fosc & 0xff, 0x40]
        block += count.to_bytes(2, byteorder='big')
        block += [0x00, 0x00, 0x97]
        self.command(block, 'Failed to set BAUD rate')
        self.baudrate = baud
        time.sleep(0.01)

        # Check BAUD rate
        if self.chipversion < 0x72:
            self.transmit([STC_CMD_BAUD_CHECK])
        else:
            self.transmit([STC_CMD_BAUD_CHECK, 0, 0, STC_BREAK, STC_BREAK ^ 0xff])
        reply = self.receive()
        if reply is not None and len(reply) == 1 and reply[0] == STC_RPL_LOCKED:
            raise Exception('MCU is locked')
        if reply is None or reply[0] != STC_CMD_BAUD_CHECK:
            raise Exception('Failed to check BAUD rate')

    #--------------------------------------------------------------------------------

    # Erase flash
    def erase(self):
        reply = self.command([STC_CMD_ERASE, 0, 0, STC_BREAK, STC_BREAK ^ 0xff],
                             'Failed to erase flash', STC_ERASE_TIMEOUT)
        self.uid = reply[1:8] if len(reply) >= 8 else None

    # Write data to flash
    def writeflash(self, addr, data):
        if len(data) > (self.flash_size - addr):
            raise Exception('Not enough memory')
        data = bytes(data)
        cmd = STC_CMD_WRITE
        for offset in range(0, len(data), STC_PAGE_SIZE):
            block = data[offset:offset + STC_PAGE_SIZE]
            block += b'\xff' * (STC_PAGE_SIZE - len(block))
            packet  = [cmd]
            packet += (addr + offset).to_bytes(2, byteorder='big')
            packet += [STC_BREAK, STC_BREAK ^ 0xff]
            packet += block
            self.transmit(packet)
            reply = self.receive()
            if reply is None or len(reply) < 2 or reply[0] != STC_CMD_WRITE_CONT or reply[1] != STC_OK:
                raise Exception('Failed to write to address 0x%04x' % (addr + offset))
            cmd = STC_CMD_WRITE_CONT

        # Finish write (bootloader v7.2 and later)
        if self.chipversion >= 0x72:
            self.command([STC_CMD_FINISH, 0, 0, STC_BREAK, STC_BREAK ^ 0xff], 'Failed to finish write', ok=True)

    # Write option bytes (keeps the MCS register values read from the MCU)
    def writeoptions(self):
        block  = [STC_CMD_OPTIONS, 0, 0, STC_BREAK, STC_BREAK ^ 0xff]
        block += STC_BLOCK_OPTIONS1
        block += self.osc_freq.to_bytes(4, byteorder='big')
        block += [self.osc_trim, self.osc_band, self.osc_div]
        block += [0xff, self.options[0], 0xff, 0xff, 0xff]
        block += list(self.options[1:5])
        self.command(block, 'Failed to write option bytes', ok=True)

# ===================================================================================
# Device Constants
# ===================================================================================

STC_PAGE_SIZE      = 128
STC_TIMEOUT        = 1
STC_SYNC_TIMEOUT   = 0.01
STC_ERASE_TIMEOUT  = 10

STC_CHAR_SYNC      = 0x7f
STC_CHAR_TRIM      = 0x66
STC_CHAR_TRIM_D    = 0xfe

STC_PREFIX         = 0x46
STC_BREAK          = 0x5a
STC_SUFFIX         = 0x16
STC_TX_CODE        = 0x6a
STC_RX_CODE        = 0x68
STC_RPL_INFO       = 0x50
STC_RPL_LOCKED     = 0x0f
STC_OK             = 0x54

STC_CMD_TRIM       = 0x00
STC_CMD_BAUD_SET   = 0x01
STC_CMD_BAUD_CHECK = 0x05
STC_CMD_ERASE      = 0x03
STC_CMD_OPTIONS    = 0x04
STC_CMD_FINISH     = 0x07
STC_CMD_WRITE      = 0x22
STC_CMD_WRITE_CONT = 0x02
STC_CMD_EXIT       = 0xff

STC_BLOCK_TRIM     = [0x00, 0x05, 0x02, 0x00, 0x80, 0x00, 0x00, 0x80,
                      0x80, 0x80, 0xfd, 0x00]
STC_BLOCK_OPTIONS1 = [0xff, 0xff, 0xff, 0x00, 0xff, 0xff, 0x00, 0xff,
                      0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
                      0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x00, 0xff]

# ===================================================================================
# Device Dictionary
# ===================================================================================

# cal: frequency calibration method (stc8g: STC8G/STC8H1K, stc8d: other STC8H, STC8A D4)
DEVICES = [
    {'name': 'STC8H1K16',         'id': 0xF721, 'flash_size':  16384, 'cal': 'stc8g'},
    {'name': 'STC8H1K20',         'id': 0xF722, 'flash_size':  20480, 'cal': 'stc8g'},
    {'name': 'STC8H1K24',         'id': 0xF723, 'flash_size':  24576, 'cal': 'stc8g'},
    {'name': 'STC8H1K28',         'id': 0xF724, 'flash_size':  28672, 'cal': 'stc8g'},
    {'name': 'STC8H1K33',         'id': 0xF725, 'flash_size':  33792, 'cal': 'stc8g'},
    {'name': 'STC8H1K02',         'id': 0xF731, 'flash_size':   2048, 'cal': 'stc8g'},
    {'name': 'STC8H1K04',         'id': 0xF732, 'flash_size':   4096, 'cal': 'stc8g'},
    {'name': 'STC8H1K06',         'id': 0xF733, 'flash_size':   6144, 'cal': 'stc8g'},
    {'name': 'STC8H1K08',         'id': 0xF734, 'flash_size':   8192, 'cal': 'stc8g'},
    {'name': 'STC8H1K10',         'id': 0xF735, 'flash_size':  10240, 'cal': 'stc8g'},
    {'name': 'STC8H1K12',         'id': 0xF736, 'flash_size':  12288, 'cal': 'stc8g'},
    {'name': 'STC8H1K17',         'id': 0xF737, 'flash_size':  17408, 'cal': 'stc8g'},
    {'name': 'STC8H3K16S4',       'id': 0xF741, 'flash_size':  16384, 'cal': 'stc8d'},
    {'name': 'STC8H3K32S4',       'id': 0xF742, 'flash_size':  32768, 'cal': 'stc8d'},
    {'name': 'STC8H3K60S4',       'id': 0xF743, 'flash_size':  61440, 'cal': 'stc8d'},
    {'name': 'STC8H3K64S4',       'id': 0xF744, 'flash_size':  65024, 'cal': 'stc8d'},
    {'name': 'STC8H3K48S4',       'id': 0xF745, 'flash_size':  49152, 'cal': 'stc8d'},
    {'name': 'STC8H3K16S2',       'id': 0xF749, 'flash_size':  16384, 'cal': 'stc8d'},
    {'name': 'STC8H3K32S2',       'id': 0xF74A, 'flash_size':  32768, 'cal': 'stc8d'},
    {'name': 'STC8H3K60S2',       'id': 0xF74B, 'flash_size':  61440, 'cal': 'stc8d'},
    {'name': 'STC8H3K64S2',       'id': 0xF74C, 'flash_size':  65024, 'cal': 'stc8d'},
    {'name': 'STC8H3K48S2',       'id': 0xF74D, 'flash_size':  49152, 'cal': 'stc8d'},
    {'name': 'STC8G1K02-20/16P',  'id': 0xF751, 'flash_size':   2048, 'cal': 'stc8g'},
    {'name': 'STC8G1K04-20/16P',  'id': 0xF752, 'flash_size':   4096, 'cal': 'stc8g'},
    {'name': 'STC8G1K06-20/16P',  'id': 0xF753, 'flash_size':   6144, 'cal': 'stc8g'},
    {'name': 'STC8G1K08-20/16P',  'id': 0xF754, 'flash_size':   8192, 'cal': 'stc8g'},
    {'name': 'STC8G1K10-20/16P',  'id': 0xF755, 'flash_size':  10240, 'cal': 'stc8g'},
    {'name': 'STC8G1K12-20/16P',  'id': 0xF756, 'flash_size':  12288, 'cal': 'stc8g'},
    {'name': 'STC8G1K17-20/16P',  'id': 0xF757, 'flash_size':  17408, 'cal': 'stc8g'},
    {'name': 'STC8G2K16S4',       'id': 0xF761, 'flash_size':  16384, 'cal': 'stc8g'},
    {'name': 'STC8G2K32S4',       'id': 0xF762, 'flash_size':  32768, 'cal': 'stc8g'},
    {'name': 'STC8G2K60S4',       'id': 0xF763, 'flash_size':  61440, 'cal': 'stc8g'},
    {'name': 'STC8G2K64S4',       'id': 0xF764, 'flash_size':  65024, 'cal': 'stc8g'},
    {'name': 'STC8G2K48S4',       'id': 0xF765, 'flash_size':  49152, 'cal': 'stc8g'},
    {'name': 'STC8G2K16S2',       'id': 0xF769, 'flash_size':  16384, 'cal': 'stc8g'},
    {'name': 'STC8G2K32S2',       'id': 0xF76A, 'flash_size':  32768, 'cal': 'stc8g'},
    {'name': 'STC8G2K60S2',       'id': 0xF76B, 'flash_size':  61440, 'cal': 'stc8g'},
    {'name': 'STC8G2K64S2',       'id': 0xF76C, 'flash_size':  65024, 'cal': 'stc8g'},
    {'name': 'STC8G2K48S2',       'id': 0xF76D, 'flash_size':  49152, 'cal': 'stc8g'},
    {'name': 'STC8G1K02T',        'id': 0xF771, 'flash_size':   2048, 'cal': 'stc8g'},
    {'name': 'STC8G1K04T',        'id': 0xF772, 'flash_size':   4096, 'cal': 'stc8g'},
    {'name': 'STC8G1K06T',        'id': 0xF773, 'flash_size':   6144, 'cal': 'stc8g'},
    {'name': 'STC8G1K08T',        'id': 0xF774, 'flash_size':   8192, 'cal': 'stc8g'},
    {'name': 'STC8G1K10T',        'id': 0xF775, 'flash_size':  10240, 'cal': 'stc8g'},
    {'name': 'STC8G1K12T',        'id': 0xF776, 'flash_size':  12288, 'cal': 'stc8g'},
    {'name': 'STC8G1K17T',        'id': 0xF777, 'flash_size':  17408, 'cal': 'stc8g'},
    {'name': 'STC8H8K16U',        'id': 0xF781, 'flash_size':  16384, 'cal': 'stc8d'},
    {'name': 'STC8H8K32U',        'id': 0xF782, 'flash_size':  32768, 'cal': 'stc8d'},
    {'name': 'STC8H8K60U',        'id': 0xF783, 'flash_size':  61440, 'cal': 'stc8d'},
    {'name': 'STC8H8K64U',        'id': 0xF784, 'flash_size':  65024, 'cal': 'stc8d'},
    {'name': 'STC8H8K48U',        'id': 0xF785, 'flash_size':  49152, 'cal': 'stc8d'},
    {'name': 'STC8G1K02A-8P',     'id': 0xF791, 'flash_size':   2048, 'cal': 'stc8g'},
    {'name': 'STC8G1K04A-8P',     'id': 0xF792, 'flash_size':   4096, 'cal': 'stc8g'},
    {'name': 'STC8G1K06A-8P',     'id': 0xF793, 'flash_size':   6144, 'cal': 'stc8g'},
    {'name': 'STC8G1K08A-8P',     'id': 0xF794, 'flash_size':   8192, 'cal': 'stc8g'},
    {'name': 'STC8G1K10A-8P',     'id': 0xF795, 'flash_size':  10240, 'cal': 'stc8g'},
    {'name': 'STC8G1K12A-8P',     'id': 0xF796, 'flash_size':  12288, 'cal': 'stc8g'},
    {'name': 'STC8G1K17A-8P',     'id': 0xF797, 'flash_size':  17408, 'cal': 'stc8g'},
    {'name': 'STC8G1K02-8P',      'id': 0xF7A1, 'flash_size':   2048, 'cal': 'stc8g'},
    {'name': 'STC8G1K04-8P',      'id': 0xF7A2, 'flash_size':   4096, 'cal': 'stc8g'},
    {'name': 'STC8G1K06-8P',      'id': 0xF7A3, 'flash_size':   6144, 'cal': 'stc8g'},
    {'name': 'STC8G1K08-8P',      'id': 0xF7A4, 'flash_size':   8192, 'cal': 'stc8g'},
    {'name': 'STC8G1K10-8P',      'id': 0xF7A5, 'flash_size':  10240, 'cal': 'stc8g'},
    {'name': 'STC8G1K12-8P',      'id': 0xF7A6, 'flash_size':  12288, 'cal': 'stc8g'},
    {'name': 'STC8G1K17-8P',      'id': 0xF7A7, 'flash_size':  17408, 'cal': 'stc8g'},
    {'name': 'STC8H4K16TLR',      'id': 0xF7C9, 'flash_size':  16384, 'cal': 'stc8d'},
    {'name': 'STC8H4K32TLR',      'id': 0xF7CA, 'flash_size':  32768, 'cal': 'stc8d'},
    {'name': 'STC8H4K60TLR',      'id': 0xF7CB, 'flash_size':  61440, 'cal': 'stc8d'},
    {'name': 'STC8H4K64TLR',      'id': 0xF7CC, 'flash_size':  65024, 'cal': 'stc8d'},
    {'name': 'STC8H4K48TLR',      'id': 0xF7CD, 'flash_size':  49152, 'cal': 'stc8d'},
    {'name': 'STC8A8K16D4',       'id': 0xF7F1, 'flash_size':  16384, 'cal': 'stc8d'},
    {'name': 'STC8A8K32D4',       'id': 0xF7F2, 'flash_size':  32768, 'cal': 'stc8d'},
    {'name': 'STC8A8K60D4',       'id': 0xF7F3, 'flash_size':  61440, 'cal': 'stc8d'},
    {'name': 'STC8A8K64D4',       'id': 0xF7F4, 'flash_size':  65024, 'cal': 'stc8d'},
    {'name': 'STC8A8K48D4',       'id': 0xF7F5, 'flash_size':  49152, 'cal': 'stc8d'},
    {'name': 'STC8A2K16D4',       'id': 0xF801, 'flash_size':  16384, 'cal': 'stc8d'},
    {'name': 'STC8A2K32D4',       'id': 0xF802, 'flash_size':  32768, 'cal': 'stc8d'},
    {'name': 'STC8A2K60D4',       'id': 0xF803, 'flash_size':  61440, 'cal': 'stc8d'},
    {'name': 'STC8A2K64D4',       'id': 0xF804, 'flash_size':  65024, 'cal': 'stc8d'},
    {'name': 'STC8A2K48D4',       'id': 0xF805, 'flash_size':  49152, 'cal': 'stc8d'},
    {'name': 'STC8H4K16TLCD',     'id': 0xF811, 'flash_size':  16384, 'cal': 'stc8d'},
    {'name': 'STC8H4K32TLCD',     'id': 0xF812, 'flash_size':  32768, 'cal': 'stc8d'},
    {'name': 'STC8H4K60TLCD',     'id': 0xF813, 'flash_size':  61440, 'cal': 'stc8d'},
    {'name': 'STC8H4K64TLCD',     'id': 0xF814, 'flash_size':  65024, 'cal': 'stc8d'},
    {'name': 'STC8H4K48TLCD',     'id': 0xF815, 'flash_size':  49152, 'cal': 'stc8d'},
    {'name': 'STC8H2K16TLCD',     'id': 0xF819, 'flash_size':  16384, 'cal': 'stc8d'},
    {'name': 'STC8H2K32TLCD',     'id': 0xF81A, 'flash_size':  32768, 'cal': 'stc8d'},
    {'name': 'STC8H2K60TLCD',     'id': 0xF81B, 'flash_size':  61440, 'cal': 'stc8d'},
    {'name': 'STC8H2K64TLCD',     'id': 0xF81C, 'flash_size':  65024, 'cal': 'stc8d'},
    {'name': 'STC8H2K48TLCD',     'id': 0xF81D, 'flash_size':  49152, 'cal': 'stc8d'},
    {'name': 'STC8H4K16LCD',      'id': 0xF821, 'flash_size':  16384, 'cal': 'stc8d'},
    {'name': 'STC8H4K32LCD',      'id': 0xF822, 'flash_size':  32768, 'cal': 'stc8d'},
    {'name': 'STC8H4K60LCD',      'id': 0xF823, 'flash_size':  61440, 'cal': 'stc8d'},
    {'name': 'STC8H4K64LCD',      'id': 0xF824, 'flash_size':  65024, 'cal': 'stc8d'},
    {'name': 'STC8H4K48LCD',      'id': 0xF825, 'flash_size':  49152, 'cal': 'stc8d'},
    {'name': 'STC8H4K16TL',       'id': 0xF831, 'flash_size':  16384, 'cal': 'stc8d'},
    {'name': 'STC8H4K32TL',       'id': 0xF832, 'flash_size':  32768, 'cal': 'stc8d'},
    {'name': 'STC8H4K60TL',       'id': 0xF833, 'flash_size':  61440, 'cal': 'stc8d'},
    {'name': 'STC8H4K64TL',       'id': 0xF834, 'flash_size':  65024, 'cal': 'stc8d'},
    {'name': 'STC8H4K48TL',       'id': 0xF835, 'flash_size':  49152, 'cal': 'stc8d'},
    {'name': 'STC8H2K16TL',       'id': 0xF839, 'flash_size':  16384, 'cal': 'stc8d'},
    {'name': 'STC8H2K32TL',       'id': 0xF83A, 'flash_size':  32768, 'cal': 'stc8d'},
    {'name': 'STC8H2K60TL',       'id': 0xF83B, 'flash_size':  61440, 'cal': 'stc8d'},
    {'name': 'STC8H2K64TL',       'id': 0xF83C, 'flash_size':  65024, 'cal': 'stc8d'},
    {'name': 'STC8H2K48TL',       'id': 0xF83D, 'flash_size':  49152, 'cal': 'stc8d'},
    {'name': 'STC8H1K02T',        'id': 0xF841, 'flash_size':   2048, 'cal': 'stc8d'},
    {'name': 'STC8H1K04T',        'id': 0xF842, 'flash_size':   4096, 'cal': 'stc8d'},
    {'name': 'STC8H1K06T',        'id': 0xF843, 'flash_size':   6144, 'cal': 'stc8d'},
    {'name': 'STC8H1K08T',        'id': 0xF844, 'flash_size':   8192, 'cal': 'stc8d'},
    {'name': 'STC8H1K10T',        'id': 0xF845, 'flash_size':  10240, 'cal': 'stc8d'},
    {'name': 'STC8H1K12T',        'id': 0xF846, 'flash_size':  12288, 'cal': 'stc8d'},
    {'name': 'STC8H1K17T',        'id': 0xF847, 'flash_size':  17408, 'cal': 'stc8d'}
]

# ===================================================================================

if __name__ == "__main__":
    _main()
