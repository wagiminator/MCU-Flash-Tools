#  USB Programming Tool for STC8H8KxxU Microcontrollers
## Description
This tool allows you to flash STC8H8KxxU microcontrollers through their USB interface, using the pre-installed embedded USB bootloader.

## Preparations
Because the USB bootloader functions as a Human Interface Device (HID), there's no need to install drivers. However, Linux doesn't initially grant sufficient permissions to access the bootloader. To resolve this issue, open a terminal and execute the following commands:

```
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="34bf", ATTR{idProduct}=="1001", MODE="666"' | sudo tee /etc/udev/rules.d/99-STC-ISP.rules
sudo udevadm control --reload-rules
```

## Installation
Ensure that the [prerequisites](https://packaging.python.org/en/latest/tutorials/installing-packages/) for installing Python packages are met. Then execute the following command in the command line:

```
pip install stc8usb
```

## Usage
To initiate new uploads, the bootloader needs to be manually started. Begin by unplugging the board from the USB port and disconnecting all power sources. Then, press and hold the BOOT button while reconnecting the board to your PC's USB port. This action triggers the chip to enter bootloader mode. Once in this mode, you can release the BOOT button and proceed to upload new firmware via USB.

If your board doesn't have a BOOT button, you'll need to short pin P3.2 to ground while connecting to achieve the same effect.

```
Usage: stc8usb [-h] [-t TRIM] [-e] [-f FLASH]

Optional arguments:
  -h,       --help          show this help message and exit
  -t TRIM,  --trim TRIM     set MCU system frequency
  -e,       --erase         perform chip erase (implied with -f)
  -f FLASH, --flash FLASH   write BIN file to flash

Example:
stc8usb -t 24000000 -f firmware.bin
```

## Links
- [MCU Flash Tools](https://github.com/wagiminator/MCU-Flash-Tools)
- [MCU Templates](https://github.com/wagiminator/MCU-Templates)
- [MCU Development Boards](https://github.com/wagiminator/Development-Boards)
- [AVR Development Boards](https://github.com/wagiminator/AVR-Development-Boards)
- [AVR Programmers](https://github.com/wagiminator/AVR-Programmer)
- [SAMD Development Boards](https://github.com/wagiminator/SAMD-Development-Boards)
