# `tbxi`: the Mac OS Toolbox Imager

`tbxi` is a command-line Python script to help with the inspection and
modification of Macintosh Toolbox ROM images. These images contain
varying amounts of high-level Mac OS code and low-level boot code.

`tbxi` has two modes, both with a `--help` option:

- `tbxi dump` converts a ROM image to a tree of self-describing text
  files and small binaries.
- `tbxi build` rebuilds the image as accurately as possible.

In between running the two commands, the directory tree can be modified.
The text-file formats produced by `tbxi dump` are designed to be easily
editable using text editors and scripts.


## Background

"OldWorld" (pre-USB) Macs contain a real physical ROM. "NewWorld" Macs
(iMac and later) have an unusual "ROM in RAM" arrangement, which retains
compatibility with the ROM-based architecture of the Mac OS while easing
software updates. An almost-complete legacy ROM image is loaded from the
"Mac OS ROM" file in the System Folder (type code 'tbxi'), leaving only
a minimal Open Firmware "Boot ROM" in the hardware.

During the progression from 68k ROMs to NewWorld PowerPC ROMs, multiple
layers of wrapping and abstraction were added. These are reflected in
the multi-level output of `tbxi dump`:

- Open Firmware bootinfo file (`Mac OS ROM` => `Bootinfo` textfile + binaries)
- structured binary of "Parcels" (`Parcels` => `Parcelfile` textfile + binaries)
- 4 MB PowerPC ROM (`MacROM` => `Configfile-1` textfile + binaries)
- 3 MB 68k ROM (`Mac68kROM` => `Romfile` textfile + binaries)


## Bugs

Some very quirky PowerPC OldWorld ROMs (e.g. PowerBook 1400/2400) cannot
be rebuilt correctly. NewWorld ROMs of version 2 or later (Sawtooth G4)
will be slightly different due to an uninitialised buffer in the
original build process.

ROM images predating before the "SuperMario" ROM (Quadra 660AV/840AV)
are not supported, excluding most 68k Mac ROMs.

The resource fork of a NewWorld ROM image is ignored, despite
containting a System Enabler that is paired with the data fork contents.
Simply copying the resource fork back will cause a crash, because the
'cfrg' resource contains offests to some PowerPC binaries at the end of
the data fork.

The `tbxi dump` format is likely to change. If you keep a collection of
dumped ROM images to peruse, re-dump them regularly.

No specific guidance is provided on ROM patches that are known to work,
e.g. to boot Mac OS 9 on the PowerPC Mac mini.


## Contributing

Yes please! Bug reports, suggestions and requests are welcome. Open a
GitHub pull request or image, or get in contact via the email on the
PyPI page.

All are welcome on our retro Mac-hacking mailing list:

https://lists.ucc.gu.uwa.edu.au/mailman/listinfo/cdg5
