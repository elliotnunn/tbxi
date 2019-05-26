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
                elif a in ('id', 'rom_size'):
                    b = ast.literal_eval(b)

                thisdict[a] = b

        if 'rom_size' in thisdict:
            rom_size = thisdict['rom_size']
        elif 'type' in thisdict:
            rsrc_list.append(thisdict)

    rom = bytearray(b'kc' * (rom_size // 2))

    maincode = dispatcher.build(path.join(src, 'MainCode'))
    rom[:len(maincode)] = maincode

    try:
        decldata = dispatcher.build(path.join(src, 'DeclData'))
    except FileNotFoundError:
        pass
    else:
        if decldata: rom[-len(decldata):] = decldata

    # now blat in the resources
    free = len(maincode) + 16
    prev_ent_ptr = 0
    bogus_off = 0x5C

    for r in rsrc_list:
        data = dispatcher.build(path.join(src, r['src']))

        data_ptr = lowlevel.pad(free + 16, ALIGN)
        mm_ptr = data_ptr - 12
        ent_ptr = lowlevel.pad(data_ptr + len(data), ALIGN)

        mm = lowlevel.FakeMMHeader.pack(
            MagicKurt=b'Kurt',
            MagicC0A00000=0xC0A00000,
            dataSizePlus12=len(data) + 12,
            bogusOff=bogus_off,
        )
        rom[mm_ptr-4:mm_ptr-4+len(mm)] = mm

        rom[data_ptr:data_ptr+len(data)] = data

        combo = r.get('combo', 'AllCombos')
        combo = REV_COMBO_FIELDS.get(combo, None)
        if combo is None:
            combo = ast.literal_eval(combo) << 56

        ent = lowlevel.ResEntry.pack(
            combo=combo,
            offsetToNext=prev_ent_ptr,
            offsetToData=data_ptr,
            rsrcType=r['type'],
            rsrcID=r['id'],
            rsrcAttr=0x58,
            rsrcName=r['name'].encode('mac_roman'),
        )
        # snip off pascal string padding
        ent = ent[:0x18 + ent[0x17]]

        rom[ent_ptr:ent_ptr+len(ent)] = ent

        free = ent_ptr + len(ent)
        prev_ent_ptr = ent_ptr
        bogus_off += 8

    head = lowlevel.ResHeader.pack(
        offsetToFirst=prev_ent_ptr,
        maxValidIndex=4,
        comboFieldSize=8,
        comboVersion=1,
        headerSize=12,
    )
    rom[len(maincode):len(maincode)+len(head)] = head

    # now set the size
    fields = lowlevel.SuperMarioHeader.unpack_from(rom)._asdict()
    fields['RomRsrc'] = len(maincode)
    fields['RomSize'] = len(rom)
    lowlevel.SuperMarioHeader.pack_into(rom, 0, **fields)

    # now set the checksums!
    checksum(rom)

    return bytes(rom)
