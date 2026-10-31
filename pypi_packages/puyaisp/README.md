#  Programming Tool for PUYA PY32 Microcontrollers
## Description
With this tool, PUYA PY32 microcontrollers can be flashed via a simple USB-to-serial converter by utilizing the factory built-in embedded UART/HID bootloader.

Supported microcontrollers (identified by the bootloader PID):

|Bootloader PID|Microcontrollers|Interfaces|
|:-|:-|:-|
|0x440|PY32F002A, PY32F003, PY32F030|UART|
|0x448|PY32F071, PY32F072, PY32F040|UART, USB HID|
|0x413|PY32F403, PY32F303|UART|

Other PY32 microcontrollers with the same bootloader protocol can be flashed as well, but their option bytes cannot be changed. PY32F002B and PY32L020 have no UART bootloader in system memory and are not supported.

## Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

## Installation
Ensure that the [prerequisites](https://packaging.python.org/en/latest/tutorials/installing-packages/) for installing Python packages are met. Then execute the following command in the command line:

```
pip install puyaisp
```

## Usage
Connect your USB-to-serial converter to your PY32 MCU as follows:

```
USB2SERIAL      PY32F002A/F003/F030    PY32F07x/F040    PY32F403/F303
+--------+
|     RXD| <--- PA2 or PA9  or PA14    PA9  or PA14     PA9  or PB10
|     TXD| ---> PA3 or PA10 or PA15    PA10 or PA15     PA10 or PB11
|     VDD| ---> VDD                    VDD              VDD
|     GND| ---> GND                    GND              GND
+--------+
```

Unused RX pins of the bootloader UARTs should not float (use pull-up resistors).

Set your MCU to bootloader mode by using ONE of the following methods:
- Disconnect your USB-to-serial converter, pull BOOT0 pin (PF4) to VCC (or press and hold the BOOT button, if your board has one), then connect the converter to your USB port. BOOT0 pin (or BOOT button) can be released now.
- Connect your USB-to-serial converter to your USB port. Pull BOOT0 pin (PF4) to VCC, then pull nRST (PF2) shortly to GND (or press and hold the BOOT button, then press and release the RESET button and then release the BOOT button, if your board has them).
- If your microcontroller has USB, pull BOOT0 pin (PF4) to VCC (or press and hold the BOOT button, if your board has one), then connect it to your USB port. The default USB VID:PID is `ffff:0448`.

```
Usage: puyaisp [-h] [-u] [-l] [-e] [-o] [-G] [-R] [-t {serial,hid}] [-f FLASH]
               [--vid VID] [--pid PID] [--path PATH]
               [--timeout TIMEOUT]

Optional arguments:
  -h, --help                     show this help message and exit
  -u, --unlock                   unlock chip (remove read protection)
  -l, --lock                     lock chip (set read protection)
  -e, --erase                    perform chip erase (implied with -f)
  -o, --rstoption                reset option bytes
  -G, --nrstgpio                 make nRST pin a GPIO pin
  -R, --nrstreset                make nRST pin a RESET pin
  -t, --transport {serial,hid}   bootloader transport
  -f FLASH, --flash FLASH        write BIN file to flash and verify
  --vid VID                      HID VID
  --pid PID                      HID PID
  --path PATH                    hidapi device path
  --timeout TIMEOUT              read timeout in ms

Examples:
puyaisp -f firmware.bin
puyaisp -t hid -f firmware.bin
```

## Links
- [MCU Flash Tools](https://github.com/wagiminator/MCU-Flash-Tools)
- [MCU Templates](https://github.com/wagiminator/MCU-Templates)
- [MCU Development Boards](https://github.com/wagiminator/Development-Boards)
- [AVR Development Boards](https://github.com/wagiminator/AVR-Development-Boards)
- [AVR Programmers](https://github.com/wagiminator/AVR-Programmer)
- [SAMD Development Boards](https://github.com/wagiminator/SAMD-Development-Boards)
