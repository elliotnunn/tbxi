import shlex
import ast
import struct
from os import path

from . import lowlevel
from . import dispatcher


ALIGN = 16
REV_COMBO_FIELDS = {v: k for (k, v) in lowlevel.COMBO_FIELDS.items()}


def checksum(binary):
    binary[:4] = bytes(4)
    binary[0x30:0x40] = bytes(16)

    lanes = [sum(binary[i::4]) & 0xFFFFFFFF for i in range(4)]
    struct.pack_into('>LLLL', binary, 0x30, *lanes)

    oneword = (sum(binary[::2])*256 + sum(binary[1::2])) & 0xFFFFFFFF
    struct.pack_into('>L', binary, 0, oneword)


def build(src):
    if not path.exists(path.join(src, 'Romfile')): raise dispatcher.WrongFormat

    romfile = dispatcher.build(path.join(src, 'Romfile')).decode('utf8').split('\n')

    rsrc_list = []
    for l in romfile:
        words = shlex.split(l, comments=True, posix=True)

        thisdict = {}
        for word in words:
            a, sep, b = word.partition('=')
            if sep == '=':
                if a == 'type':
                    b = b.encode('mac_roman')
                elif a in ('id', 'rom_size', 'offset'):
                    b = ast.literal_eval(b)

                thisdict[a] = b

        if 'rom_size' in thisdict:
            rom_size = thisdict['rom_size']
        elif 'type' in thisdict:
            rsrc_list.append(thisdict)

    rom = bytearray(b'kc' * (rom_size // 2))
    free_map = bytearray(b'X' * (rom_size // ALIGN))

    def rom_insert(offset, binary, letter=' '):
        letter = letter.encode('ascii')

        if offset + len(binary) > len(rom):
            raise IndexError('ROM too small to insert %r at %s' % (letter, hex(offset)))
        rom[offset:offset+len(binary)] = binary

        # Populate the informational array of letters
        # Only capitals can be overwritten
        start = offset // ALIGN
        stop = (offset + len(binary) - 1) // ALIGN + 1

        for i in range(start, stop):
            if free_map[i] != 20:
                if free_map[i:i+1].upper() != free_map[i:i+1]:
                    raise ValueError('Tried to insert %r over %r at %s' % (letter, free_map[i], hex(offset)))

            free_map[i:i+1] = letter

    def find_free(length):
        length = (length + ALIGN - 1) // ALIGN
        return free_map.index(b'X' * length) * ALIGN

    maincode = dispatcher.build(path.join(src, 'MainCode'))
    rom_insert(0, maincode, 'm')

    head_ptr = find_free(16)
    rom_insert(head_ptr, b'fake header', 'H')

    try:
        decldata = dispatcher.build(path.join(src, 'DeclData'))
    except FileNotFoundError:
        pass
    else:
        rom_insert(len(rom) - len(decldata), decldata, 'd')

    # now blat in the resources
    ent_ptr = 0
    bogus_off = 0x5C

    for r in rsrc_list:
        data = dispatcher.build(path.join(src, r['src']))

        # First place the data, including the fake MemMgr header
        if 'offset' in r:
            ofs = r['offset']
        else:
            ofs = find_free(16 + len(data))

        mm_ptr = ofs + 4
        data_ptr = ofs + 16

        # And insert that
        mm = lowlevel.FakeMMHeader.pack(
            MagicKurt=b'Kurt',
            MagicC0A00000=0xC0A00000,
            dataSizePlus12=len(data) + 12,
            bogusOff=bogus_off,
        )
        rom_insert(mm_ptr - 4, mm + data, 'r')

        # Calculate the independently-placed entry struct
        combo = r.get('combo', 'AllCombos')
        combo = REV_COMBO_FIELDS.get(combo, None)
        if combo is None:
            combo = ast.literal_eval(combo) << 56

        ent = lowlevel.ResEntry.pack(
            combo=combo,
            offsetToNext=ent_ptr, # this is the previous one
            offsetToData=data_ptr,
            rsrcType=r['type'],
            rsrcID=r['id'],
            rsrcAttr=0x58,
            rsrcName=r['name'].encode('mac_roman'),
        )
        # snip off pascal string padding
        ent = ent[:0x18 + ent[0x17]]

        # Place the entry struct
        ent_ptr = find_free(len(ent))
        rom_insert(ent_ptr, ent, 'e')

        bogus_off += 8

    head = lowlevel.ResHeader.pack(
        offsetToFirst=ent_ptr,
        maxValidIndex=4,
        comboFieldSize=8,
        comboVersion=1,
        headerSize=12,
    )
    rom_insert(head_ptr, head, 'h')

    # now set the size
    fields = lowlevel.SuperMarioHeader.unpack_from(rom)._asdict()
    fields['RomRsrc'] = head_ptr
    fields['RomSize'] = len(rom)
    lowlevel.SuperMarioHeader.pack_into(rom, 0, **fields)

    # now set the checksums!
    checksum(rom)

    return bytes(rom)
