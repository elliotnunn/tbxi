import os
from os import path
import re
import sys
import macresources

from .slow_lzss import decompress

from . import dispatcher
from . import cfrg_rsrc


# Special case: expects a (data, resource_list) tuple
def dump(binary, dest_dir):
    if not isinstance(binary, tuple): raise dispatcher.WrongFormat
    binary, rsrc = binary
    if not binary.startswith(b'<CHRP-BOOT>'): raise dispatcher.WrongFormat

    os.makedirs(dest_dir, exist_ok=True)

    a, b, c = binary.partition(b'</CHRP-BOOT>')
    chrp_boot = a + b
    if c.startswith(b'\r'): chrp_boot += b'\r'

    chrp_boot = chrp_boot.replace(b'\r', b'\n')

    # find the build-specific hex, and write out a clean version of the script
    chrp_boot_zeroed = bytearray(chrp_boot)
    constants = dict()
    for m in re.finditer(rb'h#\s+([A-Fa-f0-9]+)\s+constant\s+([-\w]+)', chrp_boot):
        key = m.group(2).decode('ascii')
        val = int(m.group(1), 16)
        constants[key] = val

        if key != 'elf-offset':
            for i in range(*m.span(1)):
                chrp_boot_zeroed[i:i+1] = b'0'

    with open(path.join(dest_dir, 'Bootscript'), 'wb') as f:
        f.write(chrp_boot_zeroed)

    if 'elf-offset' in constants:
        elf = binary[constants['elf-offset']:][:constants['elf-size']]
        dispatcher.dump(elf, path.join(dest_dir, 'MacOS.elf'))

    other_offset = constants.get('lzss-offset', constants.get('parcels-offset'))
    other_size = constants.get('lzss-size', constants.get('parcels-size'))
    parcels = binary[other_offset:][:other_size]

    if parcels.startswith(b'prcl'):
        filename = 'Parcels'
    else:
        filename = 'MacROM'
        parcels = decompress(parcels)

    dispatcher.dump(parcels, path.join(dest_dir, filename))

    # Lastly, dump the System Enabler (if present and rsrc fork not stripped)
    if rsrc:
        cfrgs = [r for r in rsrc if r.type == b'cfrg']

        start, stop = cfrg_rsrc.get_dfrk_range([c.data for c in cfrgs], len(binary))

        for c in cfrgs:
            c.data = cfrg_rsrc.adjust_dfrkoffset_fields(c.data, -start)

        with open(path.join(dest_dir, 'SysEnabler'), 'wb') as f:
            f.write(binary[start:stop])

        with open(path.join(dest_dir, 'SysEnabler.rdump'), 'wb') as f:
            f.write(macresources.make_rez_code(rsrc, ascii_clean=True))

        with open(path.join(dest_dir, 'SysEnabler.idump'), 'wb') as f:
            f.write(b'gblyMACS')

    elif b'Joy!' in binary[other_offset+other_size:]:
        print('Resource fork missing, ignoring orphaned data fork PEFs', file=sys.stderr)
