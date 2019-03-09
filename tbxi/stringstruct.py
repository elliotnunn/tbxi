import struct

def tuple_str2bytes(tpl):
    return tuple(x.encode('ascii') if isinstance(x, str) else x for x in tpl)

def tuple_bytes2str(tpl):
    return tuple(x.rstrip(b'\0').decode('ascii') if isinstance(x, bytes) else x for x in tpl)

class StringStruct(struct.Struct):
    """A Struct that works with str instead of bytes"""

    def unpack(self, *args, **kwargs):
        orig = super().unpack(*args, **kwargs)
        return orig.__class__(tuple_bytes2str(orig))

    def unpack_from(self, *args, **kwargs):
        orig = super().unpack_from(*args, **kwargs)
        return orig.__class__(tuple_bytes2str(orig))

    def pack(self, *args, **kwargs):
        return super().pack(*tuple_str2bytes(args), **kwargs)

    def pack_into(self, buf, offset, *args, **kwargs):
        return super().pack_into(buf, offset, *tuple_str2bytes(args), **kwargs)
