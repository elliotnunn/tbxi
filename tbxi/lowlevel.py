from .stringstruct import StringStruct
from .namedtuplestruct import NamedTupleStruct

class MyParcelStruct(NamedTupleStruct, StringStruct):
    pass

MAGIC = b'prcl\x01\x00\x00\x00'

PrclNodeStruct = MyParcelStruct('>I 4s I I I I 32s 32s', name='PrclNodeStruct',
    fields=['link', 'ostype', 'hdr_size', 'flags', 'n_children', 'child_size', 'a', 'b'])

PrclChildStruct = MyParcelStruct('>4s I 4s I I I I 32s', name='PrclChildStruct',
    fields=['ostype', 'flags', 'compress', 'unpackedlen', 'cksum', 'packedlen', 'ptr', 'name'])
