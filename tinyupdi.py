#!/usr/bin/env python3
# ===================================================================================
# Project:   TinyUPDI - Minimal application-specific UPDI programmer based on pyupdi
# Version:   v1.4
# Year:      2022
# Author:    Stefan Wagner
# Github:    https://github.com/wagiminator
# License:   MIT License
# ===================================================================================
#
# Description:
# ------------
# TinyUPDI is a serial UPDI programmer software that is adapted to a specific
# application and reduced to the functions required for this. It is normally used
# for projects with a tinyAVR and a built-in USB to serial adapter to simplify
# firmware uploading.
#
# References:
# -----------
# TinyUPDI is essentially based on pyupdi and pymcuprog:
# - https://github.com/mraardvark/pyupdi
# - https://github.com/microchip-pic-avr-tools/pymcuprog
#
# Dependencies:
# -------------
# - pyserial
#
# Restrictions:
# -------------
# - Target MCU must be a 0, 1, or 2-series tinyAVR.
# - Only flash and fuses can be programmed.
# - Firmware file must be a binary (not ELF or HEX!).
#
# Operating Instructions:
# -----------------------
# - python3 tinyupdi.py [-h] [-d DEVICE] [-e] [-f FLASH] [-fs [FUSES [FUSES ...]]]
#   -h, --help                show help message and exit
#   -d, --device              set target device (if not set, it will be auto-detected)
#   -e, --erase               perform a chip erase (implied with --flash)
#   -f FLASH, --flash FLASH   BIN file to flash
#   -fs [FUSES [FUSES ...]], --fuses [FUSES [FUSES ...]]
#                             fuses to set (syntax: fuse_nr:0xvalue)
#   -t TRIM, --trim TRIM      configure oscillator for given frequency (fuse 2)
# - Example:
#   python3 tinyupdi.py -d attiny202 -f firmware.bin -fs 6:0x04 7:0x00 8:0x00 -t 8000000


import re
import sys
import time
import argparse
import serial
from serial import Serial
from serial.tools.list_ports import comports

# If the PID/VID of the USB-to-Serial converter is known, it can be defined here,
# which can make the auto-detection a lot faster.
#VID = '1A86'
#PID = '7523'


# ===================================================================================
# Main Function
# ===================================================================================

def _main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Minimal command line'
                                     ' interface for UPDI programming')
    parser.add_argument('-d', '--device', choices=get_supported_devices(),
                        help='target device (if not set, it will be auto-detected)')
    parser.add_argument("-e", "--erase", action="store_true",
                        help="perform a chip erase (implied with --flash)")
    parser.add_argument('-f', '--flash', help='BIN file to flash')
    parser.add_argument('-fs', '--fuses', action='append', nargs='*',
                        help='fuses to set (syntax: fuse_nr:0xvalue)')
    parser.add_argument('-t', '--trim', help='configure oscillator for given frequency (fuse 2)')
    args = parser.parse_args(sys.argv[1:])

    # Check arguments
    if not any( (args.fuses, args.flash, args.erase) ):
        print('No arguments - no action!')
        sys.exit(0)

    if args.fuses is not None:
        fuselist = list()
        for fslist in args.fuses:
            for fsarg in fslist:
                if not re.match('^[0-9]+:0x[0-9a-fA-F]+$', fsarg):
                    sys.stderr.write('ERROR: Bad fuses format {}. Expected fuse_nr:0xvalue\n'.format(fsarg))
                    sys.exit(1)
                lst = fsarg.split(':0x')
                fuselist.append( (int(lst[0]), int(lst[1], 16)) )

    # Establish connection via serial to UPDI device
    try:
        print('Connecting to device ...')
        tinyupdi = Programmer()
    except Exception as ex:
        sys.stderr.write('ERROR: ' + str(ex) + '!\n')
        sys.exit(1)
    print('SUCCESS: Found programmer on port %s.' % tinyupdi.port)

    # Programming the device
    try:
        # Detect target device
        print('Detecting target MCU ...')
        device = tinyupdi.detect()
        print('SUCCESS: Found %s with %d bytes of flash.' % (device, tinyupdi.flash_size))
        if (args.device is not None) and (not args.device == device):
            raise Exception('Found device is not ' + args.device)

        # Perform chip erase
        if (args.erase) or (args.flash is not None):
            print('Performing chip erase ...')
            tinyupdi.erase()

        # Flash binary file
        if args.flash is not None:
            print('Flashing %s to %s ...' % (args.flash, device))
            with open(args.flash, 'rb') as f: data = f.read()
            tinyupdi.flash_data(data)
            print('Verifying ...')
            tinyupdi.verify_data(data)
            print('SUCCESS: %d bytes written and verified.' % len(data))

        # Write fuses
        if args.fuses is not None:
            print('Writing fuses ...')
            for fuse in fuselist:
                tinyupdi.set_fuse(fuse[0], fuse[1])
            print('Verifying fuses ...')
            for fuse in fuselist:
                tinyupdi.verify_fuse(fuse[0], fuse[1])
            print('SUCCESS: Fuses written and verified.')
                
        # Write fuse to set oscillator according to frequency
        if args.trim is not None:
            print('Setting oscillator for %s Hz ...' % args.trim)
            osc = tinyupdi.trim(int(args.trim))
            print('SUCCESS: Oscillator runs at %d MHz with corresponding factory calibration.' % osc)

    except Exception as ex:
        sys.stderr.write('ERROR: ' + str(ex) + '!\n')
        tinyupdi.exit()
        sys.exit(1)

    # Finish all up
    tinyupdi.exit()
    print('DONE.')
    sys.exit(0)


# ===================================================================================
# Programmer Class
# ===================================================================================

class Programmer(Serial):
    def __init__(self):
        super().__init__(baudrate = 230400, timeout = 1, parity=serial.PARITY_EVEN, stopbits=serial.STOPBITS_TWO)
        self.syscfg_address  = 0x0F00
        self.nvmctrl_address = 0x1000
        self.sigrow_address  = 0x1100
        self.fuses_address   = 0x1280
        self.userrow_address = 0x1300
        self.flash_pagesize  = 64
        self.flash_start     = 0x8000
        self.flash_size      = 0x0800
        self.identify()

    # Identify port of programmer and enter programming mode
    def identify(self):
        for p in comports():
            if (('VID' not in globals()) or (VID in p.hwid)) and (('PID' not in globals()) or (PID in p.hwid)):
                self.port = p.device
                try:
                    self.open()
                except:
                    continue
                self.__init()
                if not self.__check():
                    self.__send_double_break()
                    self.__init()
                    if not self.__check():
                        self.close()
                        continue
                try:
                    self.__enter_progmode()
                except:
                    self.__unlock()
                return
        raise Exception('Device not found')


    # ------------------------------------------------------------------------------
    # High-Level Functions
    # ------------------------------------------------------------------------------

    # Detect device
    def detect(self):
        deviceid = self.__get_device_id()
        for dev in UPDI_DEVICES:
            if dev['device_id'] == deviceid:
                self.flash_size = dev['flash_size']
                self.flash_pagesize = dev['flash_pagesize']
                return dev['name']
        raise Exception('Unknown or unsupported device')

    # Disable UPDI and serial connection
    def exit(self):
        self.__reset(apply_reset=True)
        self.__reset(apply_reset=False)
        self.__stcs(UPDI_CS_CTRLB, (1 << UPDI_CTRLB_UPDIDIS_BIT) | (1 << UPDI_CTRLB_CCDETDIS_BIT))
        self.close()

    # Does a chip erase using the NVM controller (v0)
    def erase(self):
        if not self.__wait_nvm_ready():
            raise Exception('Timeout waiting for flash ready before erase')
        self.__execute_nvm_command(UPDI_V0_NVMCTRL_CTRLA_CHIP_ERASE)
        if not self.__wait_nvm_ready():
            raise Exception('Timeout waiting for flash ready after erase')

    # Flash bin file
    def flash_bin(self, filename):
        with open(filename, 'rb') as f: data = f.read()
        self.flash_data(data)
        return len(data)

    # Verify bin file
    def verify_bin(self, filename):
        with open(filename, 'rb') as f: data = f.read()
        self.verify_data(data)
        return len(data)

    # Flash data
    def flash_data(self, data):
        if len(data) > self.flash_size:
            raise Exception('Not enough memory')
        self.__write_flash(self.flash_start, data)

    # Verify data
    def verify_data(self, data):
        if len(data) > self.flash_size:
            raise Exception('Not enough memory')
        readback = self.__read_flash(self.flash_start, len(data))
        if data != readback:
            raise Exception('Flash verification failure')

    # Set single fuse
    def set_fuse(self, fusenum, value):
        self.__write_fuse(fusenum, value)

    # Verify single fuse
    def verify_fuse(self, fusenum, value):
        actual_val = self.__read_fuse(fusenum)
        if actual_val != value:
            raise Exception('Fuse ' + str(fusenum) + ' verification failure')

    # Configure oscillator for given system freqency
    def trim(self, freq):
        for x in [1, 2, 4, 8, 16, 32, 64, 6, 10, 12, 24, 48]:
            if round(20000000 / x) == freq:
                self.set_fuse(0x02, 0x02)
                self.verify_fuse(0x02, 0x02)
                return 20
            if round(16000000 / x) == freq:
                self.set_fuse(0x02, 0x01)
                self.verify_fuse(0x02, 0x01)
                return 16
        raise Exception('Unsupported frequency')


    # ------------------------------------------------------------------------------
    # Physical Layer for UPDI Stack
    # ------------------------------------------------------------------------------

    # Send a double break to reset the UPDI port
    def __send_double_break(self):
        self.close()
        temporary_serial = Serial(self.port, 300, stopbits=serial.STOPBITS_ONE, timeout=1)
        temporary_serial.write([UPDI_BREAK, UPDI_BREAK])
        temporary_serial.read(2)
        temporary_serial.close()
        self.open()

    # Send a char array to UPDI with NO inter-byte delay
    def __send(self, command):
        self.write(command)
        self.read(len(command))

    # Receive a frame of a known number of chars from UPDI
    def __receive(self, size):
        return self.read(size)


    # ------------------------------------------------------------------------------
    # Datalink Layer for UPDI Stack
    # ------------------------------------------------------------------------------

    # Set the inter-byte delay bit and disable collision detection
    def __init(self):
        self.__stcs(UPDI_CS_CTRLB, 1 << UPDI_CTRLB_CCDETDIS_BIT)
        self.__stcs(UPDI_CS_CTRLA, 1 << UPDI_CTRLA_IBDLY_BIT)

    # Check UPDI by loading CS STATUSA
    def __check(self):
        if self.__ldcs(UPDI_CS_STATUSA) != 0:
            return True
        return False

    # Load data from Control/Status space
    def __ldcs(self, address):
        self.__send([UPDI_PHY_SYNC, UPDI_LDCS | (address & 0x0F)])
        response = self.__receive(1)
        if len(response) != 1:
            return 0x00
        return response[0]

    # Store a value to Control/Status space
    def __stcs(self, address, value):
        self.__send([UPDI_PHY_SYNC, UPDI_STCS | (address & 0x0F), value])

    # Load a single byte direct from a 16-bit address
    def __ld(self, address):
        self.__send([UPDI_PHY_SYNC, UPDI_LDS | UPDI_ADDRESS_16 | UPDI_DATA_8,
                   address & 0xFF, (address >> 8) & 0xFF])
        return self.__receive(1)[0]

    # Load a 16-bit word directly from a 16-bit address
    def __ld16(self, address):
        self.__send([UPDI_PHY_SYNC, UPDI_LDS | UPDI_ADDRESS_16 | UPDI_DATA_16,
                   address & 0xFF, (address >> 8) & 0xFF])
        return self.__receive(2)

    # Store a single byte value directly to a 16-bit address
    def __st(self, address, value):
        self.__send([UPDI_PHY_SYNC, UPDI_STS | UPDI_ADDRESS_16 | UPDI_DATA_8,
                   address & 0xFF, (address >> 8) & 0xFF])
        response = self.__receive(1)
        if len(response) != 1 or response[0] != UPDI_PHY_ACK:
            raise Exception('Failed to communicate with device (st)')
        self.__send([value & 0xFF])
        response = self.__receive(1)
        if len(response) != 1 or response[0] != UPDI_PHY_ACK:
            raise Exception('Failed to communicate with device (st)')

    # Store a 16-bit word value directly to a 16-bit address
    def __st16(self, address, value):
        self.__send([UPDI_PHY_SYNC, UPDI_STS | UPDI_ADDRESS_16 | UPDI_DATA_16,
                   address & 0xFF, (address >> 8) & 0xFF])
        response = self.__receive(1)
        if len(response) != 1 or response[0] != UPDI_PHY_ACK:
            raise Exception('Failed to communicate with device (st)')
        self.__send([value & 0xFF, (value >> 8) & 0xFF])
        response = self.__receive(1)
        if len(response) != 1 or response[0] != UPDI_PHY_ACK:
            raise Exception('Failed to communicate with device (st)')

    # Load a number of bytes from the pointer location with pointer post-increment
    def __ld_ptr_inc(self, size):
        self.__send([UPDI_PHY_SYNC, UPDI_LD | UPDI_PTR_INC | UPDI_DATA_8])
        return self.__receive(size)

    # Load a 16-bit word value from the pointer location with pointer post-increment
    def __ld_ptr_inc16(self, words):
        self.__send([UPDI_PHY_SYNC, UPDI_LD | UPDI_PTR_INC | UPDI_DATA_16])
        return self.__receive(words << 1)

    # Set the pointer location
    def __st_ptr(self, address):
        self.__send([UPDI_PHY_SYNC, UPDI_ST | UPDI_PTR_ADDRESS | UPDI_DATA_16,
                   address & 0xFF, (address >> 8) & 0xFF])
        response = self.__receive(1)
        if len(response) != 1 or response[0] != UPDI_PHY_ACK:
            raise Exception('Failed to communicate with device (st_ptr)')

    # Store data to the pointer location with pointer post-increment
    def __st_ptr_inc(self, data):
        self.__send([UPDI_PHY_SYNC, UPDI_ST | UPDI_PTR_INC | UPDI_DATA_8, data[0]])
        response = self.__receive(1)
        if len(response) != 1 or response[0] != UPDI_PHY_ACK:
            raise Exception('Failed to communicate with device (ACK st_ptr_inc)')
        n = 1
        while n < len(data):
            self.__send([data[n]])
            response = self.__receive(1)
            if len(response) != 1 or response[0] != UPDI_PHY_ACK:
                raise Exception('Failed to communicate with device (st_ptr_inc)')
            n += 1

    # Store a 16-bit word value to the pointer location with pointer post-increment
    def __st_ptr_inc16(self, data):
        ctrla_ackon = 1 << UPDI_CTRLA_IBDLY_BIT
        ctrla_ackoff = ctrla_ackon | (1 << UPDI_CTRLA_RSD_BIT)
        self.__stcs(UPDI_CS_CTRLA, ctrla_ackoff)
        self.__send([UPDI_PHY_SYNC, UPDI_ST | UPDI_PTR_INC | UPDI_DATA_16] )
        self.__send(data)
        self.__stcs(UPDI_CS_CTRLA, ctrla_ackon)

    # Store a value to the repeat counter
    def __repeat(self, repeats):
        if (repeats - 1) > UPDI_MAX_REPEAT_SIZE:
            raise Exception('Invalid repeat count')
        repeats -= 1
        self.__send([UPDI_PHY_SYNC, UPDI_REPEAT | UPDI_REPEAT_BYTE, repeats & 0xFF])

    # Write a key
    def __key(self, size, key):
        if len(key) != 8 << size:
            raise Exception('Invalid Key length')
        self.__send([UPDI_PHY_SYNC, UPDI_KEY | UPDI_KEY_KEY | size])
        self.__send(list(reversed(list(key))))


    # ------------------------------------------------------------------------------
    # Application Layer for UPDI Stack
    # ------------------------------------------------------------------------------

    # Enter NVM programming mode
    def __enter_progmode(self):
        if self.__in_prog_mode():
            return
        self.__key(UPDI_KEY_64, UPDI_KEY_NVM)
        key_status = self.__ldcs(UPDI_ASI_KEY_STATUS)
        if not key_status & (1 << UPDI_ASI_KEY_STATUS_NVMPROG):
            raise Exception('Key not accepted')
        self.__reset(apply_reset=True)
        self.__reset(apply_reset=False)
        if not self.__wait_unlocked(100):
            raise Exception('Failed to enter NVM programming mode: device is locked')
        if not self.__in_prog_mode():
            raise Exception('Failed to enter NVM programming mode')

    # Get device ID
    def __get_device_id(self):
        return int.from_bytes(self.__read_data(self.sigrow_address, 3), byteorder='big')

    # Check whether the NVM PROG flag is up
    def __in_prog_mode(self):
        if self.__ldcs(UPDI_ASI_SYS_STATUS) & (1 << UPDI_ASI_SYS_STATUS_NVMPROG):
            return True
        return False

    # Wait for the device to be unlocked
    def __wait_unlocked(self, timeout_ms):
        timeout = Timeout(timeout_ms)
        while not timeout.expired():
            if not self.__ldcs(UPDI_ASI_SYS_STATUS) & (1 << UPDI_ASI_SYS_STATUS_LOCKSTATUS):
                return True
        return False

    # Unlock and erase
    def __unlock(self):
        self.__key(UPDI_KEY_64, UPDI_KEY_CHIPERASE)
        key_status = self.__ldcs(UPDI_ASI_KEY_STATUS)
        if not key_status & (1 << UPDI_ASI_KEY_STATUS_CHIPERASE):
            raise Exception('Key not accepted')
        self.__reset(apply_reset=True)
        self.__reset(apply_reset=False)
        if not self.__wait_unlocked(500):
            raise Exception('Failed to chip erase using key')

    # Apply or release UPDI reset condition
    def __reset(self, apply_reset):
        if apply_reset:
            self.__stcs(UPDI_ASI_RESET_REQ, UPDI_RESET_REQ_VALUE)
        else:
            self.__stcs(UPDI_ASI_RESET_REQ, 0x00)

    # Wait for the NVM controller to be ready
    def __wait_nvm_ready(self):
        timeout = Timeout(10000)
        while not timeout.expired():
            status = self.__ld(self.nvmctrl_address + UPDI_NVMCTRL_STATUS)
            if status & (1 << UPDI_NVM_STATUS_WRITE_ERROR):
                return False
            if not status & ((1 << UPDI_NVM_STATUS_EEPROM_BUSY) | (1 << UPDI_NVM_STATUS_FLASH_BUSY)):
                return True
        return False

    # Execute an NVM COMMAND on the NVM CTRL
    def __execute_nvm_command(self, command):
        return self.__st(self.nvmctrl_address + UPDI_NVMCTRL_CTRLA, command)

    # Write a number of words to memory
    def __write_data_words(self, address, data):
        if len(data) == 2:
            value = data[0] + (data[1] << 8)
            return self.__st16(address, value)
        if len(data) > UPDI_MAX_REPEAT_SIZE << 1:
            raise Exception('Invalid data length')
        self.__st_ptr(address)
        self.__repeat(len(data) >> 1)
        return self.__st_ptr_inc16(data)

    # Writes a number of bytes to memory
    def __write_data(self, address, data):
        if len(data) == 1:
            return self.__st(address, data[0])
        elif len(data) == 2:
            self.__st(address, data[0])
            return self.__st(address + 1, data[1])
        if len(data) > UPDI_MAX_REPEAT_SIZE:
            raise Exception('Invalid data length')
        self.__st_ptr(address)
        self.__repeat(len(data))
        return self.__st_ptr_inc(data)

    # Write a page of data to NVM (v0)
    def __write_nvm(self, address, data, use_word_access=True):
        if not self.__wait_nvm_ready():
            raise Exception('Timeout waiting for flash ready before page buffer clear')
        self.__execute_nvm_command(UPDI_V0_NVMCTRL_CTRLA_PAGE_BUFFER_CLR)
        if not self.__wait_nvm_ready():
            raise Exception('Timeout waiting for flash ready after page buffer clear')
        if use_word_access:
            self.__write_data_words(address, data)
        else:
            self.__write_data(address, data)
        self.__execute_nvm_command(UPDI_V0_NVMCTRL_CTRLA_WRITE_PAGE)
        if not self.__wait_nvm_ready():
            raise Exception('Timeout waiting for flash ready after page write')

    # Write one fuse value (v0)
    def __write_fuse(self, fusenum, value):
        if not self.__wait_nvm_ready():
            raise Exception('Timeout waiting for NVM controller to be ready before fuse write')
        address = self.fuses_address + fusenum
        self.__st(self.nvmctrl_address + UPDI_NVMCTRL_ADDRL, address & 0xFF)
        self.__st(self.nvmctrl_address + UPDI_NVMCTRL_ADDRH, (address >> 8) & 0xFF)
        self.__st(self.nvmctrl_address + UPDI_NVMCTRL_DATAL, value & 0xFF)
        self.__execute_nvm_command(UPDI_V0_NVMCTRL_CTRLA_WRITE_FUSE)
        if not self.__wait_nvm_ready():
            raise Exception('Timeout waiting for NVM controller to be ready after fuse write')

    # Read a number of bytes of data from UPDI
    def __read_data(self, address, size):
        if size > UPDI_MAX_REPEAT_SIZE:
            raise Exception('Can\'t read that many bytes in one go')
        self.__st_ptr(address)
        if size > 1:
            self.__repeat(size)
        return self.__ld_ptr_inc(size)

    # Read a number of words of data from UPDI
    def __read_data_words(self, address, words):
        if words > UPDI_MAX_REPEAT_SIZE:
            raise Exception('Can\'t read that many words in one go')
        self.__st_ptr(address)
        if words > 1:
            self.__repeat(words)
        return self.__ld_ptr_inc16(words)


    # ------------------------------------------------------------------------------
    # NVM programming algorithm
    # ------------------------------------------------------------------------------

    # Read from flash
    def __read_flash(self, address, size):
        pages = size // self.flash_pagesize
        if size % self.flash_pagesize:
            pages += 1
        data = bytes()
        for _ in range(pages):
            data += (self.__read_data_words(address, self.flash_pagesize >> 1))
            address += self.flash_pagesize
        return data[:size]

    # Write to flash
    def __write_flash(self, address, data):
        data = self.__pad_data(data, self.flash_pagesize)
        pages = self.__page_data(data, self.flash_pagesize)
        for page in pages:
            self.__write_nvm(address, page, use_word_access=True)
            address += len(page)

    # Read one fuse value
    def __read_fuse(self, fusenum):
        address = self.fuses_address + fusenum
        data = self.__ld(address)
        return data

    # Pad data so that there are full pages
    def __pad_data(self, data, blocksize):
        return data + b'\xFF' * (len(data) % blocksize)

    # Divide data into pages
    def __page_data(self, data, size):
        total_length = len(data)
        result = list()
        while len(result) < total_length / size:
            result.append(data[:size])
            data = data[size:]
        return result


# ===================================================================================
# Timeout Class
# ===================================================================================

# Simple timeout helper in milliseconds.
class Timeout:
    def __init__(self, timeout_ms):
        self.timeout_ms = timeout_ms
        self.start_time = time.time()

    def expired(self):
        return time.time() - self.start_time > self.timeout_ms / 1000.0


# ===================================================================================
# Error Class - Raise an Error
# ===================================================================================

class PrgError(Exception):
    def __init__(self, msg='Something went wrong'):
        super(PrgError, self).__init__(msg)
        sys.stderr.write('ERROR: ' + msg + '\n')
        sys.exit(1)


# ===================================================================================
# Device Definitions and Functions
# ===================================================================================

# Get list of supported device names
def get_supported_devices():
    result = list()
    for d in UPDI_DEVICES:
        result.append(d['name'])
    return result

# Device definitions
UPDI_DEVICES = [
    {'name': 'attiny202',  'device_id': 0x1E9123, 'flash_size': 0x0800, 'flash_pagesize': 0x40},
    {'name': 'attiny402',  'device_id': 0x1E9227, 'flash_size': 0x1000, 'flash_pagesize': 0x40},
    {'name': 'attiny212',  'device_id': 0x1E9121, 'flash_size': 0x0800, 'flash_pagesize': 0x40},
    {'name': 'attiny412',  'device_id': 0x1E9223, 'flash_size': 0x1000, 'flash_pagesize': 0x40},
    {'name': 'attiny204',  'device_id': 0x1E9122, 'flash_size': 0x0800, 'flash_pagesize': 0x40},
    {'name': 'attiny404',  'device_id': 0x1E9226, 'flash_size': 0x1000, 'flash_pagesize': 0x40},
    {'name': 'attiny804',  'device_id': 0x1E9325, 'flash_size': 0x2000, 'flash_pagesize': 0x40},
    {'name': 'attiny1604', 'device_id': 0x1E9425, 'flash_size': 0x4000, 'flash_pagesize': 0x40},
    {'name': 'attiny214',  'device_id': 0x1E9120, 'flash_size': 0x0800, 'flash_pagesize': 0x40},
    {'name': 'attiny414',  'device_id': 0x1E9222, 'flash_size': 0x1000, 'flash_pagesize': 0x40},
    {'name': 'attiny814',  'device_id': 0x1E9322, 'flash_size': 0x2000, 'flash_pagesize': 0x40},
    {'name': 'attiny1614', 'device_id': 0x1E9422, 'flash_size': 0x4000, 'flash_pagesize': 0x40},
    {'name': 'attiny424',  'device_id': 0x1E922C, 'flash_size': 0x1000, 'flash_pagesize': 0x40},
    {'name': 'attiny824',  'device_id': 0x1E9329, 'flash_size': 0x2000, 'flash_pagesize': 0x40},
    {'name': 'attiny1624', 'device_id': 0x1E942A, 'flash_size': 0x4000, 'flash_pagesize': 0x40},
    {'name': 'attiny3224', 'device_id': 0x1E9528, 'flash_size': 0x8000, 'flash_pagesize': 0x80},
    {'name': 'attiny406',  'device_id': 0x1E9225, 'flash_size': 0x1000, 'flash_pagesize': 0x40},
    {'name': 'attiny806',  'device_id': 0x1E9324, 'flash_size': 0x2000, 'flash_pagesize': 0x40},
    {'name': 'attiny1606', 'device_id': 0x1E9424, 'flash_size': 0x4000, 'flash_pagesize': 0x40},
    {'name': 'attiny416',  'device_id': 0x1E9221, 'flash_size': 0x1000, 'flash_pagesize': 0x40},
    {'name': 'attiny816',  'device_id': 0x1E9321, 'flash_size': 0x2000, 'flash_pagesize': 0x40},
    {'name': 'attiny1616', 'device_id': 0x1E9421, 'flash_size': 0x4000, 'flash_pagesize': 0x40},
    {'name': 'attiny3216', 'device_id': 0x1E9521, 'flash_size': 0x8000, 'flash_pagesize': 0x80},
    {'name': 'attiny426',  'device_id': 0x1E922B, 'flash_size': 0x1000, 'flash_pagesize': 0x40},
    {'name': 'attiny826',  'device_id': 0x1E9328, 'flash_size': 0x2000, 'flash_pagesize': 0x40},
    {'name': 'attiny1626', 'device_id': 0x1E9429, 'flash_size': 0x4000, 'flash_pagesize': 0x40},
    {'name': 'attiny3226', 'device_id': 0x1E9527, 'flash_size': 0x8000, 'flash_pagesize': 0x80},
    {'name': 'attiny417',  'device_id': 0x1E9220, 'flash_size': 0x1000, 'flash_pagesize': 0x40},
    {'name': 'attiny427',  'device_id': 0x1E922A, 'flash_size': 0x1000, 'flash_pagesize': 0x40},
    {'name': 'attiny807',  'device_id': 0x1E9323, 'flash_size': 0x2000, 'flash_pagesize': 0x40},
    {'name': 'attiny817',  'device_id': 0x1E9320, 'flash_size': 0x2000, 'flash_pagesize': 0x40},
    {'name': 'attiny827',  'device_id': 0x1E9327, 'flash_size': 0x2000, 'flash_pagesize': 0x40},
    {'name': 'attiny1607', 'device_id': 0x1E9423, 'flash_size': 0x4000, 'flash_pagesize': 0x40},
    {'name': 'attiny1617', 'device_id': 0x1E9420, 'flash_size': 0x4000, 'flash_pagesize': 0x40},
    {'name': 'attiny1627', 'device_id': 0x1E9428, 'flash_size': 0x4000, 'flash_pagesize': 0x40},
    {'name': 'attiny3217', 'device_id': 0x1E9522, 'flash_size': 0x8000, 'flash_pagesize': 0x80},
    {'name': 'attiny3227', 'device_id': 0x1E9526, 'flash_size': 0x8000, 'flash_pagesize': 0x80}
]


# ===================================================================================
# UPDI Protocol Constants
# ===================================================================================

UPDI_BREAK = 0x00
UPDI_LDS = 0x00
UPDI_STS = 0x40
UPDI_LD = 0x20
UPDI_ST = 0x60
UPDI_LDCS = 0x80
UPDI_STCS = 0xC0
UPDI_REPEAT = 0xA0
UPDI_KEY = 0xE0
UPDI_PTR = 0x00
UPDI_PTR_INC = 0x04
UPDI_PTR_ADDRESS = 0x08
UPDI_ADDRESS_8 = 0x00
UPDI_ADDRESS_16 = 0x04
UPDI_ADDRESS_24 = 0x08
UPDI_DATA_8 = 0x00
UPDI_DATA_16 = 0x01
UPDI_DATA_24 = 0x02

UPDI_PHY_SYNC = 0x55
UPDI_PHY_ACK = 0x40
UPDI_REPEAT_BYTE = 0x00
UPDI_REPEAT_WORD = 0x01
UPDI_CS_STATUSA = 0x00
UPDI_CS_STATUSB = 0x01
UPDI_CS_CTRLA = 0x02
UPDI_CS_CTRLB = 0x03
UPDI_CTRLA_RSD_BIT = 3
UPDI_CTRLA_IBDLY_BIT = 7
UPDI_CTRLB_CCDETDIS_BIT = 3
UPDI_CTRLB_UPDIDIS_BIT = 2
UPDI_ASI_KEY_STATUS = 0x07
UPDI_ASI_RESET_REQ = 0x08
UPDI_ASI_CTRLA = 0x09
UPDI_ASI_SYS_CTRLA = 0x0A
UPDI_ASI_SYS_STATUS = 0x0B
UPDI_ASI_CRC_STATUS = 0x0C
UPDI_ASI_STATUSA_REVID = 4
UPDI_ASI_STATUSB_PESIG = 0
UPDI_ASI_KEY_STATUS_CHIPERASE = 3
UPDI_ASI_KEY_STATUS_NVMPROG = 4
UPDI_ASI_KEY_STATUS_UROWWRITE = 5
UPDI_ASI_SYS_STATUS_RSTSYS = 5
UPDI_ASI_SYS_STATUS_INSLEEP = 4
UPDI_ASI_SYS_STATUS_NVMPROG = 3
UPDI_ASI_SYS_STATUS_UROWPROG = 2
UPDI_ASI_SYS_STATUS_LOCKSTATUS = 0
UPDI_ASI_SYS_CTRLA_UROW_FINAL = 1
UPDI_RESET_REQ_VALUE = 0x59
UPDI_MAX_REPEAT_SIZE = (0xFF+1)

UPDI_KEY_SIB = 0x04
UPDI_KEY_KEY = 0x00
UPDI_KEY_64 = 0x00
UPDI_KEY_128 = 0x01
UPDI_KEY_256 = 0x02
UPDI_KEY_NVM = b'NVMProg '
UPDI_KEY_CHIPERASE = b'NVMErase'
UPDI_KEY_UROW = b'NVMUs&te'
UPDI_SIB_8BYTES = UPDI_KEY_64
UPDI_SIB_16BYTES = UPDI_KEY_128
UPDI_SIB_32BYTES = UPDI_KEY_256

UPDI_NVMCTRL_CTRLA = 0x00
UPDI_NVMCTRL_CTRLB = 0x01
UPDI_NVMCTRL_STATUS = 0x02
UPDI_NVMCTRL_INTCTRL = 0x03
UPDI_NVMCTRL_INTFLAGS = 0x04
UPDI_NVMCTRL_DATAL = 0x06
UPDI_NVMCTRL_DATAH = 0x07
UPDI_NVMCTRL_ADDRL = 0x08
UPDI_NVMCTRL_ADDRH = 0x09

UPDI_V0_NVMCTRL_CTRLA_NOP = 0x00
UPDI_V0_NVMCTRL_CTRLA_WRITE_PAGE = 0x01
UPDI_V0_NVMCTRL_CTRLA_ERASE_PAGE = 0x02
UPDI_V0_NVMCTRL_CTRLA_ERASE_WRITE_PAGE = 0x03
UPDI_V0_NVMCTRL_CTRLA_PAGE_BUFFER_CLR = 0x04
UPDI_V0_NVMCTRL_CTRLA_CHIP_ERASE = 0x05
UPDI_V0_NVMCTRL_CTRLA_ERASE_EEPROM = 0x06
UPDI_V0_NVMCTRL_CTRLA_WRITE_FUSE = 0x07

UPDI_NVM_STATUS_WRITE_ERROR = 2
UPDI_NVM_STATUS_EEPROM_BUSY = 1
UPDI_NVM_STATUS_FLASH_BUSY = 0


# ===================================================================================

if __name__ == "__main__":
    _main()
