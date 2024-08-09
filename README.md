# MCU ISP Flash Tools
This is a compilation of straightforward In-System Programming (ISP) flash tools for different microcontrollers, all written as individual Python scripts. Their single-script format makes them incredibly easy to integrate into any toolchain. Furthermore, these tools can also be installed via pip and then executed as command-line commands.

- [chprog.py - Flashing CH5xx, CH32Fxxx, CH32Vxxx, CH32Xxxx via embedded USB bootloader](#chprog)
- [rvprog.py - Flashing CH32Vxxx with WCH-LinkE via serial debug interface](#rvprog)
- [puyaisp.py - Flashing PY32F0xx with USB-to-serial converter via embedded UART bootloader](#puyaisp)
- [stc8isp.py - Flashing STC8G/8H with USB-to-serial converter via embedded UART bootloader](#stc8isp)
- [stc8usb.py - Flashing STC8H8KxxU via embedded USB bootloader](#stc8usb)
- [stm32isp.py - Flashing entry-level STM32 with USB-to-serial converter via embedded UART bootloader](#stm32isp)
- [tinyupdi.py - Flashing tinyAVR with USB-to-serial converter via UPDI](#tinyupdi)

In order for these tools to work, Python3 must be installed on your system. To do this, follow these [instructions](https://www.pythontutorial.net/getting-started/install-python/). In addition [PyUSB](https://github.com/pyusb/pyusb), [PySerial](https://github.com/pyserial/pyserial) and [pyhidapi](https://pypi.org/project/hid/) must be installed. On Linux (Debian-based), all of this can be done with the following commands:

```
sudo apt install python3 python3-pip
pip install pyusb pyserial hid
```

Windows users in particular may also need to install [libusb](https://github.com/libusb/libusb).

## chprog
### Description
With this tool, almost all WCH microcontrollers (CH5xx, CH6xx, CH32Fxxx, CH32Vxxx, CH32Xxxx, and CH32Lxxx) which have a factory-builtin bootloader (v2.x.x) can be flashed via USB.

### Preparations
On Linux you do not need to install a driver for the USB bootloader. However, by default Linux will not expose enough permission to upload your code. In order to fix this, open a terminal and run the following commands:

```
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="4348", ATTR{idProduct}=="55e0", MODE="666"' | sudo tee /etc/udev/rules.d/99-ch55x.rules
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", ATTR{idProduct}=="55e0", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-ch55x.rules
sudo udevadm control --reload-rules
```

For Windows, you need the [CH372 driver](http://www.wch-ic.com/downloads/CH372DRV_EXE.html). Alternatively, you can also use the [Zadig](https://zadig.akeo.ie/) tool to install the correct driver. Here, click "Options" -> "List All Devices" and select the USB module. Then install the libusb-win32 driver. To do this, the board must be connected and the microcontroller must be in bootloader mode.

### Usage as a Script
The bootloader must be started manually for new uploads. To do this, the board must first be disconnected from the USB port and all voltage sources. Now press the BOOT button and keep it pressed while reconnecting the board to the USB port of your PC. The chip now starts in bootloader mode, the BOOT button can be released and new firmware can be uploaded via USB. Alternatively, you can leave the board connected to the USB port, press and hold the BOOT button, press and release the RESET button and then release the BOOT button to enter the bootloader mode. If there is no BOOT button on the board, look at the datasheet to find out which pin needs to be pulled to which voltage level for the microcontroller to go into boot mode.

Now run the following command (example):
```
python3 chprog.py firmware.bin
```

### Installation via pip
Take a look [here](https://pypi.org/project/chprog/).

## rvprog
### Description
With this tool, the WCH RISC-V microcontrollers CH32Lxxx, CH32Vxxx, and CH32Xxxx can be programmed with the [WCH-LinkE](http://www.wch-ic.com/products/WCH-Link.html) (pay attention to the "E" in the name) via its serial debug interface.

### Preparations
To use the WCH-Link on Linux, you need to grant access permissions beforehand by executing the following commands:
```
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", ATTR{idProduct}=="8010", MODE="666"' | sudo tee /etc/udev/rules.d/99-WCH-LinkE.rules
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", ATTR{idProduct}=="8012", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-WCH-LinkE.rules
sudo udevadm control --reload-rules
```

On Windows, if you need to you can install the WinUSB driver over the WCH interface 1 using the [Zadig](https://zadig.akeo.ie/) tool.

### Usage as a Script
To upload firmware, you should make the following connections to the WCH-LinkE (SWCLK is not present on the CH32V003 and therefore does not need to be connected):

```
WCH-LinkE       CH32V/X
+-------+      +-------+
|  SWCLK| ---> |SWCLK  |
|  SWDIO| <--> |SWDIO  |
|    GND| ---> |GND    |
|    3V3| ---> |VDD    |
+-------+      +-------+
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
  -b, --unbrick             unbrick chip (power cycle erase)
  -u, --unlock              unlock chip (remove read protection)
  -l, --lock                lock chip (set read protection)
  -e, --erase               perform a whole chip erase
  -G, --pingpio             make nRST pin a GPIO pin (CH32V003 only)
  -R, --pinreset            make nRST pin a reset pin (CH32V003 only)
  -f FLASH, --flash FLASH   write BIN file to flash

Example:
python3 rvprog.py -f firmware.bin
```

### Installation via pip
Take a look [here](https://pypi.org/project/rvprog/).

## puyaisp
### Description
With this tool, PUYA microcontrollers of the series PY32F0xx (and maybe other PY32) can be flashed via a simple USB-to-serial converter by utilizing the factory built-in embedded bootloader.

### Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

### Usage as a Script
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

### Installation via pip
Take a look [here](https://pypi.org/project/puyaisp/).

## stc8isp
### Description
With this tool, STC8G/8H microcontrollers can be flashed via a simple USB-to-serial converter by utilizing the factory built-in embedded bootloader.

### Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

### Usage as a Script
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
Usage: stc8isp.py [-h] [-p PORT] [-t TRIM] [-e] [-f FLASH]

Optional arguments:
  -h,       --help          show this help message and exit
  -p PORT,  --port PORT     set COM port (default: /dev/ttyUSB0)
  -t TRIM,  --trim TRIM     trim IRC to frequency in Hz (128000 - 36000000)
  -e,       --erase         perform chip erase (implied with -f)
  -f FLASH, --flash FLASH   write BIN file to flash

Example:
python3 stc8isp.py -p /dev/ttyUSB0 -t 24000000 -f firmware.bin
```

### Installation via pip
Take a look [here](https://pypi.org/project/stc8isp/).

## stc8usb
## Description
This tool allows you to flash STC8H8KxxU microcontrollers through their USB interface, using the pre-installed embedded USB bootloader.

## Preparations
Because the USB bootloader functions as a Human Interface Device (HID), there's no need to install drivers. However, Linux doesn't initially grant sufficient permissions to access the bootloader. To resolve this issue, open a terminal and execute the following commands:

```
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="34bf", ATTR{idProduct}=="1001", MODE="666"' | sudo tee /etc/udev/rules.d/99-STC-ISP.rules
sudo udevadm control --reload-rules
```

### Usage as a Script
To initiate new uploads, the bootloader needs to be manually started. Begin by unplugging the board from the USB port and disconnecting all power sources. Then, press and hold the BOOT button while reconnecting the board to your PC's USB port. This action triggers the chip to enter bootloader mode. Once in this mode, you can release the BOOT button and proceed to upload new firmware via USB.

If your board doesn't have a BOOT button, you'll need to short pin P3.2 to ground while connecting to achieve the same effect.

```
Usage: stc8usb.py [-h] [-t TRIM] [-e] [-f FLASH]

Optional arguments:
  -h,       --help          show this help message and exit
  -t TRIM,  --trim TRIM     set MCU system frequency
  -e,       --erase         perform chip erase (implied with -f)
  -f FLASH, --flash FLASH   write BIN file to flash

Example:
python3 stc8usb.py -t 24000000 -f firmware.bin
```

### Installation via pip
Take a look [here](https://pypi.org/project/stc8usb/).

## stm32isp
### Description
With this tool, some entry-level STM32 microcontrollers can be flashed via a simple USB-to-serial converter by utilizing the factory built-in UART bootloader. It currently supports the following devices:
- STM32C011/031
- STM32F03xx4/6
- STM32G03x/04x
- STM32L01x/02x

### Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

### Usage as a Script
Connect your USB-to-serial converter to your STM32 MCU as follows:

```
USB2SERIAL      STM32C011/031
+--------+      +------------+
|     RXD| <--- |PA9  (PA11) |
|     TXD| ---> |PA10 (PA12) |
|     3V3| ---> |VDD (3V3)   |
|     GND| ---> |GND         |
+--------+      +------------+

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

### Installation via pip
Take a look [here](https://pypi.org/project/stm32isp/).

## tinyupdi
### Description
This tool allows tinyAVR series 0, 1, and 2 microcontrollers to be programmed using a USB-to-serial converter connected in a special way to the UPDI pin (also called SerialUPDI). More information can be found [here](https://github.com/SpenceKonde/AVR-Guidance/blob/master/UPDI/jtag2updi.md).

### Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

### Usage as a Script
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
  -t TRIM, --trim TRIM      configure oscillator for given frequency (set fuse 2)
Example:
python3 tinyupdi.py -f firmware.bin -fs 6:0x04 7:0x00 8:0x00 -t 8000000
```

### Installation via pip
Take a look [here](https://pypi.org/project/tinyupdi/).

## Links
1. [MCU Templates](https://github.com/wagiminator/MCU-Templates)
2. [MCU Development Boards](https://github.com/wagiminator/Development-Boards)
3. [AVR Development Boards](https://github.com/wagiminator/AVR-Development-Boards)
4. [SerialUPDI Programmers](https://github.com/wagiminator/AVR-Programmer)
