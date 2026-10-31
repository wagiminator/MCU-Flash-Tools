# MCU ISP Flash Tools
This is a compilation of straightforward In-System Programming (ISP) flash tools for different microcontrollers, all written as individual Python scripts. Their single-script format makes them incredibly easy to integrate into any toolchain. Furthermore, these tools can also be installed via pip and then executed as command-line commands.

- [chprog.py   - Flashing CH5xx, CH32Fxxx, CH32Vxxx, CH32Xxxx via embedded USB bootloader](#chprog)
- [rvprog.py   - Flashing CH32Vxxx with WCH-LinkE via serial debug interface](#rvprog)
- [puyaisp.py  - Flashing PY32F0xx with USB-to-serial converter via embedded UART bootloader](#puyaisp)
- [stm32isp.py - Flashing STM32 with USB-to-serial converter via embedded UART bootloader](#stm32isp)
- [tinyocd.py  - Flashing STM32, PY32, and ATSAMD via DAPLink, ST-Link, or J-Link](#tinyocd)
- [tinyupdi.py - Flashing tinyAVR with USB-to-serial converter via UPDI](#tinyupdi)
- [megaupdi.py - Flashing modern AVRs with USB-to-serial converter via UPDI](#megaupdi)
- [avrprog.py  - Flashing classic AVRs via ISP with USBasp or USBtinyISP](#avrprog)
- [stc8isp.py  - Flashing STC8G/8H with USB-to-serial converter via embedded UART bootloader](#stc8isp)
- [stc8usb.py  - Flashing STC8H8KxxU via embedded USB bootloader](#stc8usb)

In order for these tools to work, Python3 must be installed on your system. To do this, follow these [instructions](https://www.pythontutorial.net/getting-started/install-python/). In addition [PyUSB](https://github.com/pyusb/pyusb), [PySerial](https://github.com/pyserial/pyserial) and [pyhidapi](https://pypi.org/project/hid/) must be installed. On Linux (Debian-based), all of this can be done with the following commands:

```
sudo apt install python3 python3-pip
pip install pyusb pyserial hid
```

Windows users in particular may also need to install [libusb](https://github.com/libusb/libusb).

## chprog
### Description
With this tool, almost all WCH microcontrollers (CH5xx, CH6xx, CH32Fxxx, CH32Vxxx, CH32Xxxx, and CH32Lxxx) which have a factory-builtin bootloader (v2.x.x) can be flashed via USB.

Supported microcontrollers: CH54x, CH55x, CH56x, CH57x, CH58x (incl. CH584/CH585), CH59x, CH643, CH32F103, CH32F20x, CH32V103, CH32V20x, CH32V30x, CH32V317, CH32X03x and CH32L103. Microcontrollers without a USB bootloader (e.g. CH32V00x) are not supported.

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

### Web-App
You can try the web browser port [here](https://wagiminator.github.io/apps/chprog/).

## rvprog
### Description
With this open-source platform-independant command-line tool, WCH RISC-V microcontrollers can be programmed using a RISC-V compatible [WCH-Link](http://www.wch-ic.com/products/WCH-Link.html) via their serial debug interface.

The tool currently supports the following microcontrollers:
- CH32V002, CH32V003, CH32V004, CH32V005, CH32V006, CH32V007, CH32M007,
- CH32V103, CH32V203, CH32V205, CH32V208, CH32V303, CH32V305, CH32V307, CH32V317,
- CH32V406, CH32V407, CH32V467, CH32H415, CH32H416, CH32H417,
- CH32X033, CH32X035, CH32X305, CH32X315,
- CH32L103, CH32M103, CH32M030,
- CH641, CH643, CH645,
- CH565, CH569, CH571, CH573, CH581, CH582, CH583, CH584, CH585, CH591, CH592.

Read protection (-l/-u) is not available for CH643 and the CH5xx series. The CH32V205 requires WCH-Link firmware v3.6 or newer.

The tool currently supports the following programmers:
- WCH-LinkB,
- WCH-LinkE,
- WCH-LinkW,
- other compatible programmers.

### Preparations
To use the WCH-Link on Linux, you need to grant access permissions beforehand by executing the following commands:
```
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", ATTR{idProduct}=="8010", MODE="666"' | sudo tee /etc/udev/rules.d/99-WCH-LinkE.rules
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", ATTR{idProduct}=="8012", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-WCH-LinkE.rules
sudo udevadm control --reload-rules
```

On Windows, if you need to you can install the WinUSB driver over the WCH interface 1 using the [Zadig](https://zadig.akeo.ie/) tool. The libusb backend is installed automatically with the package (libusb-package).

### Usage as a Script
To upload firmware, you should make the following connections to the WCH-Link (SWCLK is not present on CH32V00x and therefore does not need to be connected):

```
WCH-Link      RISC-V MCU
+------+      +--------+
| SWCLK| ---> |SWCLK   |
| SWDIO| <--> |SWDIO   |
|   GND| ---> |GND     |
|   3V3| ---> |VDD     |
+------+      +--------+
```

If the blue LED on the WCH-Link remains illuminated once it is connected to the USB port, it means that the device is currently in ARM mode and must be switched to RISC-V mode initially. There are a few ways to accomplish this:
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
  -G, --pingpio             make PD7 a GPIO pin (CH32V00x only)
  -R, --pinreset            make PD7 a reset pin (CH32V00x only)
  -f FLASH, --flash FLASH   write BIN file to flash

Example:
python3 rvprog.py -f firmware.bin
```

### Installation via pip
Take a look [here](https://pypi.org/project/rvprog/).

### Web-App
You can try the web browser port [here](https://wagiminator.github.io/apps/rvprog/).

## puyaisp
### Description
With this tool, PUYA PY32 microcontrollers can be flashed via a simple USB-to-serial converter by utilizing the factory built-in embedded UART/HID bootloader.

Supported microcontrollers (identified by the bootloader PID):

|Bootloader PID|Microcontrollers|Interfaces|
|:-|:-|:-|
|0x440|PY32F002A, PY32F003, PY32F030|UART|
|0x448|PY32F071, PY32F072, PY32F040|UART, USB HID|
|0x413|PY32F403, PY32F303|UART|

Other PY32 microcontrollers with the same bootloader protocol can be flashed as well, but their option bytes cannot be changed. PY32F002B and PY32L020 have no UART bootloader in system memory and are not supported.

### Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

### Usage as a Script
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
python3 puyaisp -f firmware.bin
python3 puyaisp -t hid -f firmware.bin
```

### Installation via pip
Take a look [here](https://pypi.org/project/puyaisp/).

### Web-App
You can try the web browser port [here](https://wagiminator.github.io/apps/puyaisp/).

## stm32isp
### Description
With this tool, STM32 microcontrollers can be flashed via a simple USB-to-serial converter by utilizing the factory built-in UART bootloader (protocol ST AN3155). The chip is identified by the product ID reported by the bootloader. It currently supports the following devices (ST AN2606):
- STM32C0: C011, C031, C051, C071, C091/092
- STM32F0: F03x, F04x, F05x, F07x, F09x
- STM32F1: F10x low/medium/high/XL-density, value line, connectivity line
- STM32F2: F20x/21x
- STM32F3: F301/302/303/318/328/334/358/373/378/398
- STM32F4: F401/405/407/410/411/412/413/415/417/42x/43x/446/469/479
- STM32F7: F72x/73x/74x/75x/76x/77x
- STM32G0: G03x/04x/05x/06x/07x/08x/0Bx/0C1
- STM32G4: G431/441/47x/48x/491/4A1
- STM32H5: H503/563/573
- STM32H7: H72x/73x/74x/75x/7A3/7B3
- STM32L0: L01x/02x/031/041/05x/06x/07x/08x
- STM32L1: all categories
- STM32L4: L41x/42x/43x/44x/45x/46x/47x/48x/49x/4Ax/4Px/4Qx/4Rx/4Sx
- STM32L5: L552/562
- STM32U5: U535/545/575/585/595/599/5A9
- STM32WB: WB10/15/30/35/50/55
- STM32WL: WLE5/WL55

### Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

### Usage as a Script
Connect your USB-to-serial converter to the bootloader USART of your STM32 MCU. USART1 (RXD <--- PA9, TXD ---> PA10) is available on all supported devices, see ST AN2606 for further USARTs. Examples:

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

On STM32C0 and STM32G0 microcontrollers, the BOOT0 pin is initially disabled. When the chip is brand new or the main flash memory is erased, this isn't an issue as the embedded bootloader automatically kicks in. By using the stm32isp tool, the BOOT0 pin will be activated for subsequent use. However, if the chip has been previously programmed using a different software tool, the bootloader might not be accessible through the BOOT0 pin anymore. In such cases, the nBOOT_SEL bit in the User Option Bytes must be cleared (set to 0) using an SWD programmer like ST-Link and the appropriate software.

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

## tinyocd
### Description
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

### Preparations
Linux users need permission to access the programmer. Run:

```
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0483", MODE="666"' | sudo tee /etc/udev/rules.d/99-tinyocd.rules
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1366", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-tinyocd.rules
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0d28", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-tinyocd.rules
echo 'KERNEL=="hidraw*", ATTRS{idVendor}=="0d28", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-tinyocd.rules
sudo udevadm control --reload-rules
```

Add further lines for the vendor IDs of other CMSIS-DAP programmers (e.g. 2e8a, c251, 1a86).

On Windows, ST-Link (with ST driver) and CMSIS-DAP v2 (WinUSB) normally work out of the box. A J-Link must use the WinUSB driver (J-Link Configurator: "Use WinUSB") or a libusb driver installed with [Zadig](https://zadig.akeo.ie/).

### Usage as a Script
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
python3 tinyocd -f firmware.bin
```

Notes:
- The BIN file is written to the start of the flash memory (0x08000000 for STM32/PY32, 0x00000000 for SAMD).
- If the chip cannot be halted (e.g. SWD pins disabled by the firmware), tinyOCD connects under reset. For this, NRST must be connected to the programmer.
- On SAMD chips, a bootloader protected by the BOOTPROT fuse cannot be overwritten. A chip erase (-e) does not clear the BOOTPROT fuse.
- With -B the BOOT0 pin is enabled via option bytes. On STM32C0/G0 the BOOT0 pin is shared with SWCLK (PA14).

### Installation via pip
Take a look [here](https://pypi.org/project/tinyocd/).

## tinyupdi
### Description
This tool allows tinyAVR series 0, 1, and 2 microcontrollers to be programmed using a USB-to-serial converter connected in a special way to the UPDI pin (also called SerialUPDI). More information can be found [here](https://github.com/SpenceKonde/AVR-Guidance/blob/master/UPDI/jtag2updi.md).

Supported microcontrollers (all tinyAVR with UPDI):
- tinyAVR 0-series: ATtiny202, 204, 402, 404, 406, 804, 806, 807, 1604, 1606, 1607
- tinyAVR 1-series: ATtiny212, 214, 412, 414, 416, 417, 814, 816, 817, 1614, 1616, 1617, 3216, 3217
- tinyAVR 2-series: ATtiny424, 426, 427, 824, 826, 827, 1624, 1626, 1627, 3224, 3226, 3227

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

A locked device is only unlocked (by a chip erase) when -e or -f is given. Changing fuse 5 (SYSCFG0) can disable the UPDI pin; the device can then only be programmed with a high-voltage programmer.

### Installation via pip
Take a look [here](https://pypi.org/project/tinyupdi/).

### Web-App
You can try the web browser port [here](https://wagiminator.github.io/apps/tinyupdi/).

## megaupdi
### Description
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

### Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

### Usage as a Script
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

python3 megaupdi -d avr128da28 -f firmware.bin -fs 0:0x00 1:0x00
python3 megaupdi -f firmware.bin -fs 6:0x04 7:0x00 8:0x00 -t 8000000
```

Notes:
- Fuse numbers are relative to the first fuse (FUSE0). Valid numbers depend on the device family: tinyAVR/megaAVR 0: 0 - 10 (10 = LOCKBIT), AVR Dx/Ex/Lx/Sx: e.g. 0, 1, 2, 5, 6, 7, 8 (plus 10 on some families). Invalid fuse numbers are rejected before anything is erased or written.
- -t sets the oscillator fuse (16 or 20 MHz) on tinyAVR, megaAVR 0, AVR EA/EB and AVR LA. The system frequency must be reachable with the clock prescaler, which has to be set by the firmware.
- A locked device is only unlocked (by a chip erase) when -e or -f is given.
- Changing the pin configuration fuse can disable the UPDI pin (tinyAVR: fuse 5, AVR DD/DU/EA/EB/EC: fuse 5, AVR LA: fuse 3); the device can then only be programmed with a high-voltage programmer. megaUPDI prints a warning in this case.
- Only flash and fuses can be programmed. EEPROM, user row, boot row and the lock bits of the AVR Dx/Ex/Lx/Sx families are not supported.

### Installation via pip
Take a look [here](https://pypi.org/project/megaupdi/).

## avrprog
### Description
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

### Preparations
Linux users need permission to access the device. Run:
```
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="16c0", ATTR{idProduct}=="05dc", MODE="666"' | sudo tee /etc/udev/rules.d/99-avrprog.rules
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1781", ATTR{idProduct}=="0c9f", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-avrprog.rules
sudo udevadm control --reload-rules
```

On Windows, PyUSB also needs a libusb backend ("pip install libusb-package") and the programmer needs a libusb compatible driver (WinUSB, libusb-win32 or libusbK, installable with [Zadig](https://zadig.akeo.ie).

### Usage as a Script
Connect the programmer to your PC and its ISP cable to the AVR.

```
Usage: avrprog.py [-h] [-t {usbasp,usbtiny}] [-p PART] [-B BITCLOCK] [-e] [-f FLASH] [-l LFUSE] [-H HFUSE] [-E EFUSE] [-L LOCK] [-r] [-F] [--list]

Optional arguments:
  -h, --help                show help message and exit
  -t, --programmer          programmer type (default: auto-detect)
  -p, --part                chip type (default: auto-detect by signature)
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
python3 avrprog.py -f firmware.hex -l 0xe2 -H 0xdf -E 0xff
```

### Installation via pip
Take a look [here](https://pypi.org/project/avrprog/).

### Web-App
You can try the web browser port [here](https://wagiminator.github.io/apps/avrisp/).

## stc8isp
### Description
With this tool, STC8G/8H microcontrollers can be flashed via a simple USB-to-serial converter by utilizing the factory built-in embedded UART bootloader.

The tool currently supports the following microcontrollers (bootloader v7.2 and later):
- STC8G1K, STC8G2K
- STC8H1K (incl. T versions), STC8H2K/4K TL/TLCD, STC8H3K, STC8H4K TLR/LCD, STC8H8K
- STC8A8K/STC8A2K D4

When trimming the IRC (-t), the other option bytes (MCS registers) of the MCU are retained.

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

Supported microcontrollers: STC8H8K16U, STC8H8K32U, STC8H8K48U, STC8H8K60U, STC8H8K64U.

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

Possible values for -t (Hz): 250000, 500000, 1000000, 1382400, 2000000, 2764800, 3000000, 4000000, 5000000, 5529600, 6000000, 8000000, 10000000, 11059200, 12000000, 16000000, 18432000, 20000000, 22118400, 24000000, 27000000, 30000000, 33177600, 35000000, 36864000, 40000000, 44236800, 48000000. The other option bytes of the MCU are retained.

### Installation via pip
Take a look [here](https://pypi.org/project/stc8usb/).

## Links
1. [MCU Templates](https://github.com/wagiminator/MCU-Templates)
2. [MCU Development Boards](https://github.com/wagiminator/Development-Boards)
3. [AVR Development Boards](https://github.com/wagiminator/AVR-Development-Boards)
4. [SerialUPDI Programmers](https://github.com/wagiminator/AVR-Programmer)
