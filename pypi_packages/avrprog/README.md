# Programming Tool for classic AVR Microcontrollers with USBasp or USBtinyISP
## Description
With this tool, classic AVR microcontrollers can be flashed via ISP with a USBasp or a USBtinyISP programmer. The programmer type and the connected chip are detected automatically. BIN and Intel HEX files are supported; fuses and lock bits can be written, and fuse settings that would disable ISP (RSTDISBL, DWEN, SPIEN) are refused unless forced.

The tool is a Python port of the relevant parts of [avrdude](https://github.com/avrdudes/avrdude) 8.3; the part data was generated from avrdude.conf. It supports all 168 classic AVRs of avrdude.conf with ISP and paged flash, among others:
- ATtiny13(A), ATtiny24(A)/44(A)/84(A), ATtiny25/45/85, ATtiny26, ATtiny43U, ATtiny48/88, ATtiny87/167, ATtiny261(A)/461(A)/861(A), ATtiny441/841, ATtiny828(R), ATtiny1634(R), ATtiny2313(A)/4313
- ATmega8(A), ATmega16(A), ATmega32(A), ATmega64(A), ATmega128(A), ATmega162, ATmega163, ATmega8515, ATmega8535
- ATmega48/88/168/328 (A, P, PA, PB), ATmega164/324/644 (A, P, PA, PB), ATmega1284(P)
- ATmega165/169/325/329/3250/3290/645/649/6450/6490 (A, P, PA)
- ATmega640/1280/1281/2560/2561, ATmega128RFA1, ATmega64/128/256RFR2, ATmega644/1284/2564RFR2
- ATmega8U2/16U2/32U2, ATmega16U4/32U4, AT90USB82/162/646/647/1286/1287
- ATmega16M1/32M1/64M1, ATmega32C1/64C1, AT90CAN32/64/128, AT90PWM1/2(B)/3(B)/81/161/216/316
- ATmega16HVB/32HVB, ATmega32HVE2/64HVE2, ATmegaS64M1/S128, ATA5505, ATA6612C/6613C/6614Q/6616C/6617C, ATA664251

Use `avrprog --list` to show all supported chips.

## Preparations
Linux users need permission to access the device. Run:
```
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="16c0", ATTR{idProduct}=="05dc", MODE="666"' | sudo tee /etc/udev/rules.d/99-avrprog.rules
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1781", ATTR{idProduct}=="0c9f", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-avrprog.rules
sudo udevadm control --reload-rules
```

On Windows, the programmer needs a libusb compatible driver (WinUSB, libusb-win32 or libusbK, installable with [Zadig](https://zadig.akeo.ie)). The libusb backend is installed automatically with the package (libusb-package).

## Installation
Ensure that the [prerequisites](https://packaging.python.org/en/latest/tutorials/installing-packages/) for installing Python packages are met. Then execute the following command in the command line:

```
pip install avrprog
```

## Usage
Connect the programmer to your PC and its ISP cable to the AVR.

```
Usage: avrprog [-h] [-t {usbasp,usbtiny}] [-p PART] [-B BITCLOCK] [-e] [-f FLASH] [-l LFUSE] [-H HFUSE] [-E EFUSE] [-L LOCK] [-r] [-F] [--list]

Optional arguments:
  -h, --help                show help message and exit
  -t, --programmer          programmer type (default: auto-detect)
  -p, --part                chip type, e.g. m328p (default: auto-detect by signature)
  -B, --bitclock            ISP clock: period in us (e.g. 10) or frequency (e.g. 125kHz)
  -e, --erase               perform a chip erase (implied with -f)
  -f FLASH, --flash FLASH   write BIN or HEX file to flash and verify
  -l, --lfuse VALUE         write low fuse byte
  -H, --hfuse VALUE         write high fuse byte
  -E, --efuse VALUE         write extended fuse byte
  -L, --lock VALUE          write lock byte (after all other actions)
  -r, --read                read and show fuses, lock bits and calibration
  -F, --force               allow fuse settings that disable ISP (RSTDISBL, DWEN, SPIEN)
  --list                    list supported chips
Without action arguments the tool shows programmer, chip and fuses.

Example:
avrprog -f firmware.hex -l 0xe2 -H 0xdf -E 0xff
```

## License
GNU General Public License v2.0 or later (derived from avrdude).

## Links
- [MCU Flash Tools](https://github.com/wagiminator/MCU-Flash-Tools)
- [avrdude](https://github.com/avrdudes/avrdude)
- [MCU Templates](https://github.com/wagiminator/MCU-Templates)
- [MCU Development Boards](https://github.com/wagiminator/Development-Boards)
- [AVR Development Boards](https://github.com/wagiminator/AVR-Development-Boards)
- [AVR Programmers](https://github.com/wagiminator/AVR-Programmer)
