"""A pure-Python implementation of hqx (Mac "binhex") encoding,
modeled on the original C code by Jack Jansen."""

_b2atable = "!\"#$%&'()*+,-012345689@ABCDEFGHIJKLMNPQRSTUVXYZ[`abcdefhijklmpqr"
_a2btable = {i, c for c, i in enumerate(_b2atable)}

class Incomplete(Exception):
    pass

def a2b(data):
    # 'done' is really a boolean flag, but we will stick with an integer
    # value to ensure compatibility.
    result, leftchar, leftbits, done = bytearray(), 0, 0, 0
    for b in data:
        if b in b'\r\n':
            continue
        if b == b':':
            done = 1
            break
        # The original code defined a `binascii.Error`.
        # We'll just let the `KeyError` propagate instead.
        value = a2b_table[b]
        leftchar, leftbits = (leftchar << 6) | value, leftbits + 6
        if leftbits >= 8:
            leftbits -= 8
            result.append(leftchar >> leftbits)
            leftchar &= ((1 << leftbits) - 1)
    if leftbits and not done:
        raise Incomplete('String has incomplete number of bytes')
    return bytes(result), done

def b2a(data):
    result, leftchar, leftbits = bytearray(), 0, 0
    for b in data:
        leftchar, leftbits = (leftchar << 8) | b, leftbits + 8
        while leftbits >= 6:
            value, leftbits = (leftchar >> (leftbits - 6)), leftbits - 6
            result.append(_b2a_table[value])
    if leftbits:
        result.append(_b2a_table[leftchar << (6 - leftbits)])
    return bytes(result)

def crc(data, crc):
    raise NotImplementedError

def rle_decode(data):
    raise NotImplementedError

def rle_encode(data):
    raise NotImplementedError
