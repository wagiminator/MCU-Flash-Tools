# Programming Tool for WCH RISC-V Microcontrollers using WCH-LinkE
## Description
With this open-source platform-independant command-line tool, WCH RISC-V microcontrollers can be programmed using the [WCH-LinkE](http://www.wch-ic.com/products/WCH-Link.html) (pay attention to the "E" in the name) via their serial debug interface.

The tool currently supports the following microcontrollers:
- CH32V003, CH32V103, CH32V203, CH32V208, CH32V303, CH32V305, CH32V307,
- CH32X033, CH32X035,
- CH32L103,
- CH571, CH573, CH581, CH582, CH583, CH591, CH592.

## Preparations
To use the WCH-LinkE on Linux, you need to grant access permissions beforehand by executing the following commands:
```
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", ATTR{idProduct}=="8010", MODE="666"' | sudo tee /etc/udev/rules.d/99-WCH-LinkE.rules
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", ATTR{idProduct}=="8012", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-WCH-LinkE.rules
sudo udevadm control --reload-rules
```

On Windows, if you need to you can install the WinUSB driver over the WCH interface 1 using the [Zadig](https://zadig.akeo.ie/) tool.

## Installation
Ensure that the [prerequisites](https://packaging.python.org/en/latest/tutorials/installing-packages/) for installing Python packages are met. Then execute the following command in the command line:

```
pip install rvprog
```

## Usage
To upload firmware, you should make the following connections to the WCH-LinkE (SWCLK is not present on the CH32V003 and therefore does not need to be connected):

```
WCH-LinkE      RISC-V MCU
+-------+      +--------+
|  SWCLK| ---> |SWCLK   |
|  SWDIO| <--> |SWDIO   |
|    GND| ---> |GND     |
|    3V3| ---> |VDD     |
+-------+      +--------+
```

If the blue LED on the WCH-LinkE remains illuminated once it is connected to the USB port, it means that the device is currently in ARM mode and must be switched to RISC-V mode initially. There are a few ways to accomplish this:
- You can utilize the rvprog tool with the -v option (see below).
- Alternatively, you can select "WCH-LinkRV" in the software provided by WCH, such as MounRiver Studio or WCH-LinkUtility.
- Another option is to hold down the ModeS button on the device while plugging it into the USB port.

More information can be found in the [WCH-Link User Manual](http://www.wch-ic.com/downloads/WCH-LinkUserManual_PDF.html).

```
Usage: rvprog [-h] [-a] [-v] [-b] [-u] [-l] [-e] [-G] [-R] [-f FLASH]

Optional arguments:
  -h, --help                show help message and exit
  -a, --armmode             switch WCH-LinkE to ARM mode
  -v, --rvmode              switch WCH-LinkE to RISC-V mode
  -b, --unbrick             unbrick chip (power cycle erase)
  -u, --unlock              unlock chip (remove read protection)
  -l, --lock                lock chip (set read protection)
  -e, --erase               perform a whole chip erase
  -G, --pingpio             make nRST pin a GPIO pin (CH32V003 only)
  -R, --pinreset            make nRST pin a reset pin (CH32V003 only)
  -f FLASH, --flash FLASH   write BIN file to flash

Example:
rvprog -f firmware.bin
```

## Links
- [MCU Flash Tools](https://github.com/wagiminator/MCU-Flash-Tools)
- [MCU Templates](https://github.com/wagiminator/MCU-Templates)
- [MCU Development Boards](https://github.com/wagiminator/Development-Boards)
- [AVR Development Boards](https://github.com/wagiminator/AVR-Development-Boards)
- [AVR Programmers](https://github.com/wagiminator/AVR-Programmer)
- [SAMD Development Boards](https://github.com/wagiminator/SAMD-Development-Boards)
