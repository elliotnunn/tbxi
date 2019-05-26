from os import path
import shlex
import ast
import re
import struct
import glob

from .lowlevel import ConfigInfo

from . import dispatcher


MAPNAMES = ['sup', 'usr', 'cpu', 'ovl']
BATNAMES = ['ibat0', 'ibat1', 'ibat2', 'ibat3', 'dbat0', 'dbat1', 'dbat2', 'dbat3']


class CodeLine(dict):
    def __getattr__(self, attrname):
        return self[attrname]

    def __setattr__(self, attrname, attrval):
        self[attrname] = attrval


def iter_configinfo_names():
    yield 'Configfile'

    n = 1
    while True:
        yield 'Configfile-%d' % n
        n += 1


def is_safe(expr):
    chexpr = re.sub(r'\b(0x[0-9a-f]+|0b[01]+|\b[1-9][0-9]*|\b0\b)', '', expr.lower())
    for char in chexpr:
        if char not in '+-|&()':
            return False

    return True


def sub_constants(expr):
    K = dict(PMDT_InvalidAddress=0xA00, PMDT_Available=0xA01)

    for k, v in K.items():
        expr = re.sub(r'\b%s\b' % k, '(%s)' % hex(v), expr)

    return expr


def parse_configinfo(src_path):
    linelist = []
    chunks = {'': linelist} # must sort as first

    for line in dispatcher.build(src_path).decode('utf8').split('\n'):
        words = shlex.split(line, comments=True, posix=True)
        if len(words) == 0: continue

        if len(words) == 1 and words[0].startswith('[') and words[0].endswith(']'):
            linelist = []
            chunks[words[0][1:-1]] = linelist
            continue

        worddict = CodeLine()
        linelist.append(worddict)
        for word in words:
            k, sep, v = word.partition('=')
            if sep: worddict[k] = v

    # do some cleanup: replace all instances of BASE with ROMImageBaseOffset
    base = '-0x30C000' # bad fallback, don't skip ROMImageBaseOffset
    lines = chunks['']
    for words in lines:
        for k, v in words.items():
            if k == 'ROMImageBaseOffset':
                base = v

    base = '(%s)' % base

    for header, lines in chunks.items():
        for words in lines:
            for k, v in list(words.items()):
                if k == 'BootstrapVersion':
                    words[k] = v.encode('mac_roman')
                    continue

                if k == 'brpn':
                    v2 = re.sub(r'\bBASE\b', base, v)
                    is_relative = (v != v2)
                    if is_safe(v2):
                        words[k] = is_relative, eval(v2)
                    continue

                v2 = re.sub(r'\bBASE\b', base, v)
                v2 = sub_constants(v2)
                if is_safe(v2):
                    words[k] = eval(v2)

    return chunks


def insert_and_assert(binary, insertee, offset):
    existing = binary[offset:offset+len(insertee)]
    if existing != insertee and any(existing):
        raise ValueError('inserting over something else')

    binary[offset:offset+len(insertee)] = insertee


def checksum_image(binary, ofs):
    # ugly, but iterating the right was is painfully slow

    byte_lanes = [sum(binary[i::8]) for i in range(8)]

    zeroed_byte_lanes = list(byte_lanes)
    for j in range(ofs, ofs+40):
        zeroed_byte_lanes[j % 8] -= binary[j]

    sum32 = [lane % (1<<32) for lane in zeroed_byte_lanes]

    sum64 = sum(lane << (k * 8) for (k, lane) in enumerate(reversed(zeroed_byte_lanes)))
    sum64 %= 1 << 64

    allsums = b''.join(x.to_bytes(4, byteorder='big') for x in sum32)
    allsums += sum64.to_bytes(8, byteorder='big')

    return allsums


def build(src):
    if not path.exists(path.join(src, 'Configfile')) or path.exists(path.join(src, 'Configfile-1')): raise dispatcher.WrongFormat

    print('powerpc', src)

    cilist = []
    for ciname in iter_configinfo_names():
        try:
            cilist.append(parse_configinfo(path.join(src, ciname)))
        except (FileNotFoundError, NotADirectoryError):
            break

    if len(cilist) == 0: raise dispatcher.WrongFormat

    # This will typically contain the emulator, which I can't reliably extract
    try:
        rom = bytearray(dispatcher.build(path.join(src, 'EverythingElse')))
    except FileNotFoundError:
        rom = bytearray(0x400000)

    # Now we go through every configinfo and insert it (oh hell)
    for ci in reversed(cilist):
        fields = {key: 0 for key in ConfigInfo._fields}
        lowmem = bytearray()
        pagemap = bytearray()
        segptrs = [bytearray(128) for _ in MAPNAMES]
        batmap = bytearray() # will be padded to 128
        batptrs = [0 for _ in MAPNAMES]

        for header, lines in ci.items():
            if header == '':
                for words in lines:
                    for k, v in words.items():
                        if k in fields:
                            fields[k] = v

            elif header == 'LowMemory':
                for words in lines:
                    lowmem.extend(struct.pack('>LL', words.address, words.value))

            elif header == 'PageMappingInfo':
                for words in lines:
                    if 'segment_ptr_here' in words:
                        mapidx = MAPNAMES.index(words.map.lower())
                        struct.pack_into('>LL', segptrs[mapidx], 8 * words.segment_ptr_here, len(pagemap), words.segment_register)

                    elif 'special_pmdt' in words:
                        key = 'PageMap%sOffset' % words.special_pmdt.upper()
                        fields[key] = len(pagemap)

                    elif 'pmdt_page_offset' in words:
                        long2 = words.phys_page << 12 | words.attr
                        pagemap.extend(struct.pack('>HHL', words.pmdt_page_offset, words.pages_minus_1, long2))

            elif header == 'BatMappingInfo':
                for words in lines:
                    if 'bat_ptr_here' in words:
                        batidx = BATNAMES.index(words.bat_ptr_here.lower())
                        mapidx = MAPNAMES.index(words.map.lower())
                        fourbits = len(batmap) // 8
                        shift = 4 * (7 - batidx)
                        batptrs[mapidx] |= fourbits << shift

                    elif 'bepi' in words:
                        ubat = lbat = 0

                        ubat |= words.bepi & 0xFFFE0000 # trailing zeroes hopefully
                        ubat |= words.bl_128k << 2
                        ubat |= words.vs << 1
                        ubat |= words.vp

                        lbat |= words.unk23 << 8
                        lbat |= words.wim << 4
                        lbat |= words.ks << 3
                        lbat |= words.ku << 2
                        lbat |= words.pp

                        is_relative, brpn = words.brpn # special case in parse_configinfo
                        if is_relative: lbat |= 0x200
                        lbat = (lbat + brpn) & 0xFFFFFFFF

                        batmap.extend(struct.pack('>LL', ubat, lbat))

        # Get the awkward array data into the struct
        fields['SegMap32SupInit'] = segptrs[0]
        fields['SegMap32UsrInit'] = segptrs[1]
        fields['SegMap32CPUInit'] = segptrs[2]
        fields['SegMap32OvlInit'] = segptrs[3]
        fields['BatMap32SupInit'] = batptrs[0]
        fields['BatMap32UsrInit'] = batptrs[1]
        fields['BatMap32CPUInit'] = batptrs[2]
        fields['BatMap32OvlInit'] = batptrs[3]
        fields['BATRangeInit'] = batmap

        # Great, now we'll neaten up fields and blat it out
        lowmem.extend(b'\0\0\0\0')

        flat = bytearray(0x1000)
        ptr = len(flat)

        ptr -= len(lowmem)
        insert_and_assert(flat, lowmem, ptr)
        fields['MacLowMemInitOffset'] = ptr

        if len(pagemap) > 0:
            ptr -= len(pagemap)
            insert_and_assert(flat, pagemap, ptr)
            fields['PageMapInitOffset'] = ptr
            fields['PageMapInitSize'] = len(pagemap)

        insert_and_assert(flat, ConfigInfo.pack(**fields), 0)

        # Insert the ConfigInfo struct!
        configinfo_offset = -fields['ROMImageBaseOffset'] # this var used below
        insert_and_assert(rom, flat, configinfo_offset)

        # Now insert other things as directed by the struct
        described = [
            ('Mac68KROM', 'Mac68KROM'),
            ('ExceptionTable', 'ExceptionTable'),
            ('HWInitCode', 'HWInit'),
            ('KernelCode', 'NanoKernel'),
            ('OpenFWBundle', 'OpenFW'),
        ]

        for basename, filename in described:
            blob_offset = fields[basename + 'Offset']
            if blob_offset == 0: continue

            matches = glob.glob(glob.escape(path.join(src, filename)) + '*')
            if matches:
                match = min(matches) # try for * before *.src
                blob = dispatcher.build(match)
                insert_and_assert(rom, blob, configinfo_offset + blob_offset)

    # let's do a cheeky checksum!
    cksum = checksum_image(rom, configinfo_offset)
    insert_and_assert(rom, cksum, configinfo_offset) # overwrites start of ConfigInfo

    return bytes(rom)
