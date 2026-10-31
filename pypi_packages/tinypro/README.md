# Programming Tool for (E)EPROMs and Flash Memory ICs via XGecu TL866A, TL866CS, TL866II+, T48 and T56
## Description
With this tool, (E)EPROMs and flash memory ICs can be read, written and verified as binary images using the XGecu TL866A, TL866CS, TL866II+, T48 and T56 universal programmers. The programmer is detected automatically. SPI flash chips are detected automatically by their JEDEC ID; all other chips are selected by name (the chip ID is checked if the chip has one).

Supported memory types (over 22,000 chip names for the TL866II+/T48/T56 and over 12,000 for the TL866A/CS), among others:
- parallel EPROMs, OTP EPROMs and EEPROMs (27Cxxx, 28Cxxx, ...), also 16 bit (27C1024, ...)
- parallel flash (29Fxxx, 39SFxxx, 49Fxxx, 28Fxxx, ...), also in TSOP/PLCC/SOP packages with adapter
- SPI flash and SPI EEPROMs (25xxx), AT45 DataFlash, FWH/LPC flash
- I2C EEPROMs (24Cxx) and Microwire EEPROMs (93Cxx)

All other functions of the programmers (MCUs, PLDs, logic IC tests, ICSP, ...) are deliberately not supported. Use `tinypro --list PATTERN` to search the supported chips.

The tool is a Python port of the relevant parts of [minipro](https://gitlab.com/DavidGriffith/minipro); the chip database was generated from minipro's infoic.xml.

## Preparations
Linux users need permission to access the programmer. Run:
```
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="04d8", ATTR{idProduct}=="e11c", MODE="666"' | sudo tee /etc/udev/rules.d/99-tinypro.rules
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="a466", ATTR{idProduct}=="0a53", MODE="666"' | sudo tee -a /etc/udev/rules.d/99-tinypro.rules
sudo udevadm control --reload-rules
```

On Windows, the TL866II+, T48 and T56 work with the original XGecu driver (WinUSB). The TL866A/CS needs a WinUSB driver, which can be installed with [Zadig](https://zadig.akeo.ie). The libusb backend is installed automatically with the package (libusb-package).

The T56 needs an FPGA bitstream (algorithm) for each chip family. Like minipro, tinyPro reads these from the file algorithm.xml, which is not included. Specify its path with `-a` or put it into the current directory or into ~/.local/share/minipro/.

## Installation
Ensure that the [prerequisites](https://packaging.python.org/en/latest/tutorials/installing-packages/) for installing Python packages are met. Then execute the following command in the command line:

```
pip install tinypro
```

## Usage
Connect the programmer to your PC and insert the chip into the ZIF socket (or into the required adapter).

```
Usage: tinypro [-h] [-d DEVICE] [-r FILE] [-w FILE] [-v FILE] [-b] [-e] [-m {code,data}] [-P] [-y] [-a FILE] [-l [PATTERN]]

Optional arguments:
  -h, --help                show help message and exit
  -d, --device DEVICE       chip name, e.g. AT28C256 (default: auto-detect SPI flash)
  -r, --read FILE           read memory and save to BIN file
  -w, --write FILE          write BIN file to memory and verify (erases chip first)
  -v, --verify FILE         verify memory against BIN file
  -b, --blank               perform a blank check
  -e, --erase               erase chip
  -m, --memory {code,data}  memory section (default: code)
  -P, --protect             write-protect chip after writing (if supported)
  -y, --ignoreid            continue on chip ID mismatch (at your own risk)
  -a, --algorithm FILE      path to algorithm.xml (T56 only)
  -l, --list [PATTERN]      list supported chips (optionally matching PATTERN)
The actions are executed in the order: read, erase, write, verify, blank check.
Without action arguments the tool shows programmer and chip.

Examples:
tinypro -r backup.bin                  (read SPI flash, auto-detect)
tinypro -d AT28C256 -w image.bin       (write parallel EEPROM)
tinypro -d 27C512 -v image.bin         (verify EPROM)
tinypro -l 25Q32                       (search chip names)
```

Notes:
- Chip names can be given with or without package (e.g. `27C512` or `27C512@PLCC32`); without package the DIP version is preferred.
- A BIN file smaller than the memory is written to the start of the memory, the rest of the memory is left blank (after erasing).
- Flash memories are erased before writing; write protection is removed automatically if the chip requires it. UV-EPROMs must be blank before writing.
- SPI flash is auto-detected in the 8-pin and 16-pin socket positions. For other chips use `-d`.

## License
GNU General Public License v3.0 or later (derived from minipro).

## Links
- [MCU Flash Tools](https://github.com/wagiminator/MCU-Flash-Tools)
- [minipro](https://gitlab.com/DavidGriffith/minipro)
- [XGecu](http://www.xgecu.com/en/)
- [MCU Templates](https://github.com/wagiminator/MCU-Templates)
- [MCU Development Boards](https://github.com/wagiminator/Development-Boards)
