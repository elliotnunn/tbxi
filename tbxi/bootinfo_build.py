from os import path
import re
import zlib
import sys
import macresources

try:
    from .fast_lzss import compress
except ImportError:
    from .slow_lzss import compress

from . import dispatcher
from . import cfrg_rsrc


def append_checksum(binary):
    cksum = ('\r\\ h# %08X' % zlib.adler32(binary)).encode('ascii')
    binary.extend(cksum)


# Fix a subtle incompatibility between pre/post-v7.8 scripts & trampolines
# (this is ugly)
def edit_bootscript_for_elf(script, tramp):
    oldprop = b'AAPL,toolbox-image,lzss'
    newprop = b'AAPL,toolbox-parcels'

    matrix = (oldprop in script, newprop in script, oldprop in tramp, newprop in tramp)

    if matrix == (True, False, False, True):
        print('Bootscript older than MacOS.elf (fixing %s => %s)' % (oldprop.decode('ascii'), newprop.decode('ascii')), file=sys.stderr)
        script = script.replace(oldprop, newprop)
    elif matrix == (False, True, True, False):
        print('Bootscript newer than MacOS.elf (fixing %s => %s)' % (newprop.decode('ascii'), oldprop.decode('ascii')), file=sys.stderr)
        script = script.replace(newprop, oldprop)
    else:
        return script

    return script


def build(src):
    try:
        with open(path.join(src, 'Bootscript'), 'rb') as f:
            booter = bytearray(f.read().replace(b'\n', b'\r'))
    except (NotADirectoryError, FileNotFoundError):
        raise dispatcher.WrongFormat

    elf = dispatcher.build(path.join(src, 'MacOS.elf'))
    booter[:] = edit_bootscript_for_elf(booter, elf)

    has_checksum = (b'adler32' in booter)

    constants = dict()
    constant_spans = dict()
    for m in re.finditer(rb'h#\s+([A-Fa-f0-9]+)\s+constant\s+([-\w]+)', booter):
        key = m.group(2).decode('ascii')
        val = int(m.group(1), 16)
        constants[key] = val
        constant_spans[key] = m.span(1)

    booter.append(4) # EOT

    for f in ['elf-offset', 'elf-size']:
        assert f in constants

    if 'elf-offset' in constants:
        # special case: pad according to residual info in script
        booter.extend(b'\0' * (constants['elf-offset'] - len(booter)))

        constants['elf-offset'] = len(booter)
        booter.extend(elf)
        constants['elf-size'] = len(booter) - constants['elf-offset']

    if 'lzss-offset' in constants:
        base = 'lzss'
    else:
        base = 'parcels'

    if base + '-offset' in constants:
        constants[base + '-offset'] = len(booter)
        for attempt in ['MacROM', 'Parcels']:
            try:
                data = dispatcher.build(path.join(src, attempt))
            except:
                pass
            else:
                break
        else:
            raise FileNotFoundError

        if not data.startswith(b'prcl'): data = compress(data)
        booter.extend(data)

        constants[base + '-size'] = len(booter) - constants[base + '-offset']

    constants['info-size'] = len(booter)

    for key, (start, stop) in reversed(sorted(constant_spans.items())):
        insert = ('%X' % constants[key]).zfill(stop - start).encode('ascii')
        assert start + len(insert) == stop
        booter[start:stop] = insert

    if has_checksum: append_checksum(booter)

    # Add a System Enabler (or even just 'vers' information)
    rsrcfork = []
    try:
        datafork = open(path.join(src, 'SysEnabler'), 'rb').read()
        rsrcfork = list(macresources.parse_rez_code(open(path.join(src, 'SysEnabler.rdump'), 'rb').read()))

        while len(booter) % 16: booter.append(0)
        delta = len(booter)
        booter.extend(datafork)
        if len(datafork) > 0 and has_checksum: append_checksum(booter)

        for r in rsrcfork:
            if r.type == b'cfrg':
                r.data = cfrg_rsrc.adjust_dfrkoffset_fields(r.data, delta)

    except FileNotFoundError:
        pass

    return bytes(booter), rsrcfork
