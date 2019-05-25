import struct
from collections import namedtuple

class NamedTupleStruct(struct.Struct):
    """A Struct that works with namedtuple instead of tuple"""

    def __init__(self, *args, name=None, fields=None, **kwargs):
        self.__namedtuple = namedtuple(name, fields)
        self._fields = self.__namedtuple._fields
        super().__init__(*args, **kwargs)

    def __tuplify(self, *args, **kwargs):
        kwargs = {k:v for (k,v) in kwargs.items() if k in self.__namedtuple._fields}
        return self.__namedtuple(*args, **kwargs)

    def unpack(self, *args, **kwargs):
        orig = super().unpack(*args, **kwargs)
        return self.__namedtuple(*orig)

    def unpack_from(self, *args, **kwargs):
        orig = super().unpack_from(*args, **kwargs)
        return self.__namedtuple(*orig)

    def pack(self, *args, **kwargs):
        nt = self.__tuplify(*args, **kwargs)
        return super().pack(*nt)

    def pack_into(self, buf, offset, *args, **kwargs):
        nt = self.__tuplify(*args, **kwargs)
        return super().pack_into(buf, offset, *nt)
