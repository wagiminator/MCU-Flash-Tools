# Minimal UPDI Programming Tool for tinyAVR
## Description
This tool allows tinyAVR series 0, 1, and 2 microcontrollers to be programmed using a USB-to-serial converter connected in a special way to the UPDI pin (also called SerialUPDI). More information can be found [here](https://github.com/SpenceKonde/AVR-Guidance/blob/master/UPDI/jtag2updi.md).

## Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

## Installation
Ensure that the [prerequisites](https://packaging.python.org/en/latest/tutorials/installing-packages/) for installing Python packages are met. Then execute the following command in the command line:

```
pip install tinyupdi
```

## Usage
Connect the USB-to-serial converter via USB to the PC and via the circuit described below to the UPDI pin of the microcontroller.

```
USB2SERIAL                       tinyAVR
+--------+                    +-----------+
|     RXD| <------------+---> |UPDI (PA0) |
|        |              |     |           |
|     TXD| ---|1kOhm|---+     |           |
|        |                    |           |
|     VDD| -----------------> |VDD        |
|     GND| -----------------> |GND        |
+--------+                    +-----------+
```

Alternatively, a pre-assembled [SerialUPDI programmer](https://github.com/wagiminator/AVR-Programmer) can be used.

```
Usage: tinyupdi [-h] [-d DEVICE] [-e] [-f FLASH] [-fs [FUSES [FUSES ...]]] [-t TRIM]

Optional arguments:
  -h, --help                show help message and exit
  -d, --device              set target device (if not set, it will be auto-detected)
  -e, --erase               perform a chip erase (implied with --flash)
  -f FLASH, --flash FLASH   BIN file to flash
  -fs [FUSES [FUSES ...]], --fuses [FUSES [FUSES ...]]
                            fuses to set (syntax: fuse_nr:0xvalue)
  -t TRIM, --trim TRIM      configure oscillator for given frequency (set fuse 2)
Example:
tinyupdi -f firmware.bin -fs 6:0x04 7:0x00 8:0x00 -t 8000000
```

## Links
- [MCU Flash Tools](https://github.com/wagiminator/MCU-Flash-Tools)
- [MCU Templates](https://github.com/wagiminator/MCU-Templates)
- [MCU Development Boards](https://github.com/wagiminator/Development-Boards)
- [AVR Development Boards](https://github.com/wagiminator/AVR-Development-Boards)
- [AVR Programmers](https://github.com/wagiminator/AVR-Programmer)
- [SAMD Development Boards](https://github.com/wagiminator/SAMD-Development-Boards)
