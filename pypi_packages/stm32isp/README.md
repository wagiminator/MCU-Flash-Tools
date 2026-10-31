#  Programming Tool for STM32 Microcontrollers
## Description
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

## Preparations
If necessary, a driver for the USB-to-serial converter used must be installed.

## Installation
Ensure that the [prerequisites](https://packaging.python.org/en/latest/tutorials/installing-packages/) for installing Python packages are met. Then execute the following command in the command line:

```
pip install stm32isp
```

## Usage
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
Usage: stm32isp [-h] [-u] [-l] [-e] [-f FLASH]

Optional arguments:
  -h, --help                show this help message and exit
  -u, --unlock              unlock chip (remove read protection)
  -l, --lock                lock chip (set read protection)
  -e, --erase               perform chip erase (implied with -f)
  -f FLASH, --flash FLASH   write BIN file to flash and verify

Example:
stm32isp -f firmware.bin
```

## Links
- [MCU Flash Tools](https://github.com/wagiminator/MCU-Flash-Tools)
- [MCU Templates](https://github.com/wagiminator/MCU-Templates)
- [MCU Development Boards](https://github.com/wagiminator/Development-Boards)
- [AVR Development Boards](https://github.com/wagiminator/AVR-Development-Boards)
- [AVR Programmers](https://github.com/wagiminator/AVR-Programmer)
- [SAMD Development Boards](https://github.com/wagiminator/SAMD-Development-Boards)
