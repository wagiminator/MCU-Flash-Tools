#  stc8isp - Programming Tool for STC8G/8H Microcontrollers
## Description
With this tool, STC8G/8H microcontrollers can be flashed via a simple USB-to-serial converter by utilizing the factory built-in embedded bootloader.

## Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

## Installation
- Install [Python3](https://www.pythontutorial.net/getting-started/install-python/).
- Install [pip](https://pip.pypa.io/en/stable/installation/).
- Install stc8isp: 

```
pip install stc8isp
```

## Usage
- Connect your USB-to-serial converter to your MCU as shown below.
- Run stc8isp.py (see below for arguments).
- Perform a power cycle of your MCU (reconnect to power) when prompted.

```
USB2SERIAL         STC8G/8H
+--------+         +------+
|     VCC| --/ --> |VCC   |    interruptible (for power cycle)
|     RXD| --|R|-- |P3.1  |    resistor (100R - 1000R)
|     TXD| --|<|-- |P3.0  |    diode (e.g. 1N5819)
|     GND| ------- |GND   |    common ground
+--------+         +------+
```

```
Usage: stc8isp [-h] [-p PORT] [-t TRIM] [-e] [-f FLASH]

Optional arguments:
  -h,       --help          show this help message and exit
  -p PORT,  --port PORT     set COM port (default: /dev/ttyUSB0)
  -t TRIM,  --trim TRIM     trim IRC to frequency in Hz (128000 - 36000000)
  -e,       --erase         perform chip erase (implied with -f)
  -f FLASH, --flash FLASH   write BIN file to flash

Example:
stc8isp -p /dev/ttyUSB0 -t 24000000 -f firmware.bin
```

## Links
- [MCU Flash Tools](https://github.com/wagiminator/MCU-Flash-Tools)
- [MCU Templates](https://github.com/wagiminator/MCU-Templates)
- [MCU Development Boards](https://github.com/wagiminator/Development-Boards)
- [AVR Development Boards](https://github.com/wagiminator/AVR-Development-Boards)
- [AVR Programmers](https://github.com/wagiminator/AVR-Programmer)
- [SAMD Development Boards](https://github.com/wagiminator/SAMD-Development-Boards)