#!/usr/bin/env python3
# ===================================================================================
# Project:   megaUPDI - Simple serial UPDI programmer for all AVR microcontrollers
#                       with UPDI interface (based on TinyUPDI)
# Version:   v1.0
# Year:      2026
# Author:    Stefan Wagner
# Github:    https://github.com/wagiminator
# License:   MIT License
# ===================================================================================
#
# Description:
# ------------
# megaUPDI is a simple serial UPDI programmer software for all AVR microcontrollers
# with UPDI programming interface. It uses a USB-to-serial adapter (e.g. CH340,
# CP2102, FT232R) with a resistor (or a diode) between RX and TX that is connected
# to the UPDI pin of the target MCU. megaUPDI is an extension of TinyUPDI that is
# reduced to the functions needed to upload firmware and to set fuses.
#
# Supported microcontrollers (133 devices):
# -----------------------------------------
# - tinyAVR 0-series:  ATtiny202/204/402/404/406/804/806/807/1604/1606/1607
# - tinyAVR 1-series:  ATtiny212/214/412/414/416/416auto/417/814/816/817/
#                      1614/1616/1617/3216/3217
# - tinyAVR 2-series:  ATtiny424/426/427/824/826/827/1624/1626/1627/3224/3226/3227
# - megaAVR 0-series:  ATmega808/809/1608/1609/3208/3209/4808/4809
# - AVR DA (and DA-S): AVR32DA28/32/48, AVR64DA28/32/48/64, AVR128DA28/32/48/64
#                      (also with suffix S)
# - AVR DB:            AVR32DB28/32/48, AVR64DB28/32/48/64, AVR128DB28/32/48/64
# - AVR DD:            AVR16DD14/20/28/32, AVR32DD14/20/28/32, AVR64DD14/20/28/32
# - AVR DU:            AVR16DU14/20/28/32, AVR32DU14/20/28/32, AVR64DU28/32
# - AVR EA:            AVR8EA28/32, AVR16EA28/32/48, AVR32EA28/32/48, AVR64EA28/32/48
# - AVR EB:            AVR16EB14/20/28/32, AVR32EB14/20/28/32
# - AVR EC:            AVR64EC28/48
# - AVR LA:            AVR16LA14/20/28/32, AVR32LA14/20/28/32
# - AVR SD:            AVR32SD20/28/32
#
# References:
# -----------
# megaUPDI is based on TinyUPDI, pyupdi, pymcuprog and the serialupdi programmer
# of AVRDUDE (device data and NVM controller variants):
# - https://github.com/wagiminator/MCU-Flash-Tools
# - https://github.com/mraardvark/pyupdi
# - https://github.com/microchip-pic-avr-tools/pymcuprog
# - https://github.com/avrdudes/avrdude
#
# Dependencies:
# -------------
# - pyserial
#
# Restrictions:
# -------------
# - Only flash and fuses can be programmed (no EEPROM, user row, boot row, lock bits
#   of the AVR Dx/Ex/Lx/Sx families).
# - Firmware file must be a binary (not ELF or HEX!).
# - High-voltage UPDI activation is not supported.
#
# Operating Instructions:
# -----------------------
# - python3 megaupdi.py [-h] [-p PORT] [-d DEVICE] [-e] [-f FLASH] [-fs [FUSES ...]] [-t TRIM] [-l]
#   -h, --help                show help message and exit
#   -p, --port                serial port (if not set, it will be auto-detected)
#   -d, --device              set target device (if not set, it will be auto-detected)
#   -e, --erase               perform a chip erase (implied with --flash)
#   -f FLASH, --flash FLASH   BIN file to flash
#   -fs [FUSES ...], --fuses [FUSES ...]
#                             fuses to set (syntax: fuse_nr:0xvalue)
#   -t TRIM, --trim TRIM      configure oscillator for given frequency (fuse 2)
#   -l, --list                list supported devices
# - Example:
#   python3 megaupdi.py -f firmware.bin
#   python3 megaupdi.py -d avr128da28 -f firmware.bin -fs 0:0x00 1:0x00
#   python3 megaupdi.py -d attiny202 -f firmware.bin -fs 6:0x04 7:0x00 8:0x00 -t 8000000


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
                                     ' interface for UPDI programming of AVR microcontrollers')
    parser.add_argument('-p', '--port', help='serial port (if not set, it will be auto-detected)')
    parser.add_argument('-d', '--device',
                        help='target device (if not set, it will be auto-detected), see --list')
    parser.add_argument("-e", "--erase", action="store_true",
                        help="perform a chip erase (implied with --flash)")
    parser.add_argument('-f', '--flash', help='BIN file to flash')
    parser.add_argument('-fs', '--fuses', action='append', nargs='*',
                        help='fuses to set (syntax: fuse_nr:0xvalue)')
    parser.add_argument('-t', '--trim', type=int, help='configure oscillator for given frequency (fuse 2)')
    parser.add_argument('-l', '--list', action='store_true', help='list supported devices')
    args = parser.parse_args(sys.argv[1:])

    # List supported devices
    if args.list:
        for family in UPDI_FAMILIES:
            names = [d['name'] for d in UPDI_DEVICES if d['family'] == family]
            print('%-11s %s' % (family + ':', ', '.join(names)))
        sys.exit(0)

    # Check arguments
    if not any( (args.fuses, args.flash, args.erase, args.trim) ):
        print('No arguments - no action!')
        sys.exit(0)

    if args.device is not None:
        args.device = args.device.lower()
        if args.device not in get_supported_devices():
            sys.stderr.write('ERROR: Unsupported device %s (see --list)\n' % args.device)
            sys.exit(1)

    fuselist = list()
    if args.fuses is not None:
        for fslist in args.fuses:
            for fsarg in fslist:
                if not re.match('^[0-9]+:0x[0-9a-fA-F]+$', fsarg):
                    sys.stderr.write('ERROR: Bad fuses format {}. Expected fuse_nr:0xvalue\n'.format(fsarg))
                    sys.exit(1)
                lst = fsarg.split(':0x')
                fusenum, value = int(lst[0]), int(lst[1], 16)
                if fusenum > UPDI_MAX_FUSE or value > 0xFF:
                    sys.stderr.write('ERROR: Bad fuse {}. Fuse number must be 0 - {}, value 0x00 - 0xff\n'.format(fsarg, UPDI_MAX_FUSE))
                    sys.exit(1)
                fuselist.append( (fusenum, value) )

    if args.trim is not None and get_oscillator(args.trim) is None:
        sys.stderr.write('ERROR: Unsupported frequency {} Hz for -t\n'.format(args.trim))
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

    # Establish connection via serial to UPDI device
    try:
        print('Connecting to device ...')
        megaupdi = Programmer(args.port)
    except Exception as ex:
        sys.stderr.write('ERROR: ' + str(ex) + '!\n')
        sys.exit(1)
    print('SUCCESS: Found %s (NVM P:%s) on port %s.' % (megaupdi.sib_family, megaupdi.nvm_version, megaupdi.port))

    # Programming the device
    try:
        # Unlock device (chip erase by key) if necessary
        if megaupdi.locked:
            if not ((args.erase) or (data is not None)):
                raise Exception('Device is locked, use -e or -f to unlock it (erases the chip)')
            print('Device is locked, unlocking with chip erase ...')
            megaupdi.unlock()
            print('SUCCESS: Device is unlocked.')

        # Detect target device
        print('Detecting target MCU ...')
        device = megaupdi.detect()
        print('SUCCESS: Found %s with %d bytes of flash.' % (device, megaupdi.flash_size))
        if (args.device is not None) and (not args.device == device):
            raise Exception('Found device is not ' + args.device)

        # Check everything device-specific before anything is erased or written
        if (data is not None) and (len(data) > megaupdi.flash_size):
            raise Exception('Not enough memory (file: %d bytes, flash: %d bytes)' % (len(data), megaupdi.flash_size))
        for fuse in fuselist:
            megaupdi.check_fuse(fuse[0], fuse[1])
        if args.trim is not None:
            megaupdi.check_trim(args.trim)

        # Perform chip erase
        if (args.erase) or (data is not None):
            print('Performing chip erase ...')
            megaupdi.erase()

        # Flash binary file
        if data is not None:
            print('Flashing %s to %s ...' % (args.flash, device))
            megaupdi.flash_data(data)
            print('Verifying ...')
            megaupdi.verify_data(data)
            print('SUCCESS: %d bytes written and verified.' % len(data))

        # Write fuses
        if fuselist:
            print('Writing fuses ...')
            for fuse in fuselist:
                megaupdi.set_fuse(fuse[0], fuse[1])
            print('Verifying fuses ...')
            for fuse in fuselist:
                megaupdi.verify_fuse(fuse[0], fuse[1])
            print('SUCCESS: Fuses written and verified.')

        # Write fuse to set oscillator according to frequency
        if args.trim is not None:
            print('Setting oscillator for %s Hz ...' % args.trim)
            osc = megaupdi.trim(args.trim)
            print('SUCCESS: Oscillator runs at %d MHz with corresponding factory calibration.' % osc)

    except Exception as ex:
        sys.stderr.write('ERROR: ' + str(ex) + '!\n')
        try:
            megaupdi.exit()
        except:
            pass
        sys.exit(1)

    # Finish all up
    megaupdi.exit()
    print('DONE.')
    sys.exit(0)


# ===================================================================================
# Programmer Class
# ===================================================================================

class Programmer(Serial):
    def __init__(self, port=None):
        super().__init__(baudrate = 230400, timeout = 1, parity=serial.PARITY_EVEN, stopbits=serial.STOPBITS_TWO)
        self.syscfg_address  = 0x0F00
        self.nvmctrl_address = 0x1000
        self.sigrow_address  = 0x1100
        self.fuses_address   = 0x1280
        self.flash_start     = 0x8000
        self.flash_size      = 0x0800
        self.flash_pagesize  = 64
        self.family          = None
        self.sib_family      = ''
        self.nvm_version     = '0'
        self.addr24          = False
        self.locked          = False
        self.identify(port)

    # Identify port of programmer, read SIB and enter programming mode
    def identify(self, port=None):
        if port is not None:
            ports = [port]
        else:
            ports = [p.device for p in comports()
                     if (('VID' not in globals()) or (VID in p.hwid)) and (('PID' not in globals()) or (PID in p.hwid))]
        for device in ports:
            self.port = device
            try:
                self.open()
            except:
                continue
            self.__send_double_break()
            self.__init()
            if not self.__check():
                self.close()
                continue
            if self.__ldcs(UPDI_ASI_SYS_STATUS) & (1 << UPDI_ASI_SYS_STATUS_RSTSYS):
                self.__reset(apply_reset=False)
            sib = self.__read_sib()
            if sib is None:
                self.close()
                continue
            self.sib_family  = sib[0:7].strip()
            self.nvm_version = sib[10]
            if self.nvm_version not in UPDI_NVM_PARAMS:
                self.close()
                raise Exception('Unsupported NVM controller version P:%s (SIB: %s)' % (self.nvm_version, sib.strip()))
            self.addr24 = self.nvm_version != '0'
            try:
                self.__enter_progmode()
            except LockedError:
                self.locked = True
            return
        if port is not None:
            raise Exception('No UPDI device found on port %s' % port)
        raise Exception('Device not found')


    # ------------------------------------------------------------------------------
    # High-Level Functions
    # ------------------------------------------------------------------------------

    # Detect device by its signature (the address of the signature row depends on the family)
    def detect(self):
        candidates = [0x1100, 0x1080] if self.nvm_version in '023' else [0x1080, 0x1100]
        ids = list()
        for address in candidates:
            deviceid = int.from_bytes(self.__read_data(address, 3), byteorder='big')
            ids.append(deviceid)
            for dev in UPDI_DEVICES:
                family = UPDI_FAMILIES[dev['family']]
                if dev['device_id'] == deviceid and family['sigrow'] == address:
                    self.family         = family
                    self.sigrow_address = address
                    self.fuses_address  = family['fuses']
                    self.flash_start    = family['flash_start']
                    self.flash_size     = dev['flash_size']
                    self.flash_pagesize = dev['flash_pagesize']
                    return dev['name']
        raise Exception('Unknown or unsupported device (ID 0x%06X)' % ids[0])

    # Unlock device by chip erase and enter programming mode
    def unlock(self):
        self.__unlock()
        self.__init()
        self.__enter_progmode()
        self.locked = False

    # Disable UPDI and serial connection
    def exit(self):
        self.__reset(apply_reset=True)
        self.__reset(apply_reset=False)
        self.__stcs(UPDI_CS_CTRLB, (1 << UPDI_CTRLB_UPDIDIS_BIT) | (1 << UPDI_CTRLB_CCDETDIS_BIT))
        self.close()

    # Does a chip erase using the NVM controller
    def erase(self):
        self.__wait_nvm_ready('before chip erase')
        if self.nvm_version == '0':
            self.__execute_nvm_command(UPDI_V0_NVMCTRL_CTRLA_CHIP_ERASE)
            self.__wait_nvm_ready('after chip erase')
        else:
            self.__execute_nvm_command(UPDI_NVMCTRL_CTRLA_CHIP_ERASE)
            self.__wait_nvm_ready('after chip erase', clear=True)

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

    # Check fuse number and value for the detected device (prints warnings)
    def check_fuse(self, fusenum, value):
        if fusenum not in self.family['fuselist']:
            raise Exception('Fuse %d does not exist on this device (valid: %s)' %
                            (fusenum, ', '.join(str(x) for x in self.family['fuselist'])))
        pin = self.family['updipin']
        if pin is not None and fusenum == pin[0] and ((value & pin[1]) >> pin[2]) not in pin[3]:
            print('WARNING: Fuse %d disables the UPDI pin, further programming requires a HV programmer!' % fusenum)
        if self.nvm_version == '0' and fusenum == UPDI_V0_FUSE_LOCKBIT and value != UPDI_V0_LOCKBIT_UNLOCKED:
            print('WARNING: Fuse %d (LOCKBIT) locks the device, unlocking requires a chip erase!' % fusenum)

    # Set single fuse
    def set_fuse(self, fusenum, value):
        self.__write_fuse(self.fuses_address + fusenum, value)

    # Verify single fuse
    def verify_fuse(self, fusenum, value):
        actual_val = self.__read_fuse(self.fuses_address + fusenum)
        if actual_val != value:
            raise Exception('Fuse ' + str(fusenum) + ' verification failure')

    # Check whether the oscillator of the detected device can be set for given frequency
    def check_trim(self, freq):
        osc = get_oscillator(freq)
        if osc is None:
            raise Exception('Unsupported frequency')
        if self.family['osc'] is None:
            raise Exception('Oscillator frequency cannot be selected by fuse on this device (-t)')
        if osc not in self.family['osc'][3]:
            raise Exception('%d MHz oscillator is not available on this device' % osc)
        return osc

    # Configure oscillator for given system frequency
    def trim(self, freq):
        osc = self.check_trim(freq)
        fusenum, mask, shift, values = self.family['osc']
        value = (self.__read_fuse(self.fuses_address + fusenum) & ~mask & 0xFF) | (values[osc] << shift)
        self.set_fuse(fusenum, value)
        self.verify_fuse(fusenum, value)
        return osc


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
    # Datalink Layer for UPDI Stack (16-bit or 24-bit addresses)
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

    # Address bytes and size flags for the current address mode
    def __addr(self, address):
        if self.addr24:
            return [address & 0xFF, (address >> 8) & 0xFF, (address >> 16) & 0xFF]
        return [address & 0xFF, (address >> 8) & 0xFF]

    def __asize(self):
        return UPDI_ADDRESS_24 if self.addr24 else UPDI_ADDRESS_16

    # Wait for ACK
    def __ack(self, name):
        response = self.__receive(1)
        if len(response) != 1 or response[0] != UPDI_PHY_ACK:
            raise Exception('Failed to communicate with device (%s)' % name)

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

    # Load a single byte direct from an address
    def __ld(self, address):
        self.__send([UPDI_PHY_SYNC, UPDI_LDS | self.__asize() | UPDI_DATA_8] + self.__addr(address))
        response = self.__receive(1)
        if len(response) != 1:
            raise Exception('Failed to communicate with device (ld)')
        return response[0]

    # Store a single byte value directly to an address
    def __st(self, address, value):
        self.__send([UPDI_PHY_SYNC, UPDI_STS | self.__asize() | UPDI_DATA_8] + self.__addr(address))
        self.__ack('st')
        self.__send([value & 0xFF])
        self.__ack('st')

    # Store a 16-bit word value directly to an address
    def __st16(self, address, value):
        self.__send([UPDI_PHY_SYNC, UPDI_STS | self.__asize() | UPDI_DATA_16] + self.__addr(address))
        self.__ack('st16')
        self.__send([value & 0xFF, (value >> 8) & 0xFF])
        self.__ack('st16')

    # Load a number of bytes from the pointer location with pointer post-increment
    def __ld_ptr_inc(self, size):
        self.__send([UPDI_PHY_SYNC, UPDI_LD | UPDI_PTR_INC | UPDI_DATA_8])
        response = self.__receive(size)
        if len(response) != size:
            raise Exception('Failed to communicate with device (ld_ptr_inc)')
        return response

    # Load a 16-bit word value from the pointer location with pointer post-increment
    def __ld_ptr_inc16(self, words):
        self.__send([UPDI_PHY_SYNC, UPDI_LD | UPDI_PTR_INC | UPDI_DATA_16])
        response = self.__receive(words << 1)
        if len(response) != words << 1:
            raise Exception('Failed to communicate with device (ld_ptr_inc16)')
        return response

    # Set the pointer location
    def __st_ptr(self, address):
        self.__send([UPDI_PHY_SYNC, UPDI_ST | UPDI_PTR_ADDRESS | (UPDI_DATA_24 if self.addr24 else UPDI_DATA_16)]
                    + self.__addr(address))
        self.__ack('st_ptr')

    # Store a 16-bit word value to the pointer location with pointer post-increment
    # (ACKs are disabled for the block, response signature disabled)
    def __st_ptr_inc16(self, data):
        ctrla_ackon = 1 << UPDI_CTRLA_IBDLY_BIT
        ctrla_ackoff = ctrla_ackon | (1 << UPDI_CTRLA_RSD_BIT)
        self.__stcs(UPDI_CS_CTRLA, ctrla_ackoff)
        self.__send([UPDI_PHY_SYNC, UPDI_ST | UPDI_PTR_INC | UPDI_DATA_16] )
        self.__send(data)
        self.__stcs(UPDI_CS_CTRLA, ctrla_ackon)

    # Store a value to the repeat counter
    def __repeat(self, repeats):
        if repeats < 1 or repeats > UPDI_MAX_REPEAT_SIZE:
            raise Exception('Invalid repeat count')
        repeats -= 1
        self.__send([UPDI_PHY_SYNC, UPDI_REPEAT | UPDI_REPEAT_BYTE, repeats & 0xFF])

    # Write a key
    def __key(self, size, key):
        if len(key) != 8 << size:
            raise Exception('Invalid Key length')
        self.__send([UPDI_PHY_SYNC, UPDI_KEY | UPDI_KEY_KEY | size])
        self.__send(list(reversed(list(key))))

    # Read the System Information Block (SIB), returns string or None
    def __read_sib(self):
        self.__send([UPDI_PHY_SYNC, UPDI_KEY | UPDI_KEY_SIB | UPDI_SIB_32BYTES])
        response = self.__receive(32)
        try:
            sib = response.decode('ascii')
        except UnicodeDecodeError:
            return None
        if len(sib) < 19 or sib[8:10] != 'P:':
            return None
        return sib


    # ------------------------------------------------------------------------------
    # Application Layer for UPDI Stack
    # ------------------------------------------------------------------------------

    # Enter NVM programming mode
    def __enter_progmode(self):
        if self.__in_prog_mode():
            return
        self.__reset(apply_reset=True)
        self.__key(UPDI_KEY_64, UPDI_KEY_NVM)
        key_status = self.__ldcs(UPDI_ASI_KEY_STATUS)
        if not key_status & (1 << UPDI_ASI_KEY_STATUS_NVMPROG):
            self.__reset(apply_reset=False)
            raise Exception('Key not accepted')
        self.__reset(apply_reset=True)
        self.__reset(apply_reset=False)
        if not self.__wait_unlocked(100):
            raise LockedError('Failed to enter NVM programming mode: device is locked')
        timeout = Timeout(500)
        while not self.__in_prog_mode():
            if timeout.expired():
                raise Exception('Failed to enter NVM programming mode')

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

    # Wait for the NVM controller to be ready, optionally remove command afterwards
    def __wait_nvm_ready(self, when, clear=False):
        status_reg, error_mask = UPDI_NVM_PARAMS[self.nvm_version]
        timeout = Timeout(10000)
        result = None
        while not timeout.expired():
            status = self.__ld(self.nvmctrl_address + status_reg)
            if status & error_mask:
                result = 'NVM controller error (STATUS 0x%02X) %s' % (status, when)
                break
            if not status & UPDI_NVM_STATUS_BUSY_MASK:
                break
        else:
            result = 'Timeout waiting for NVM controller %s' % when
        if clear:
            self.__execute_nvm_command(UPDI_NVMCTRL_CTRLA_NOCMD)
        if result is not None:
            raise Exception(result)

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

    # Write a page of data to flash (NVM controller variant according to SIB)
    def __write_page(self, address, data):
        v = self.nvm_version
        if v == '0':                                    # tinyAVR, megaAVR 0: page buffer
            self.__wait_nvm_ready('before page buffer clear')
            self.__execute_nvm_command(UPDI_V0_NVMCTRL_CTRLA_PAGE_BUFFER_CLR)
            self.__wait_nvm_ready('after page buffer clear')
            self.__write_data_words(address, data)
            self.__execute_nvm_command(UPDI_V0_NVMCTRL_CTRLA_WRITE_PAGE)
            self.__wait_nvm_ready('after page write')
        elif v in UPDI_NVM_PAGE_ORIENTED:               # AVR EA, EB, ...: page buffer
            self.__wait_nvm_ready('before page buffer clear')
            self.__execute_nvm_command(UPDI_NVMCTRL_CTRLA_FLASH_PAGE_BUFFER_CLEAR)
            self.__wait_nvm_ready('after page buffer clear')
            self.__write_data_words(address, data)
            self.__execute_nvm_command(UPDI_NVMCTRL_CTRLA_FLASH_PAGE_WRITE)
            self.__wait_nvm_ready('after page write', clear=True)
        else:                                           # AVR DA, DB, DD, DU, ...: word write
            self.__wait_nvm_ready('before flash write')
            self.__execute_nvm_command(UPDI_NVMCTRL_CTRLA_FLASH_WRITE)
            self.__write_data_words(address, data)
            self.__wait_nvm_ready('after flash write', clear=True)

    # Write one fuse value (NVM controller variant according to SIB)
    def __write_fuse(self, address, value):
        v = self.nvm_version
        if v == '0':                                    # fuses are written by command
            self.__wait_nvm_ready('before fuse write')
            self.__st(self.nvmctrl_address + UPDI_V0_NVMCTRL_ADDRL, address & 0xFF)
            self.__st(self.nvmctrl_address + UPDI_V0_NVMCTRL_ADDRH, (address >> 8) & 0xFF)
            self.__st(self.nvmctrl_address + UPDI_V0_NVMCTRL_DATAL, value & 0xFF)
            self.__execute_nvm_command(UPDI_V0_NVMCTRL_CTRLA_WRITE_FUSE)
            self.__wait_nvm_ready('after fuse write')
        elif v in UPDI_NVM_PAGE_ORIENTED:               # fuses are EEPROM-based (page buffer)
            self.__wait_nvm_ready('before fuse write')
            self.__execute_nvm_command(UPDI_NVMCTRL_CTRLA_EEPROM_PAGE_BUFFER_CLEAR)
            self.__wait_nvm_ready('after page buffer clear')
            self.__st(address, value)
            self.__execute_nvm_command(UPDI_NVMCTRL_CTRLA_EEPROM_PAGE_ERASE_WRITE)
            self.__wait_nvm_ready('after fuse write', clear=True)
        else:                                           # fuses are EEPROM-based
            self.__wait_nvm_ready('before fuse write')
            self.__execute_nvm_command(UPDI_NVMCTRL_CTRLA_EEPROM_ERASE_WRITE)
            self.__st(address, value)
            self.__wait_nvm_ready('after fuse write', clear=True)

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

    # Read from flash (in blocks of max. 256 bytes)
    def __read_flash(self, address, size):
        data = bytearray()
        end = address + size
        while address < end:
            words = min(UPDI_READ_BLOCK_SIZE, end - address + 1) >> 1
            data += self.__read_data_words(address, words)
            address += words << 1
        return bytes(data[:size])

    # Write to flash
    def __write_flash(self, address, data):
        data = self.__pad_data(data, self.flash_pagesize)
        pages = self.__page_data(data, self.flash_pagesize)
        for page in pages:
            self.__write_page(address, page)
            address += len(page)

    # Read one fuse value
    def __read_fuse(self, address):
        return self.__ld(address)

    # Pad data so that there are full pages
    def __pad_data(self, data, blocksize):
        if len(data) % blocksize:
            data = bytes(data) + b'\xFF' * (blocksize - len(data) % blocksize)
        return data

    # Divide data into pages
    def __page_data(self, data, size):
        return [data[i:i + size] for i in range(0, len(data), size)]


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
# Error Class
# ===================================================================================

# Device is locked
class LockedError(Exception):
    pass


# ===================================================================================
# Device Definitions and Functions
# ===================================================================================

# Get oscillator (16 or 20 MHz) for given system frequency (with prescaler)
def get_oscillator(freq):
    for x in [1, 2, 4, 8, 16, 32, 64, 6, 10, 12, 24, 48]:
        if round(20000000 / x) == freq:
            return 20
        if round(16000000 / x) == freq:
            return 16
    return None

# Get list of supported device names
def get_supported_devices():
    result = list()
    for d in UPDI_DEVICES:
        result.append(d['name'])
    return result

# Device families (generated from avrdude.conf and avrintel.c of AVRDUDE v8.3):
# - flash_start: address of the flash in the data space
# - sigrow:      address of the signature row (device ID)
# - fuses:       address of fuse 0
# - fuselist:    valid fuse numbers for -fs
# - osc:         (fuse, mask, shift, {MHz: value}) for -t, None if not available
# - updipin:     (fuse, mask, shift, (values with UPDI enabled)), None if UPDI pin is fixed
UPDI_FAMILIES = {
    'tiny0':      {'flash_start': 0x008000, 'sigrow': 0x1100, 'fuses': 0x1280, 'fuselist': (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10), 'osc': (2, 0x03, 0, {16: 1, 20: 2}), 'updipin': (5, 0x0C, 2, (1,))},
    'tiny1':      {'flash_start': 0x008000, 'sigrow': 0x1100, 'fuses': 0x1280, 'fuselist': (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10), 'osc': (2, 0x03, 0, {16: 1, 20: 2}), 'updipin': (5, 0x0C, 2, (1,))},
    'tiny1-auto': {'flash_start': 0x008000, 'sigrow': 0x1100, 'fuses': 0x1280, 'fuselist': (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10), 'osc': (2, 0x03, 0, {16: 1}), 'updipin': (5, 0x0C, 2, (1,))},
    'tiny2':      {'flash_start': 0x008000, 'sigrow': 0x1100, 'fuses': 0x1280, 'fuselist': (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10), 'osc': (2, 0x03, 0, {16: 1, 20: 2}), 'updipin': (5, 0x0C, 2, (1, 3,))},
    'mega0':      {'flash_start': 0x004000, 'sigrow': 0x1100, 'fuses': 0x1280, 'fuselist': (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10), 'osc': (2, 0x03, 0, {16: 1, 20: 2}), 'updipin': None},
    'DA':         {'flash_start': 0x800000, 'sigrow': 0x1100, 'fuses': 0x1050, 'fuselist': (0, 1, 2, 5, 6, 7, 8), 'osc': None, 'updipin': None},
    'DA-S':       {'flash_start': 0x800000, 'sigrow': 0x1100, 'fuses': 0x1050, 'fuselist': (0, 1, 2, 5, 6, 7, 8, 10), 'osc': None, 'updipin': None},
    'DB':         {'flash_start': 0x800000, 'sigrow': 0x1100, 'fuses': 0x1050, 'fuselist': (0, 1, 2, 5, 6, 7, 8), 'osc': None, 'updipin': None},
    'DD':         {'flash_start': 0x800000, 'sigrow': 0x1100, 'fuses': 0x1050, 'fuselist': (0, 1, 2, 5, 6, 7, 8), 'osc': None, 'updipin': (5, 0x10, 4, (1,))},
    'DU':         {'flash_start': 0x800000, 'sigrow': 0x1080, 'fuses': 0x1050, 'fuselist': (0, 1, 2, 5, 6, 7, 8, 10), 'osc': None, 'updipin': (5, 0x10, 4, (1,))},
    'EA':         {'flash_start': 0x800000, 'sigrow': 0x1100, 'fuses': 0x1050, 'fuselist': (0, 1, 2, 5, 6, 7, 8), 'osc': (2, 0x08, 3, {16: 1, 20: 0}), 'updipin': (5, 0x10, 4, (1,))},
    'EB':         {'flash_start': 0x800000, 'sigrow': 0x1080, 'fuses': 0x1050, 'fuselist': (0, 1, 2, 5, 6, 7, 8, 10), 'osc': (2, 0x08, 3, {16: 1, 20: 0}), 'updipin': (5, 0x10, 4, (1,))},
    'EC':         {'flash_start': 0x800000, 'sigrow': 0x1080, 'fuses': 0x1050, 'fuselist': (0, 1, 2, 5, 6, 7, 8, 10), 'osc': None, 'updipin': (5, 0x10, 4, (1,))},
    'LA':         {'flash_start': 0x800000, 'sigrow': 0x1080, 'fuses': 0x1050, 'fuselist': (0, 1, 2, 3, 4, 5, 6, 7, 8, 10), 'osc': (2, 0x08, 3, {16: 1, 20: 0}), 'updipin': (3, 0x02, 1, (1,))},
    'SD':         {'flash_start': 0x800000, 'sigrow': 0x1080, 'fuses': 0x1050, 'fuselist': (0, 1, 5, 6, 7, 8, 10), 'osc': None, 'updipin': None},
}

UPDI_DEVICES = [
    {'name': 'attiny202',    'device_id': 0x1E9123, 'family': 'tiny0',      'flash_size': 0x00800, 'flash_pagesize': 0x040},
    {'name': 'attiny204',    'device_id': 0x1E9122, 'family': 'tiny0',      'flash_size': 0x00800, 'flash_pagesize': 0x040},
    {'name': 'attiny402',    'device_id': 0x1E9227, 'family': 'tiny0',      'flash_size': 0x01000, 'flash_pagesize': 0x040},
    {'name': 'attiny404',    'device_id': 0x1E9226, 'family': 'tiny0',      'flash_size': 0x01000, 'flash_pagesize': 0x040},
    {'name': 'attiny406',    'device_id': 0x1E9225, 'family': 'tiny0',      'flash_size': 0x01000, 'flash_pagesize': 0x040},
    {'name': 'attiny804',    'device_id': 0x1E9325, 'family': 'tiny0',      'flash_size': 0x02000, 'flash_pagesize': 0x040},
    {'name': 'attiny806',    'device_id': 0x1E9324, 'family': 'tiny0',      'flash_size': 0x02000, 'flash_pagesize': 0x040},
    {'name': 'attiny807',    'device_id': 0x1E9323, 'family': 'tiny0',      'flash_size': 0x02000, 'flash_pagesize': 0x040},
    {'name': 'attiny1604',   'device_id': 0x1E9425, 'family': 'tiny0',      'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'attiny1606',   'device_id': 0x1E9424, 'family': 'tiny0',      'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'attiny1607',   'device_id': 0x1E9423, 'family': 'tiny0',      'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'attiny212',    'device_id': 0x1E9121, 'family': 'tiny1',      'flash_size': 0x00800, 'flash_pagesize': 0x040},
    {'name': 'attiny214',    'device_id': 0x1E9120, 'family': 'tiny1',      'flash_size': 0x00800, 'flash_pagesize': 0x040},
    {'name': 'attiny412',    'device_id': 0x1E9223, 'family': 'tiny1',      'flash_size': 0x01000, 'flash_pagesize': 0x040},
    {'name': 'attiny414',    'device_id': 0x1E9222, 'family': 'tiny1',      'flash_size': 0x01000, 'flash_pagesize': 0x040},
    {'name': 'attiny416',    'device_id': 0x1E9221, 'family': 'tiny1',      'flash_size': 0x01000, 'flash_pagesize': 0x040},
    {'name': 'attiny417',    'device_id': 0x1E9220, 'family': 'tiny1',      'flash_size': 0x01000, 'flash_pagesize': 0x040},
    {'name': 'attiny814',    'device_id': 0x1E9322, 'family': 'tiny1',      'flash_size': 0x02000, 'flash_pagesize': 0x040},
    {'name': 'attiny816',    'device_id': 0x1E9321, 'family': 'tiny1',      'flash_size': 0x02000, 'flash_pagesize': 0x040},
    {'name': 'attiny817',    'device_id': 0x1E9320, 'family': 'tiny1',      'flash_size': 0x02000, 'flash_pagesize': 0x040},
    {'name': 'attiny1614',   'device_id': 0x1E9422, 'family': 'tiny1',      'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'attiny1616',   'device_id': 0x1E9421, 'family': 'tiny1',      'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'attiny1617',   'device_id': 0x1E9420, 'family': 'tiny1',      'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'attiny3216',   'device_id': 0x1E9521, 'family': 'tiny1',      'flash_size': 0x08000, 'flash_pagesize': 0x080},
    {'name': 'attiny3217',   'device_id': 0x1E9522, 'family': 'tiny1',      'flash_size': 0x08000, 'flash_pagesize': 0x080},
    {'name': 'attiny416auto', 'device_id': 0x1E9228, 'family': 'tiny1-auto', 'flash_size': 0x01000, 'flash_pagesize': 0x040},
    {'name': 'attiny424',    'device_id': 0x1E922C, 'family': 'tiny2',      'flash_size': 0x01000, 'flash_pagesize': 0x040},
    {'name': 'attiny426',    'device_id': 0x1E922B, 'family': 'tiny2',      'flash_size': 0x01000, 'flash_pagesize': 0x040},
    {'name': 'attiny427',    'device_id': 0x1E922A, 'family': 'tiny2',      'flash_size': 0x01000, 'flash_pagesize': 0x040},
    {'name': 'attiny824',    'device_id': 0x1E9329, 'family': 'tiny2',      'flash_size': 0x02000, 'flash_pagesize': 0x040},
    {'name': 'attiny826',    'device_id': 0x1E9328, 'family': 'tiny2',      'flash_size': 0x02000, 'flash_pagesize': 0x040},
    {'name': 'attiny827',    'device_id': 0x1E9327, 'family': 'tiny2',      'flash_size': 0x02000, 'flash_pagesize': 0x040},
    {'name': 'attiny1624',   'device_id': 0x1E942A, 'family': 'tiny2',      'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'attiny1626',   'device_id': 0x1E9429, 'family': 'tiny2',      'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'attiny1627',   'device_id': 0x1E9428, 'family': 'tiny2',      'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'attiny3224',   'device_id': 0x1E9528, 'family': 'tiny2',      'flash_size': 0x08000, 'flash_pagesize': 0x080},
    {'name': 'attiny3226',   'device_id': 0x1E9527, 'family': 'tiny2',      'flash_size': 0x08000, 'flash_pagesize': 0x080},
    {'name': 'attiny3227',   'device_id': 0x1E9526, 'family': 'tiny2',      'flash_size': 0x08000, 'flash_pagesize': 0x080},
    {'name': 'atmega808',    'device_id': 0x1E9326, 'family': 'mega0',      'flash_size': 0x02000, 'flash_pagesize': 0x040},
    {'name': 'atmega809',    'device_id': 0x1E932A, 'family': 'mega0',      'flash_size': 0x02000, 'flash_pagesize': 0x040},
    {'name': 'atmega1608',   'device_id': 0x1E9427, 'family': 'mega0',      'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'atmega1609',   'device_id': 0x1E9426, 'family': 'mega0',      'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'atmega3208',   'device_id': 0x1E9530, 'family': 'mega0',      'flash_size': 0x08000, 'flash_pagesize': 0x080},
    {'name': 'atmega3209',   'device_id': 0x1E9531, 'family': 'mega0',      'flash_size': 0x08000, 'flash_pagesize': 0x080},
    {'name': 'atmega4808',   'device_id': 0x1E9650, 'family': 'mega0',      'flash_size': 0x0C000, 'flash_pagesize': 0x080},
    {'name': 'atmega4809',   'device_id': 0x1E9651, 'family': 'mega0',      'flash_size': 0x0C000, 'flash_pagesize': 0x080},
    {'name': 'avr32da28',    'device_id': 0x1E9534, 'family': 'DA',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr32da32',    'device_id': 0x1E9533, 'family': 'DA',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr32da48',    'device_id': 0x1E9532, 'family': 'DA',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr64da28',    'device_id': 0x1E9615, 'family': 'DA',         'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr64da32',    'device_id': 0x1E9614, 'family': 'DA',         'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr64da48',    'device_id': 0x1E9613, 'family': 'DA',         'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr64da64',    'device_id': 0x1E9612, 'family': 'DA',         'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr128da28',   'device_id': 0x1E970A, 'family': 'DA',         'flash_size': 0x20000, 'flash_pagesize': 0x200},
    {'name': 'avr128da32',   'device_id': 0x1E9709, 'family': 'DA',         'flash_size': 0x20000, 'flash_pagesize': 0x200},
    {'name': 'avr128da48',   'device_id': 0x1E9708, 'family': 'DA',         'flash_size': 0x20000, 'flash_pagesize': 0x200},
    {'name': 'avr128da64',   'device_id': 0x1E9707, 'family': 'DA',         'flash_size': 0x20000, 'flash_pagesize': 0x200},
    {'name': 'avr32da28s',   'device_id': 0x1E9572, 'family': 'DA-S',       'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr32da32s',   'device_id': 0x1E9571, 'family': 'DA-S',       'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr32da48s',   'device_id': 0x1E9570, 'family': 'DA-S',       'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr64da28s',   'device_id': 0x1E962E, 'family': 'DA-S',       'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr64da32s',   'device_id': 0x1E962D, 'family': 'DA-S',       'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr64da48s',   'device_id': 0x1E962C, 'family': 'DA-S',       'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr64da64s',   'device_id': 0x1E962B, 'family': 'DA-S',       'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr128da28s',  'device_id': 0x1E9712, 'family': 'DA-S',       'flash_size': 0x20000, 'flash_pagesize': 0x200},
    {'name': 'avr128da32s',  'device_id': 0x1E9711, 'family': 'DA-S',       'flash_size': 0x20000, 'flash_pagesize': 0x200},
    {'name': 'avr128da48s',  'device_id': 0x1E9710, 'family': 'DA-S',       'flash_size': 0x20000, 'flash_pagesize': 0x200},
    {'name': 'avr128da64s',  'device_id': 0x1E970F, 'family': 'DA-S',       'flash_size': 0x20000, 'flash_pagesize': 0x200},
    {'name': 'avr32db28',    'device_id': 0x1E9537, 'family': 'DB',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr32db32',    'device_id': 0x1E9536, 'family': 'DB',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr32db48',    'device_id': 0x1E9535, 'family': 'DB',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr64db28',    'device_id': 0x1E9619, 'family': 'DB',         'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr64db32',    'device_id': 0x1E9618, 'family': 'DB',         'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr64db48',    'device_id': 0x1E9617, 'family': 'DB',         'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr64db64',    'device_id': 0x1E9616, 'family': 'DB',         'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr128db28',   'device_id': 0x1E970E, 'family': 'DB',         'flash_size': 0x20000, 'flash_pagesize': 0x200},
    {'name': 'avr128db32',   'device_id': 0x1E970D, 'family': 'DB',         'flash_size': 0x20000, 'flash_pagesize': 0x200},
    {'name': 'avr128db48',   'device_id': 0x1E970C, 'family': 'DB',         'flash_size': 0x20000, 'flash_pagesize': 0x200},
    {'name': 'avr128db64',   'device_id': 0x1E970B, 'family': 'DB',         'flash_size': 0x20000, 'flash_pagesize': 0x200},
    {'name': 'avr16dd14',    'device_id': 0x1E9434, 'family': 'DD',         'flash_size': 0x04000, 'flash_pagesize': 0x200},
    {'name': 'avr16dd20',    'device_id': 0x1E9433, 'family': 'DD',         'flash_size': 0x04000, 'flash_pagesize': 0x200},
    {'name': 'avr16dd28',    'device_id': 0x1E9432, 'family': 'DD',         'flash_size': 0x04000, 'flash_pagesize': 0x200},
    {'name': 'avr16dd32',    'device_id': 0x1E9431, 'family': 'DD',         'flash_size': 0x04000, 'flash_pagesize': 0x200},
    {'name': 'avr32dd14',    'device_id': 0x1E953B, 'family': 'DD',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr32dd20',    'device_id': 0x1E953A, 'family': 'DD',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr32dd28',    'device_id': 0x1E9539, 'family': 'DD',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr32dd32',    'device_id': 0x1E9538, 'family': 'DD',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr64dd14',    'device_id': 0x1E961D, 'family': 'DD',         'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr64dd20',    'device_id': 0x1E961C, 'family': 'DD',         'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr64dd28',    'device_id': 0x1E961B, 'family': 'DD',         'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr64dd32',    'device_id': 0x1E961A, 'family': 'DD',         'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr16du14',    'device_id': 0x1E943B, 'family': 'DU',         'flash_size': 0x04000, 'flash_pagesize': 0x200},
    {'name': 'avr16du20',    'device_id': 0x1E943A, 'family': 'DU',         'flash_size': 0x04000, 'flash_pagesize': 0x200},
    {'name': 'avr16du28',    'device_id': 0x1E9439, 'family': 'DU',         'flash_size': 0x04000, 'flash_pagesize': 0x200},
    {'name': 'avr16du32',    'device_id': 0x1E9438, 'family': 'DU',         'flash_size': 0x04000, 'flash_pagesize': 0x200},
    {'name': 'avr32du14',    'device_id': 0x1E954F, 'family': 'DU',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr32du20',    'device_id': 0x1E954E, 'family': 'DU',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr32du28',    'device_id': 0x1E9540, 'family': 'DU',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr32du32',    'device_id': 0x1E953F, 'family': 'DU',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr64du28',    'device_id': 0x1E9622, 'family': 'DU',         'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr64du32',    'device_id': 0x1E9621, 'family': 'DU',         'flash_size': 0x10000, 'flash_pagesize': 0x200},
    {'name': 'avr8ea28',     'device_id': 0x1E932C, 'family': 'EA',         'flash_size': 0x02000, 'flash_pagesize': 0x040},
    {'name': 'avr8ea32',     'device_id': 0x1E932B, 'family': 'EA',         'flash_size': 0x02000, 'flash_pagesize': 0x040},
    {'name': 'avr16ea28',    'device_id': 0x1E9437, 'family': 'EA',         'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'avr16ea32',    'device_id': 0x1E9436, 'family': 'EA',         'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'avr16ea48',    'device_id': 0x1E9435, 'family': 'EA',         'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'avr32ea28',    'device_id': 0x1E953E, 'family': 'EA',         'flash_size': 0x08000, 'flash_pagesize': 0x040},
    {'name': 'avr32ea32',    'device_id': 0x1E953D, 'family': 'EA',         'flash_size': 0x08000, 'flash_pagesize': 0x040},
    {'name': 'avr32ea48',    'device_id': 0x1E953C, 'family': 'EA',         'flash_size': 0x08000, 'flash_pagesize': 0x040},
    {'name': 'avr64ea28',    'device_id': 0x1E9620, 'family': 'EA',         'flash_size': 0x10000, 'flash_pagesize': 0x080},
    {'name': 'avr64ea32',    'device_id': 0x1E961F, 'family': 'EA',         'flash_size': 0x10000, 'flash_pagesize': 0x080},
    {'name': 'avr64ea48',    'device_id': 0x1E961E, 'family': 'EA',         'flash_size': 0x10000, 'flash_pagesize': 0x080},
    {'name': 'avr16eb14',    'device_id': 0x1E9449, 'family': 'EB',         'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'avr16eb20',    'device_id': 0x1E9440, 'family': 'EB',         'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'avr16eb28',    'device_id': 0x1E943F, 'family': 'EB',         'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'avr16eb32',    'device_id': 0x1E943E, 'family': 'EB',         'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'avr32eb14',    'device_id': 0x1E952D, 'family': 'EB',         'flash_size': 0x08000, 'flash_pagesize': 0x040},
    {'name': 'avr32eb20',    'device_id': 0x1E952C, 'family': 'EB',         'flash_size': 0x08000, 'flash_pagesize': 0x040},
    {'name': 'avr32eb28',    'device_id': 0x1E952B, 'family': 'EB',         'flash_size': 0x08000, 'flash_pagesize': 0x040},
    {'name': 'avr32eb32',    'device_id': 0x1E952A, 'family': 'EB',         'flash_size': 0x08000, 'flash_pagesize': 0x040},
    {'name': 'avr64ec28',    'device_id': 0x1E962A, 'family': 'EC',         'flash_size': 0x10000, 'flash_pagesize': 0x080},
    {'name': 'avr64ec48',    'device_id': 0x1E9628, 'family': 'EC',         'flash_size': 0x10000, 'flash_pagesize': 0x080},
    {'name': 'avr16la14',    'device_id': 0x1E9454, 'family': 'LA',         'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'avr16la20',    'device_id': 0x1E9453, 'family': 'LA',         'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'avr16la28',    'device_id': 0x1E9452, 'family': 'LA',         'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'avr16la32',    'device_id': 0x1E9451, 'family': 'LA',         'flash_size': 0x04000, 'flash_pagesize': 0x040},
    {'name': 'avr32la14',    'device_id': 0x1E9529, 'family': 'LA',         'flash_size': 0x08000, 'flash_pagesize': 0x040},
    {'name': 'avr32la20',    'device_id': 0x1E9560, 'family': 'LA',         'flash_size': 0x08000, 'flash_pagesize': 0x040},
    {'name': 'avr32la28',    'device_id': 0x1E9559, 'family': 'LA',         'flash_size': 0x08000, 'flash_pagesize': 0x040},
    {'name': 'avr32la32',    'device_id': 0x1E9558, 'family': 'LA',         'flash_size': 0x08000, 'flash_pagesize': 0x040},
    {'name': 'avr32sd20',    'device_id': 0x1E9554, 'family': 'SD',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr32sd28',    'device_id': 0x1E9553, 'family': 'SD',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
    {'name': 'avr32sd32',    'device_id': 0x1E9552, 'family': 'SD',         'flash_size': 0x08000, 'flash_pagesize': 0x200},
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
UPDI_READ_BLOCK_SIZE = 256

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

# NVM controller variants (from SIB "P:x"): STATUS register offset, write error mask
# P:0 = tinyAVR, megaAVR 0 (16-bit addresses, page buffer)
# P:2 = AVR DA, DB, DD (24-bit, word write)    P:3 = AVR EA (24-bit, page buffer)
# P:4 = AVR DU (24-bit, word write)            P:5 = AVR EB (24-bit, page buffer)
# P:6 = 24-bit, word write (as P:4, STATUS at 0x07)
UPDI_NVM_PARAMS = {'0': (0x02, 0x04), '2': (0x02, 0x30), '3': (0x06, 0x70),
                   '4': (0x06, 0x70), '5': (0x06, 0x70), '6': (0x07, 0x70)}
UPDI_NVM_PAGE_ORIENTED = '35'
UPDI_NVM_STATUS_BUSY_MASK = 0x03

UPDI_NVMCTRL_CTRLA = 0x00

UPDI_V0_NVMCTRL_DATAL = 0x06
UPDI_V0_NVMCTRL_DATAH = 0x07
UPDI_V0_NVMCTRL_ADDRL = 0x08
UPDI_V0_NVMCTRL_ADDRH = 0x09

UPDI_V0_NVMCTRL_CTRLA_NOP = 0x00
UPDI_V0_NVMCTRL_CTRLA_WRITE_PAGE = 0x01
UPDI_V0_NVMCTRL_CTRLA_ERASE_PAGE = 0x02
UPDI_V0_NVMCTRL_CTRLA_ERASE_WRITE_PAGE = 0x03
UPDI_V0_NVMCTRL_CTRLA_PAGE_BUFFER_CLR = 0x04
UPDI_V0_NVMCTRL_CTRLA_CHIP_ERASE = 0x05
UPDI_V0_NVMCTRL_CTRLA_ERASE_EEPROM = 0x06
UPDI_V0_NVMCTRL_CTRLA_WRITE_FUSE = 0x07

UPDI_NVMCTRL_CTRLA_NOCMD = 0x00
UPDI_NVMCTRL_CTRLA_FLASH_WRITE = 0x02
UPDI_NVMCTRL_CTRLA_FLASH_PAGE_WRITE = 0x04
UPDI_NVMCTRL_CTRLA_FLASH_PAGE_BUFFER_CLEAR = 0x0F
UPDI_NVMCTRL_CTRLA_EEPROM_ERASE_WRITE = 0x13
UPDI_NVMCTRL_CTRLA_EEPROM_PAGE_ERASE_WRITE = 0x15
UPDI_NVMCTRL_CTRLA_EEPROM_PAGE_BUFFER_CLEAR = 0x1F
UPDI_NVMCTRL_CTRLA_CHIP_ERASE = 0x20

UPDI_V0_FUSE_LOCKBIT = 0x0A
UPDI_V0_LOCKBIT_UNLOCKED = 0xC5
UPDI_MAX_FUSE = 0x0F


# ===================================================================================

if __name__ == "__main__":
    _main()
