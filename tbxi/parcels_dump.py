from collections import defaultdict, Counter
import os
from os import path
from shlex import quote
import struct
import hashlib

from . import dispatcher

from .slow_lzss import decompress
from .lowlevel import PrclNodeStruct, PrclChildStruct
from .pef_info import suggest_name


HEADER_COMMENT = """
# Automated dump of Toolbox Parcels (magic number 'prcl')

#parcel_type [metadata...]
\t#child_type [metadata...] [src=*[.lzss]]
\t\t#null_terminated_strings_instead_of_src_file

# Parcel types are four bytes (child types are unimportant)
#   'prop': match and edit an existing DT node
#   'node': create a new DT node
#   'rom ': Power Macintosh ROM image
#   'psum': black/whitelists for computing DT checksum

#  Flag    Struct   Meaning of known flag
#  -----   ------   --------------------------------------------
#  F0000   parcel   (bitmask) number of new 'special' DT node
#  00200   parcel   edit DT node only if required for boot disk
#  00010   parcel   use only once
#  00008   parcel   match DT node if: ('device_type' == b field)
#  00004   parcel      AND  ('compatible' contains a field
#  00002   parcel           OR   parent 'name' == a field
#  00001   parcel           OR   'name' == a field)
#  -----   ------   --------------------------------------------
#  F0000   child    (bitmask) number of 'special' parent
#  00080   child    create DT prop under 'special' DT node above
#  00100   child    DT prop is for boot debugging only
#  00040   child    delete existing DT prop (vs create)
#  00020   child    do not replace existing DT prop
#  00010   child    use only once
#  00004   child    checksum enabled (crc32)

""".strip()


def quickhash(foo):
    return hashlib.sha512(foo).hexdigest()


def walk_tree(binary):
    """Get low level representation of tree

    e.g. [(prclnodetuple, [prclchildtuple, ...]), ...]
    """

    prclnode = None

    parents = []
    for i in iter(lambda: prclnode.link if prclnode else struct.unpack_from('>12xI', binary)[0], 0):
        prclnode = PrclNodeStruct.unpack_from(binary, offset=i)
        
        children = []
        for j in range(i + PrclNodeStruct.size, i + prclnode.hdr_size, prclnode.child_size):
            prclchild = PrclChildStruct.unpack_from(binary, offset=j)

            children.append(prclchild)

        parents.append((prclnode, children))

    return parents


def unique_binary_tpl(prclchild):
    return (prclchild.ptr, prclchild.packedlen, prclchild.compress)


def guess_binary_name(parent_struct, child_struct, adjacent_name, data):
    # 4 MB ROM-in-RAM image
    if parent_struct.ostype == child_struct.ostype == 'rom ':
        return 'MacROM'

    # Native (PCI) driver with an embedded name and version
    ndrv_name = suggest_name(data)
    if ndrv_name: return ndrv_name

    # A "special" property called by its actual name
    if parent_struct.flags & 0xF0000 or child_struct.flags & 0x80:
        return child_struct.name

    # A driver property with an adjacent name property
    if 'AAPL,MacOS,PowerPC' in child_struct.name and adjacent_name:
        return adjacent_name

    # A lanLib (for netbooting)
    if child_struct.name == 'lanLib,AAPL,MacOS,PowerPC':
        return parent_struct.a + '_lanLib'

    return ''


def dump(binary, dest_dir):
    if not binary.startswith(b'prcl'): raise dispatcher.WrongFormat

    os.makedirs(dest_dir, exist_ok=True)

    basic_structure = walk_tree(binary)

    # Decompress everything
    unpacked_dict = {}
    binary_of = lambda child: unpacked_dict[unique_binary_tpl(child)]
    binary_counts = Counter()
    for prclnode, children in basic_structure:
        for prclchild in children:
            binary_counts[unique_binary_tpl(prclchild)] += 1

            data = binary[prclchild.ptr:prclchild.ptr+prclchild.packedlen]
            if prclchild.compress == 'lzss': data = decompress(data)

            unpacked_dict[unique_binary_tpl(prclchild)] = data

    filename_dict = {} # maps binary data to a filename
    for prclnode, children in basic_structure:
        # A fragment prop may have an adjacent prop giving it a name, get this ready
        adjacent_name = None
        for check_child in children:
            if check_child.name == 'code,AAPL,MacOS,name':
                adjacent_name = unpacked_dict[unique_binary_tpl(check_child)].rstrip(b'\0').decode('ascii')

        # Best guess original-ish name for this binary
        for prclchild in children:
            if prclchild.ostype not in ('cstr', 'csta'):
                base = guess_binary_name(
                    parent_struct=prclnode,
                    child_struct=prclchild,
                    adjacent_name=adjacent_name,
                    data=binary_of(prclchild),
                )
                filename_dict[binary_of(prclchild)] = base

    # Post-process to ensure that all names are unique
    used_names = Counter(filename_dict.values())
    for binary, filename in list(filename_dict.items()):
        if used_names[filename] > 1:
            if filename: filename += '-'
            filename += quickhash(binary)
            filename_dict[binary] = filename 

    filename_dict = {b: (fn+'.pef' if b.startswith(b'Joy!peff') else fn) for (b, fn) in filename_dict.items()}

    # Dump blobs to disk
    for data, filename in filename_dict.items():
        dispatcher.dump(data, path.join(dest_dir, filename))

    # Get printing!!!
    with open(path.join(dest_dir, 'Parcelfile'), 'w') as f:
        f.write(HEADER_COMMENT + '\n\n')

        for prclnode, children in basic_structure:
            line = quote(prclnode.ostype)
            line += ' flags=0x%05x' % prclnode.flags
            if prclnode.a: line += ' a=%s' % quote(prclnode.a)
            if prclnode.b: line += ' b=%s' % quote(prclnode.b)

            print(line, file=f)

            for prclchild in children:
                line = '\t%s' % quote(prclchild.ostype)
                line += ' flags=0x%05x' % prclchild.flags
                if prclchild.name: line += ' name=%s' % quote(prclchild.name)

                if prclchild.ostype not in ('cstr', 'csta'):
                    filename = filename_dict[binary_of(prclchild)]
                    if prclchild.compress == 'lzss': filename += '.lzss'
                    line += ' src=%s' % quote(filename)

                if binary_counts[unique_binary_tpl(prclchild)] > 1:
                    line += ' deduplicate=1'

                if prclnode.ostype == 'psum' and prclchild.ostype == 'csta':
                    if prclchild is children[0]: line += "  # [5] Property whitelist:"
                    if prclchild is children[1]: line += "  # [4] Node 'name' whitelist:"
                    if prclchild is children[2]: line += "  # [3] Node 'name' blacklist:"
                    if prclchild is children[3]: line += "  # [2] Node 'device-type' whitelist:"
                    if prclchild is children[4]: line += "  # [1] Node 'device-type' blacklist:"

                print(line, file=f)

                if prclchild.ostype in ('cstr', 'csta'):
                    strangs = unpacked_dict[unique_binary_tpl(prclchild)].split(b'\0')[:-1]
                    for s in strangs:
                        line = '\t\t%s' % quote(s.decode('ascii'))

                        print(line, file=f)

            print(file=f)
