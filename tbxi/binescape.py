from ast import literal_eval

def ascii_from_bytes(s):
    # convert to b'stuff' form, then cut off the first two and last one chars
    return ''.join(repr(bytes([c]))[2:-1] for c in s)

def bytes_from_ascii(s):
    # undo the above
    return b'"'.join(literal_eval('b"' + part + '"') for part in s.split('"')).decode('ascii')
