from os import path
import os
import shlex

from .lowlevel import SuperMarioHeader, ResHeader, ResEntry, FakeMMHeader, COMBO_FIELDS

from . import dispatcher


PAD = b'kc' * 100

HEADER_COMMENT = """
# Automated dump of Macintosh ROM resources

# The (optional) combo mask switches a resource based on the DefaultRSRCs
# field of the box's ProductInfo structure. (The low-memory variable at
# 0xDD8 points to ProductInfo, and the DefaultRSRCs byte is at offset
# 0x16.) The combo field is usually used for the Standard Apple Numeric
# Environment (SANE) PACKs 4 and 5.

# Summary of known combos:
# 0b01111000    AllCombos (DEFAULT)         Universal resource          
# 0b01000000    AppleTalk1                  Appletalk 1.0               
# 0b00100000    AppleTalk2                  Appletalk 2.0               
# 0b00110000    AppleTalk2_NetBoot_FPU      Has FPU and remote booting  
# 0b00001000    AppleTalk2_NetBoot_NoFPU    Has remote booting, no FPU  
# 0b00010000    NetBoot                     Has remote booting          

""".strip()

def clean_maincode(binary):
    binary = bytearray(binary)

    header = SuperMarioHeader.unpack_from(binary)
    modified_header = header._asdict()

    for k in list(modified_header):
        if k.startswith('CheckSum'):
            modified_header[k] = 0
    modified_header['RomRsrc'] = 0
    modified_header['RomSize'] = 1

    SuperMarioHeader.pack_into(binary, 0, **modified_header)

    return bytes(binary)


def is_supermario(binary):
    return (len(binary) in (0x200000, 0x300000)) and (PAD in binary)


def extract_decldata(binary):
    return binary[binary.rfind(PAD) + len(PAD):]


# Get a list of (entry_offset, data_offset, data_len)
def extract_resource_offsets(binary):
    # chase the linked list around
    offsets = []

    reshead = SuperMarioHeader.unpack_from(binary).RomRsrc
    link = ResHeader.unpack_from(binary, reshead).offsetToFirst
    while link:
        data = ResEntry.unpack_from(binary, link).offsetToData
        datasize = FakeMMHeader.unpack_from(binary, data - 16).dataSizePlus12 - 12
        offsets.append((link, data, datasize))
        link = ResEntry.unpack_from(binary, link).offsetToNext

    offsets.reverse()
    return offsets


def sanitize_macroman(binary):
    string = binary.decode('mac_roman')
    string = ''.join(c if c.isalpha() or c.isdigit() else '_' for c in string)
    return string


def express_macroman(binary):
    return repr(binary)[1:]
    accum = ''
    for b in binary:
        if b == ord(' '):
            accum += '\\ '
        elif b < 128 and chr(b).isprintable() and not chr(b).isspace():
            accum += chr(b)
        else:
            accum += '\\x%02X' % b
    return accum


def quodec(binary):
    return shlex.quote(binary.decode('mac_roman'))


def ljustspc(s, n):
    return (s + ' ').ljust(n)


def dump(binary, dest_dir):
    if not is_supermario(binary): raise dispatcher.WrongFormat

    os.makedirs(dest_dir, exist_ok=True)

    with open(path.join(dest_dir, 'Romfile'), 'w') as f:
        print(HEADER_COMMENT +  '\n', file=f)
        print('rom_size=%s\n' % hex(len(binary)), file=f)

        header = SuperMarioHeader.unpack_from(binary)

        main_code = clean_maincode(binary[:header.RomRsrc])
        dispatcher.dump(main_code, path.join(dest_dir, 'MainCode'))

        decldata = extract_decldata(binary)
        if decldata:
            dispatcher.dump(decldata, path.join(dest_dir, 'DeclData'))

        # now for the tricky bit: resources :(
        unavail_filenames = set(['', '.pef', '.pict'])
        types_where_Main_should_be_in_filename = set()

        known_forced_offsets = []

        for i, (hoffset, doffset, dlen) in enumerate(extract_resource_offsets(binary)):
            rsrc_dir = path.join(dest_dir, 'Rsrc')
            os.makedirs(rsrc_dir, exist_ok=True)

            data = binary[doffset:doffset+dlen]
            entry = ResEntry.unpack_from(binary, hoffset)

            offset_forced = False
            if hoffset < doffset: # Either offset was forced, or previous forced offset caused fit problems
                # Tricky guessing: check whether the data would have fit where the entry struct went
                for known in known_forced_offsets:
                    if hoffset <= known < hoffset + 16 + dlen:
                        break
                else:
                    offset_forced = True

            if offset_forced:
                known_forced_offsets.append(doffset - 16)

            # mmhead = FakeMMHeader.unpack_from(binary, doffset - 16)
            # assert mmhead.MagicKurt == b'Kurt'
            # assert mmhead.MagicC0A00000 == 0xC0A00000
            
            report_combo_field = COMBO_FIELDS.get(entry.combo, '0b' + bin(entry.combo >> 56)[2:].zfill(8))

            if entry.rsrcName == b'%A5Init':
                types_where_Main_should_be_in_filename.add(entry.rsrcType)

            # create a friendly ascii filename for the resource
            filename = '%s_%d' % (sanitize_macroman(entry.rsrcType), entry.rsrcID)
            if entry.rsrcName != b'Main' or entry.rsrcType in types_where_Main_should_be_in_filename:
                filename += '_' + sanitize_macroman(entry.rsrcName)
            if report_combo_field != 'AllCombos':
                filename += '_' + report_combo_field.replace('AppleTalk', 'AT')
            filename = filename.strip('_')
            while '__' in filename: filename = filename.replace('__', '_')
            if data.startswith(b'Joy!peff'): filename += '.pef'
            if entry.rsrcType == b'PICT': filename += '.pict'
            while filename in unavail_filenames: filename = '_' + filename

            unavail_filenames.add(filename)

            with open(path.join(rsrc_dir, filename), 'wb') as f2:
                f2.write(data)

            filename = path.join('Rsrc', filename)

            # Now, just need to dream up a data format
            report = ''
            report = ljustspc(report + 'type=' + quodec(entry.rsrcType), 12)
            report = ljustspc(report + 'id=' + str(entry.rsrcID), 24)
            report = ljustspc(report + 'name=' + quodec(entry.rsrcName), 48)
            report = ljustspc(report + 'src=' + shlex.quote(filename), 84)
            if report_combo_field != 'AllCombos':
                report = ljustspc(report + 'combo=' + report_combo_field, 0)
            if offset_forced:
                report = ljustspc(report + 'offset=0x%X' % (doffset - 16), 0)
            report = report.rstrip()

            print(report, file=f)
