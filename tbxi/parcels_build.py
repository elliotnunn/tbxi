from shlex import split
from os import path
import struct
from binascii import crc32

from .lowlevel import PrclNodeStruct, PrclChildStruct, MAGIC

try:
    from .fast_lzss import compress
except ImportError:
    from .slow_lzss import compress

from . import dispatcher


class CodeLine(dict):
    def __getattr__(self, attrname):
        return self[attrname]

    def __setattr__(self, attrname, attrval):
        self[attrname] = attrval


def get_indent_level(from_str):
    if from_str.startswith('\t\t'):
        return 2
    elif from_str.startswith('\t'):
        return 1
    else:
        return 0

def get_keys(from_list, **available):
    ret = CodeLine()

    for k, v in available.items():
        ret[k] = v('')

    for i in from_list:
        k, _, v = i.partition('=')
        fmt = available[k]
        ret[k] = fmt(v)

    return ret

def gethex(from_str):
    if not from_str: return 0
    if from_str.lower().startswith('0x'):
        return int(from_str[2:], base=16)
    else:
        return int(from_str)

def getbool(from_str):
    from_str = from_str.lower()
    if from_str.strip() in ('', 'no', 'n', 'false', 'f', '0'):
        return False
    else:
        return True

class PdslParseError(Exception):
    pass

def build(src):
    if not path.exists(path.join(src, 'Parcelfile')): raise dispatcher.WrongFormat
    node_list = []

    with open(path.join(src, 'Parcelfile')) as f:
        try:
            for line_num, line in enumerate(f, start=1):
                level = get_indent_level(line)
                pieces = split(line, comments=True, posix=True)

                if not pieces: continue

                if level == 0:
                    # parcel node
                    new = get_keys(pieces[1:], flags=gethex, a=str, b=str)
                    new.ostype = pieces[0]
                    new.children = []
                    node_list.append(new)

                elif level == 1:
                    # parcel child
                    new = get_keys(pieces[1:], flags=gethex, name=str, src=str, deduplicate=getbool)
                    new.ostype = pieces[0]
                    new.data = bytearray()
                    new.compress = ''

                    if new.src:
                        if not path.isabs(new.src): # look rel to Parcelfile
                            new.src = path.join(src, new.src)

                        a, b = path.splitext(new.src)
                        if b.lower() == '.lzss':
                            new.src = a
                            new.compress = 'lzss'

                        new.data = dispatcher.build(new.src)
                        new.unpackedlen = len(new.data)
                        if new.compress == 'lzss':
                            new.data = compress(new.data)
                        new.packedlen = len(new.data)

                    node_list[-1].children.append(new)

                elif level == 2:
                    # some C strings to add to the data
                    child = node_list[-1].children[-1]
                    assert not child.src
                    for x in pieces:
                        child.data.extend(x.encode('mac_roman') + b'\0')
                        child.packedlen = child.unpackedlen = len(child.data)

        except:
            raise PdslParseError('Line %d' % line_num)

    # Great! Now that we have this cool data structure, turn it into parcels...
    accum = bytearray()

    accum.extend(MAGIC)
    accum.extend(b'\x00\x00\x00\x14')
    hdr_ptr = len(accum)
    accum.extend(bytes(4))  
    accum.extend(bytes(4))

    dedup_dict = {}
    cksum_history = set() # dedup pointers get a checksum when they shouldn't

    for node in node_list:
        # Link previous member to this one
        struct.pack_into('>I', accum, hdr_ptr, len(accum))

        hdr_ptr = len(accum)
        hdr_size = PrclNodeStruct.size + len(node.children)*PrclChildStruct.size
        accum.extend(b'!' * hdr_size)

        # okay, now start blatting data!
        for child in node.children:
            child.data = bytes(child.data) # no more mutability

            if child.deduplicate and child.data in dedup_dict:
                child.ptr = dedup_dict[child.data]
                continue

            child.ptr = len(accum)

            accum.extend(child.data)

            while len(accum) % 4 != 0:
                accum.append(0x99) # this is the only place we pad

            if child.deduplicate:
                dedup_dict[child.data] = child.ptr

        PrclNodeStruct.pack_into(accum, hdr_ptr,
            link=0, ostype=node.ostype, hdr_size=hdr_size, flags=node.flags,
            n_children=len(node.children), child_size=PrclChildStruct.size,
            a=node.a, b=node.b,
        )

        pack_ptr = hdr_ptr + PrclNodeStruct.size

        for child in node.children:
            if child.flags & 4 or child.ptr in cksum_history:
                data = accum[child.ptr:child.ptr+child.packedlen]
                child.cksum = crc32(data)
                cksum_history.add(child.ptr)
            else:
                child.cksum = 0

            PrclChildStruct.pack_into(accum, pack_ptr, **child)
            pack_ptr += PrclChildStruct.size

    return bytes(accum)
