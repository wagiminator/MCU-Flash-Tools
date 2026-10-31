# Simple SerialUPDI Programming Tool for all AVR Microcontrollers with UPDI
## Description
megaUPDI allows all AVR microcontrollers with UPDI programming interface (tinyAVR 0/1/2, megaAVR 0, AVR DA/DB/DD/DU/EA/EB/EC/LA/SD) to be programmed using a USB-to-serial converter connected in a special way to the UPDI pin (also called SerialUPDI). More information can be found [here](https://github.com/SpenceKonde/AVR-Guidance/blob/master/UPDI/jtag2updi.md). megaUPDI is the big brother of [TinyUPDI](https://pypi.org/project/tinyupdi/): the NVM controller variant (P:0, P:2 ... P:6) is read from the System Information Block (SIB) of the target, the device is identified by its signature.

Supported microcontrollers (133 devices):
- tinyAVR 0-series: ATtiny202, 204, 402, 404, 406, 804, 806, 807, 1604, 1606, 1607
- tinyAVR 1-series: ATtiny212, 214, 412, 414, 416, 416auto, 417, 814, 816, 817, 1614, 1616, 1617, 3216, 3217
- tinyAVR 2-series: ATtiny424, 426, 427, 824, 826, 827, 1624, 1626, 1627, 3224, 3226, 3227
- megaAVR 0-series: ATmega808, 809, 1608, 1609, 3208, 3209, 4808, 4809
- AVR DA: AVR32DA28/32/48, AVR64DA28/32/48/64, AVR128DA28/32/48/64 (also DA-S variants, e.g. AVR128DA28S)
- AVR DB: AVR32DB28/32/48, AVR64DB28/32/48/64, AVR128DB28/32/48/64
- AVR DD: AVR16DD14/20/28/32, AVR32DD14/20/28/32, AVR64DD14/20/28/32
- AVR DU: AVR16DU14/20/28/32, AVR32DU14/20/28/32, AVR64DU28/32
- AVR EA: AVR8EA28/32, AVR16EA28/32/48, AVR32EA28/32/48, AVR64EA28/32/48
- AVR EB: AVR16EB14/20/28/32, AVR32EB14/20/28/32
- AVR EC: AVR64EC28/48
- AVR LA: AVR16LA14/20/28/32, AVR32LA14/20/28/32
- AVR SD: AVR32SD20/28/32

## Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

## Installation
Ensure that the [prerequisites](https://packaging.python.org/en/latest/tutorials/installing-packages/) for installing Python packages are met. Then execute the following command in the command line:

```
pip install megaupdi
```

## Usage
Connect the USB-to-serial converter via USB to the PC and via the circuit described below to the UPDI pin of the microcontroller.

```
USB2SERIAL                         AVR
+--------+                    +-----------+
|     RXD| <------------+---> |UPDI       |
|        |              |     |           |
|     TXD| ---|1kOhm|---+     |           |
|        |                    |           |
|     VDD| -----------------> |VDD        |
|     GND| -----------------> |GND        |
+--------+                    +-----------+
```

Alternatively, a pre-assembled [SerialUPDI programmer](https://github.com/wagiminator/AVR-Programmer) can be used.

```
Usage: megaupdi [-h] [-p PORT] [-d DEVICE] [-e] [-f FLASH] [-fs [FUSES ...]] [-t TRIM] [-l]

Optional arguments:
  -h, --help                show help message and exit
  -p PORT, --port PORT      serial port (if not set, it will be auto-detected)
  -d, --device              set target device (if not set, it will be auto-detected)
  -e, --erase               perform a chip erase (implied with --flash)
  -f FLASH, --flash FLASH   BIN file to flash
  -fs [FUSES ...], --fuses [FUSES ...]
                            fuses to set (syntax: fuse_nr:0xvalue)
  -t TRIM, --trim TRIM      configure oscillator for given frequency (set fuse 2)
  -l, --list                list supported devices
Examples:
megaupdi -f firmware.bin
megaupdi -d avr128da28 -f firmware.bin -fs 0:0x00 1:0x00
megaupdi -f firmware.bin -fs 6:0x04 7:0x00 8:0x00 -t 8000000
```

Notes:
- Fuse numbers are relative to the first fuse (FUSE0). Valid numbers depend on the device family: tinyAVR/megaAVR 0: 0 - 10 (10 = LOCKBIT), AVR Dx/Ex/Lx/Sx: e.g. 0, 1, 2, 5, 6, 7, 8 (plus 10 on some families). Invalid fuse numbers are rejected before anything is erased or written.
- -t sets the oscillator fuse (16 or 20 MHz) on tinyAVR, megaAVR 0, AVR EA/EB and AVR LA. The system frequency must be reachable with the clock prescaler, which has to be set by the firmware.
- A locked device is only unlocked (by a chip erase) when -e or -f is given.
- Changing the pin configuration fuse can disable the UPDI pin (tinyAVR: fuse 5, AVR DD/DU/EA/EB/EC: fuse 5, AVR LA: fuse 3); the device can then only be programmed with a high-voltage programmer. megaUPDI prints a warning in this case.
- Only flash and fuses can be programmed. EEPROM, user row, boot row and the lock bits of the AVR Dx/Ex/Lx/Sx families are not supported.

## Links
- [MCU Flash Tools](https://github.com/wagiminator/MCU-Flash-Tools)
- [MCU Templates](https://github.com/wagiminator/MCU-Templates)
- [MCU Development Boards](https://github.com/wagiminator/Development-Boards)
- [AVR Development Boards](https://github.com/wagiminator/AVR-Development-Boards)
- [AVR Programmers](https://github.com/wagiminator/AVR-Programmer)
- [SAMD Development Boards](https://github.com/wagiminator/SAMD-Development-Boards)
