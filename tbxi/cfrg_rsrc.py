# Routines to fiddle with 'cfrg' (Code Fragment) metadata resources

# These are required only because the code fragments
# referenced by a cfrg are usually at specific offsets
# in a data fork, rather than in a resource. When we
# manipulate a data fork, any corresponding cfrg must be
# adjusted accordingly. This un-Mac-like scheme originated
# as a way to allow code fragments to be memory-mapped,
# which is impossible in a frequently-repacked resource fork.


import struct


# Internal: where are the fields that must be edited?
def get_dfrkoffset_field_positions(cfrg):
    # old-style cfrg only, seems to work fine...
    entry_cnt, = struct.unpack_from('>L', cfrg, 28)

    ctr = 32

    for i in range(entry_cnt):
        if len(cfrg) < ctr + 43: break

        if cfrg[ctr + 23] == 1: # kDataForkCFragLocator
            yield ctr + 24

        ctr += 42 + 1 + cfrg[ctr + 42]
        while ctr % 4: ctr += 1


# Tell this resource that you moved the PEFs that it references in the data fork
def adjust_dfrkoffset_fields(cfrg, delta):
    cfrg = bytearray(cfrg)

    for field in get_dfrkoffset_field_positions(cfrg):
        ofs, = struct.unpack_from('>L', cfrg, field)
        ofs += delta
        struct.pack_into('>L', cfrg, field, ofs)

    return bytes(cfrg)


# Get the (start, stop) offset range of PEFs in the data fork
def get_dfrk_range(cfrg_list, dfrk_len):
    left = dfrk_len
    right = 0

    for cfrg in cfrg_list:
        for field in get_dfrkoffset_field_positions(cfrg):
            my_left, = struct.unpack_from('>L', cfrg, field)
            left = min(my_left, left)

            my_right, = struct.unpack_from('>L', cfrg, field + 4)
            if my_right == 0:
                right = dfrk_len
            else:
                right = max(right, my_left + my_right)

    return left, right
