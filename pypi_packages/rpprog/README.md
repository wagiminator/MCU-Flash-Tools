# USB Programming Tool for Raspberry Pi RP2040 and RP2350
## Description
With this tool, Raspberry Pi RP2040 and RP2350 microcontrollers (e.g. on the Raspberry Pi Pico, Pico W, Pico 2 and Pico 2 W) can be flashed via USB using the PICOBOOT interface of the factory built-in USB bootloader (BOOTSEL mode). In contrast to drag-and-drop, the USB drive does not need to be mounted. Firmware can be written from BIN, UF2, Intel HEX and ELF files and is verified afterwards. In addition, the flash can be erased and read, and a running firmware can be restarted into BOOTSEL mode.

Supported microcontrollers: RP2040, RP2350A, RP2350B (Arm and RISC-V firmware), RP2354A/B.

## Preparations
On Linux you do not need to install a driver. However, by default Linux will not expose enough permission to upload your code. In order to fix this, open a terminal and run the following commands:

```
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="2e8a", ATTR{idProduct}=="0003", MODE="666"' | sudo tee /etc/udev/rules.d/99-rp2-boot.rules
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="2e8a", ATTR{idProduct}=="000f", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-rp2-boot.rules
sudo udevadm control --reload-rules
```

On Windows, the PICOBOOT interface of the RP2040 needs the WinUSB driver. Install it with the [Zadig](https://zadig.akeo.ie/) tool: click "Options" -> "List All Devices", select "RP2 Boot (Interface 1)" and install the WinUSB driver. The board must be connected in BOOTSEL mode. The RP2350 provides the necessary Microsoft OS descriptors, so Windows usually installs the driver automatically.

## Installation
Ensure that the [prerequisites](https://packaging.python.org/en/latest/tutorials/installing-packages/) for installing Python packages are met. Then execute the following command in the command line:

```
pip install rpprog
```

## Usage
To enter the USB bootloader (BOOTSEL mode), hold the BOOTSEL button while connecting the board to the USB port of your PC, then release the button. Alternatively, `-b` restarts a running firmware into BOOTSEL mode, either via the reset interface of the Raspberry Pi Pico SDK (stdio_usb) or via a "1200 baud touch" of a USB serial port (e.g. MCU-Templates usb_cdc library, Arduino cores). If several serial ports are present, select the port with `-p`.

The flash size is detected automatically by searching for mirrored data, which requires a non-empty flash. If the flash is empty, the default size of the Raspberry Pi Pico (2MB) or Pico 2 (4MB) is used for `-e` and `-r`; use `-s` to set another size. Before writing, rpprog checks whether the image contains a valid second stage bootloader (RP2040) or an IMAGE_DEF block (RP2350) and shows a warning if not. UF2 files of the wrong chip family are rejected.

```
Usage: rpprog [-h] [-b] [-p PORT] [-e] [-f FLASH] [-a ADDR] [-r READ]
              [-s SIZE] [-x] [-n]

Optional arguments:
  -h, --help                show this help message and exit
  -b, --bootsel             restart running firmware into BOOTSEL mode first
  -p PORT, --port PORT      serial port for the 1200 baud touch (with -b)
  -e, --erase               perform a whole chip erase
  -f FLASH, --flash FLASH   write BIN/UF2/HEX/ELF file to flash and verify
  -a ADDR, --address ADDR   flash address for BIN files (default: 0x10000000)
  -r READ, --read READ      read flash and save it as BIN file
  -s SIZE, --size SIZE      size for -e and -r (default: detected flash size)
  -x, --reboot              reboot and start firmware (implied with -e and -f)
  -n, --noreboot            stay in BOOTSEL mode after -e or -f

Without action arguments, rpprog shows the chip, its bootrom version, 
the flash size and whether a bootable firmware is present.

Examples:
rpprog -f firmware.uf2
rpprog -b -f firmware.bin
rpprog -r backup.bin
```

## Links
- [MCU Flash Tools](https://github.com/wagiminator/MCU-Flash-Tools)
- [MCU Templates](https://github.com/wagiminator/MCU-Templates)
- [MCU Development Boards](https://github.com/wagiminator/Development-Boards)
- [Raspberry Pi picotool](https://github.com/raspberrypi/picotool)
