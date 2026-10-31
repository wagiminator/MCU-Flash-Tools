# Programming Tool for STM32, PY32 and SAMD Microcontrollers via CMSIS-DAP, ST-Link or J-Link
## Description
tinyOCD is a simple programming tool for ARM Cortex-M microcontrollers using the SWD interface. It works with CMSIS-DAP v1 (HID) and v2 (bulk) programmers (e.g. DAPLink, Raspberry Pi Debug Probe), ST-Link V2, V2-1 and V3 as well as SEGGER J-Link. Programmer and chip are detected automatically. The flash memory is programmed by a small generic flash loader that runs in the RAM of the target.

Supported microcontrollers:
- STM32: C0, F0, F1, F2, F3, F4, F7, G0, G4, H5, H7, L0, L1, L4, L4+, L5, U0, U3, U5, WB, WBA, WL
- PUYA: PY32F002A, PY32F003, PY32F030, PY32F002B, PY32F071, PY32F072 (and compatible, e.g. AIR001)
- Microchip/ATMEL: ATSAMD09, ATSAMD10, ATSAMD11, ATSAMD20, ATSAMD21, ATSAMDA1, ATSAML21, ATSAML22, ATSAMC20, ATSAMC21, ATSAMD51, ATSAME51, ATSAME53, ATSAME54

Functions:
- write BIN file to flash and verify (with chip erase)
- chip erase
- remove/set read protection (unlock/lock)
- make BOOT0 pin usable for the embedded bootloader (STM32C0/F0/F3/G0/G4/L4/L5/U0/U5/WB/WL, PY32F0xx/F07x)
- configure NRST pin as GPIO or reset pin (STM32C0/G0/G4/U0, PY32)

## Preparations
Linux users need permission to access the programmer. Run:

```
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0483", MODE="666"' | sudo tee /etc/udev/rules.d/99-tinyocd.rules
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1366", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-tinyocd.rules
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0d28", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-tinyocd.rules
echo 'KERNEL=="hidraw*", ATTRS{idVendor}=="0d28", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-tinyocd.rules
sudo udevadm control --reload-rules
```

Add further lines for the vendor IDs of other CMSIS-DAP programmers (e.g. 2e8a, c251, 1a86).

On Windows, ST-Link (with ST driver) and CMSIS-DAP v2 (WinUSB) normally work out of the box. A J-Link must use the WinUSB driver (J-Link Configurator: "Use WinUSB") or a libusb driver installed with [Zadig](https://zadig.akeo.ie/). For CMSIS-DAP v1 (HID) programmers on Windows and macOS, install hidapi: `pip install tinyocd[hid]`.

## Installation
Ensure that the [prerequisites](https://packaging.python.org/en/latest/tutorials/installing-packages/) for installing Python packages are met. Then execute the following command in the command line:

```
pip install tinyocd
```

## Usage
Connect the programmer to your PC and to the SWD interface of the MCU (SWDIO, SWCLK, GND, optionally NRST and VCC).

```
Usage: tinyocd [-h] [-p {auto,cmsis-dap,stlink,jlink}] [-s SPEED] [-u] [-l] [-e] [-B] [-G] [-R] [-f FLASH] [-t]

Optional arguments:
  -h, --help                show help message and exit
  -p, --probe               select programmer type (default: auto)
  -s SPEED, --speed SPEED   SWD clock in kHz (default: 1000)
  -u, --unlock              unlock chip (remove read protection, erases chip)
  -l, --lock                lock chip (set read protection)
  -e, --erase               perform a whole chip erase (implied with -f)
  -B, --bootpin             make BOOT0 pin usable for embedded bootloader
  -G, --pingpio             make NRST pin a GPIO pin
  -R, --pinreset            make NRST pin a reset pin
  -f FLASH, --flash FLASH   write BIN file to flash and verify
  -t, --list                list supported chips

Example:
tinyocd -f firmware.bin
```

Notes:
- The BIN file is written to the start of the flash memory (0x08000000 for STM32/PY32, 0x00000000 for SAMD).
- If the chip cannot be halted (e.g. SWD pins disabled by the firmware), tinyOCD connects under reset. For this, NRST must be connected to the programmer.
- On SAMD chips, a bootloader protected by the BOOTPROT fuse cannot be overwritten. A chip erase (-e) does not clear the BOOTPROT fuse.
- With -B the BOOT0 pin is enabled via option bytes. On STM32C0/G0 the BOOT0 pin is shared with SWCLK (PA14).

## Links
- [MCU Flash Tools](https://github.com/wagiminator/MCU-Flash-Tools)
- [MCU Templates](https://github.com/wagiminator/MCU-Templates)
- [MCU Development Boards](https://github.com/wagiminator/Development-Boards)
