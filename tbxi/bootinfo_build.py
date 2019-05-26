from os import path
import re
import zlib

try:
    from .fast_lzss import compress
except ImportError:
    from .slow_lzss import compress

from . import dispatcher


def append_checksum(binary):
    cksum = ('\r\\ h# %08X' % zlib.adler32(binary)).encode('ascii')
    binary.extend(cksum)


def build(src):
    try:
        with open(path.join(src, 'Bootscript'), 'rb') as f:
            booter = bytearray(f.read().replace(b'\n', b'\r'))
    except (NotADirectoryError, FileNotFoundError):
        raise dispatcher.WrongFormat

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
        booter.extend(dispatcher.build(path.join(src, 'MacOS.elf')))
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

    return bytes(booter)
