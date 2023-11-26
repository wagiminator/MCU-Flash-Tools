# MCU ISP Flash Tools
This is a compilation of straightforward In-System Programming (ISP) flash tools for different microcontrollers, all written as individual Python scripts. Their single-script format makes them incredibly easy to integrate into any toolchain.

- [chprog.py - Flashing CH55x, CH32Fxxx, CH32Vxxx via embedded USB bootloader](#chprog)
- [rvprog.py - Flashing CH32Vxxx with WCH-LinkE via serial debug interface](#rvprog)
- [puyaisp.py - Flashing PY32F0xx with USB-to-serial converter via embedded USART bootloader](#puyaisp)
- [stc8isp.py - Flashing STC8G/8H with USB-to-serial converter via embedded USART bootloader](#stc8isp)
- [stm32isp.py - Flashing entry-level STM32 with USB-to-serial converter via embedded USART bootloader](#stm32isp)
- [tinyupdi.py - Flashing tinyAVR with USB-to-serial converter via UPDI](#tinyupdi)

In order for these tools to work, Python3 must be installed on your system. To do this, follow these [instructions](https://www.pythontutorial.net/getting-started/install-python/). In addition [PyUSB](https://github.com/pyusb/pyusb) and [PySerial](https://github.com/pyserial/pyserial) must be installed. On Linux (Debian-based), all of this can be done with the following commands:

```
sudo apt install python3 python3-pip
python3 -m pip install pyusb pyserial
```

Windows users in particular may also need to install [libusb](https://github.com/libusb/libusb).

## chprog
### Description
With this tool, almost all WCH microcontrollers (e.g. CH55x, CH32Fxxx, and CH32Vxxx) which have a factory-builtin bootloader (v2.x.x) can be flashed via USB.

### Preparations
On Linux you do not need to install a driver for the USB bootloader. However, by default Linux will not expose enough permission to upload your code. In order to fix this, open a terminal and run the following commands:

```
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="4348", ATTR{idProduct}=="55e0", MODE="666"' | sudo tee /etc/udev/rules.d/99-ch55x.rules
sudo udevadm control --reload-rules
```

For Windows, you need the [CH372 driver](http://www.wch-ic.com/downloads/CH372DRV_EXE.html). Alternatively, you can also use the [Zadig Tool](https://zadig.akeo.ie/) to install the correct driver. Here, click "Options" -> "List All Devices" and select the USB module. Then install the libusb-win32 driver. To do this, the board must be connected and the microcontroller must be in bootloader mode.

### Usage
The bootloader must be started manually for new uploads. To do this, the board must first be disconnected from the USB port and all voltage sources. Now press the BOOT button and keep it pressed while reconnecting the board to the USB port of your PC. The chip now starts in bootloader mode, the BOOT button can be released and new firmware can be uploaded via USB. Alternatively, you can leave the board connected to the USB port, press and hold the BOOT button, press and release the RESET button and then release the BOOT button to enter the bootloader mode. If there is no BOOT button on the board, look at the datasheet to find out which pin needs to be pulled to which voltage level for the microcontroller to go into boot mode.

Now run the following command (example):
```
python3 chprog.py firmware.bin
```

## rvprog
### Description
With this tool, the WCH RISC-V microcontrollers (CH32Vxxx) can be programmed with the [WCH-LinkE](http://www.wch-ic.com/products/WCH-Link.html) (pay attention to the "E" in the name) via its serial debug interface.

### Preparations
To use the WCH-Link on Linux, you need to grant access permissions beforehand by executing the following commands:
```
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", ATTR{idProduct}=="8010", MODE="666"' | sudo tee /etc/udev/rules.d/99-WCH-LinkE.rules
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", ATTR{idProduct}=="8012", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-WCH-LinkE.rules
sudo udevadm control --reload-rules
```

On Windows, if you need to you can install the WinUSB driver over the WCH interface 1.

### Usage
To upload firmware, you should make the following connections to the WCH-LinkE (SWCLK is not present on the CH32V003 and therefore does not need to be connected):

```
WCH-LinkE      CH32Vxxx
+-------+      +------+
|  SWCLK| ---> |SWCLK |
|  SWDIO| <--> |SWDIO |
|    GND| ---> |GND   |
|    3V3| ---> |VDD   |
+-------+      +------+
```

If the blue LED on the WCH-LinkE remains illuminated once it is connected to the USB port, it means that the device is currently in ARM mode and must be switched to RISC-V mode initially. There are a few ways to accomplish this:
- You can utilize the rvprog tool with the -v option (see below).
- Alternatively, you can select "WCH-LinkRV" in the software provided by WCH, such as MounRiver Studio or WCH-LinkUtility.
- Another option is to hold down the ModeS button on the device while plugging it into the USB port.

More information can be found in the [WCH-Link User Manual](http://www.wch-ic.com/downloads/WCH-LinkUserManual_PDF.html).

```
Usage: rvprog.py [-h] [-a] [-v] [-b] [-u] [-l] [-e] [-G] [-R] [-f FLASH]

Optional arguments:
  -h, --help                show help message and exit
  -a, --armmode             switch WCH-Link to ARM mode
  -v, --rvmode              switch WCH-Link to RISC-V mode
  -b, --unbrick             unbrick chip
  -u, --unlock              unlock chip (remove read protection)
  -l, --lock                lock chip (set read protection)
  -e, --erase               perform a whole chip erase
  -G, --pingpio             make nRST pin a GPIO pin
  -R, --pinreset            make nRST pin a reset pin
  -f FLASH, --flash FLASH   write BIN file to flash

Example:
python3 rvprog.py -f firmware.bin
```

## puyaisp
### Description
With this tool, PUYA microcontrollers of the series PY32F0xx (and maybe other PY32) can be flashed via a simple USB-to-serial converter by utilizing the factory built-in embedded bootloader.

### Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

### Usage
Connect your USB-to-serial converter to your PY32F0xx MCU as follows:

```
USB2SERIAL            PY32F0xx
+--------+      +-------------------+
|     RXD| <--- |PA2 or PA9  or PA14|
|     TXD| ---> |PA3 or PA10 or PA15|
|     VDD| ---> |VDD                |
|     GND| ---> |GND                |
+--------+      +-------------------+
```

Set your MCU to bootloader mode by using ONE of the following methods:
- Disconnect your USB-to-serial converter, pull BOOT0 pin (PF4) to VCC (or press and hold the BOOT button, if your board has one), then connect the converter to your USB port. BOOT0 pin (or BOOT button) can be released now.
- Connect your USB-to-serial converter to your USB port. Pull BOOT0 pin (PF4) to VCC, then pull nRST (PF2) shortly to GND (or press and hold the BOOT button, then press and release the RESET button and then release the BOOT button, if your board has them).

These steps are not necessary when using a CH340X USB-to-serial converter with control lines for nRST and BOOT0. In this case, the software automatically puts the MCU into bootloader mode.

```
Usage: puyaisp.py [-h] [-u] [-l] [-e] [-o] [-G] [-R] [-f FLASH]

Optional arguments:
  -h, --help                show this help message and exit
  -u, --unlock              unlock chip (remove read protection)
  -l, --lock                lock chip (set read protection)
  -e, --erase               perform chip erase (implied with -f)
  -o, --rstoption           reset option bytes
  -G, --nrstgpio            make nRST pin a GPIO pin
  -R, --nrstreset           make nRST pin a RESET pin
  -f FLASH, --flash FLASH   write BIN file to flash and verify

Example:
python3 puyaisp.py -f firmware.bin
```

## stc8isp
### Description
With this tool, STC8G/8H microcontrollers can be flashed via a simple USB-to-serial converter by utilizing the factory built-in embedded bootloader.

### Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

### Usage
- Connect your USB-to-serial converter to your MCU and to a USB port of your PC.
- Run stc8isp.py (see below for arguments).
- Perform a power cycle of your MCU (reconnect to power) when prompted.

```
Usage: stc8isp.py [-h] [-p PORT] [-e] [-f FLASH]

Optional arguments:
  -h, --help                show this help message and exit
  -p PORT, --port PORT      set COM port (default: /dev/ttyUSB0)
  -e, --erase               perform chip erase (implied with -f)
  -f FLASH, --flash FLASH   write BIN file to flash

Example:
python3 stc8isp.py -p /dev/ttyUSB0 -f firmware.bin
```

## stm32isp
### Description
With this tool, some entry-level STM32 microcontrollers can be flashed via a simple USB-to-serial converter by utilizing the factory built-in embedded bootloader. It currently supports the following devices:
- STM32F03xx4/6
- STM32G03x/04x
- STM32L01x/02x

### Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

### Usage
Connect your USB-to-serial converter to your STM32 MCU as follows:

```
USB2SERIAL      STM32F03xx4/6
+--------+      +------------+
|     RXD| <--- |PA9  or PA14|
|     TXD| ---> |PA10 or PA15|
|     3V3| ---> |VDD (3V3)   |
|     GND| ---> |GND         |
+--------+      +------------+

USB2SERIAL      STM32G03x/04x
+--------+      +------------+
|     RXD| <--- |PA2 or PA9  |
|     TXD| ---> |PA3 or PA10 |
|     3V3| ---> |VDD (3V3)   |
|     GND| ---> |GND         |
+--------+      +------------+

USB2SERIAL      STM32L01x/02x
+--------+      +------------+
|     RXD| <--- |PA2 or PA9  |
|     TXD| ---> |PA3 or PA10 |
|     3V3| ---> |VDD (3V3)   |
|     GND| ---> |GND         |
+--------+      +------------+
```

Set your MCU to boot mode by using ONE of the following method:
- Disconnect your board from all power supplies, pull BOOT0 pin to VCC (or press and hold the BOOT button if your board has one), then connect the board to your USB port. The BOOT button can be released now.
- Connect your USB-to-serial converter to your USB port. Pull BOOT0 pin to VCC, then pull nRST shortly to GND (or press and hold the BOOT button, then press and release the RESET button and then release the BOOT button, if your board has them).

On STM32G03x/04x microcontrollers, the BOOT0 pin is initially disabled. When the chip is brand new or the main flash memory is erased, this isn't an issue as the embedded bootloader automatically kicks in. By using the stm32isp tool, the BOOT0 pin will be activated for subsequent use. However, if the chip has been previously programmed using a different software tool, the bootloader might not be accessible through the BOOT0 pin anymore. In such cases, the nBOOT_SEL bit in the User Option Bytes must be cleared (set to 0) using an SWD programmer like ST-Link and the appropriate software.

```
Usage: stm32isp.py [-h] [-u] [-l] [-e] [-f FLASH]

Optional arguments:
  -h, --help                show this help message and exit
  -u, --unlock              unlock chip (remove read protection)
  -l, --lock                lock chip (set read protection)
  -e, --erase               perform chip erase (implied with -f)
  -f FLASH, --flash FLASH   write BIN file to flash and verify

Example:
python3 stm32isp.py -f firmware.bin
```

## tinyupdi
### Description
This tool allows tinyAVR series 0, 1, and 2 microcontrollers to be programmed using a USB-to-serial converter connected in a special way to the UPDI pin (also called SerialUPDI). More information can be found [here](https://github.com/SpenceKonde/AVR-Guidance/blob/master/UPDI/jtag2updi.md).

### Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

### Usage
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
Usage: tinyupdi.py [-h] [-d DEVICE] [-e] [-f FLASH] [-fs [FUSES [FUSES ...]]]

Optional arguments:
  -h, --help                show help message and exit
  -d, --device              set target device (if not set, it will be auto-detected)
  -e, --erase               perform a chip erase (implied with --flash)
  -f FLASH, --flash FLASH   BIN file to flash
  -fs [FUSES [FUSES ...]], --fuses [FUSES [FUSES ...]]
                            fuses to set (syntax: fuse_nr:0xvalue)
Example:
python3 tinyupdi.py -f firmware.bin -fs 2:0x01 6:0x04 8:0x00
```

## Links
1. [MCU Templates](https://github.com/wagiminator/MCU-Templates)
2. [MCU Development Boards](https://github.com/wagiminator/Development-Boards)
3. [AVR Development Boards](https://github.com/wagiminator/AVR-Development-Boards)
4. [SerialUPDI Programmers](https://github.com/wagiminator/AVR-Programmer)
