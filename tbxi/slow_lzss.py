# This file is adapted from LZSS.C by Haruhiko Okumura 4/6/1989

# Decompression is pretty quick
# Compression is pretty slow:
# about 50s to compress a 4 MB rom on my machine

from warnings import warn
have_warned_about_slowness = False

N = 0x1000
F = 18
THRESHOLD = 2
NIL = N


def memset(buf, start, stop, to):
    for i in range(start, stop):
        buf[i] = to


def decompress(lzss):
    lzss = iter(lzss)
    plain = bytearray()

    lzdict = bytearray(b' ' * N)

    dict_i = N - F
    def push(byte):
        nonlocal dict_i
        lzdict[dict_i % N] = byte
        dict_i += 1

        plain.append(byte)

    # Iterate through byte-headed "runs"
    try:
        for headerbyte in lzss:
            for bitnum in range(8):
                if (headerbyte >> bitnum) & 1:
                    # Copy a single byte verbatim
                    push(next(lzss))
                else:
                    # Copy 3-18 bytes from the dictionary
                    byte1 = next(lzss)
                    byte2 = next(lzss)
                    lookup_i = (byte2 << 4) & 0xf00 | byte1
                    lookup_len = (byte2 & 0x0f) + 3

                    for i in range(lookup_i, lookup_i+lookup_len):
                        push(lzdict[i % N])

    except StopIteration:
        # Means the last header had <8 real bits, no problem
        pass

    return bytes(plain)


class Tree:
    def __init__(self):
        self.lchild = [0] * (N + 1)
        self.rchild = [0] * (N + 257); memset(self.rchild, N + 1, N + 256 + 1, NIL)
        self.parent = [0] * (N + 1); memset(self.parent, 0, N, NIL)

    # Inserts string of length F, text_buf[r..r+F-1], into one of the trees
    # (text_buf[r]'th tree) and returns the longest-match position and length
    # via the global variables match_position and match_length.
    # If match_length = F, then removes the old node in favor of the new one,
    # because the old one will be deleted sooner. Note r plays double role,
    # as tree node and position in buffer.
    def insert_node(self, r, text_buf):
        lchild, rchild, parent = self.lchild, self.rchild, self.parent

        cmp = 1
        key = text_buf[r:]
        p = N + 1 + key[0]
        rchild[r] = lchild[r] = NIL

        match_length = 0
        match_position = 0

        while 1:
            if cmp >= 0:
                if rchild[p] != NIL:
                    p = rchild[p]
                else:
                    rchild[p] = r
                    parent[r] = p
                    return match_position, match_length
            else:
                if lchild[p] != NIL:
                    p = lchild[p]
                else:
                    lchild[p] = r
                    parent[r] = p
                    return match_position, match_length

            i = 1
            while i < F:
                cmp = key[i] - text_buf[p + i]
                if cmp != 0: break
                i += 1

            if i > match_length:
                match_position = p
                match_length = i
                if match_length >= F: break # out of while loop

        parent[r] = parent[p]
        lchild[r] = lchild[p]
        rchild[r] = rchild[p]
        parent[lchild[p]] = r
        parent[rchild[p]] = r

        if rchild[parent[p]] == p:
            rchild[parent[p]] = r
        else:
            lchild[parent[p]] = r

        parent[p] = NIL;

        return match_position, match_length

    # deletes node p from tree
    def delete_node(self, p):
        lchild, rchild, parent = self.lchild, self.rchild, self.parent

        if parent[p] == NIL: return

        if rchild[p] == NIL:
            q = lchild[p]
        elif lchild[p] == NIL:
            q = rchild[p]
        else:
            q = lchild[p]
            if rchild[q] != NIL:
                while 1:
                    q = rchild[q]
                    if rchild[q] == NIL: break

                rchild[parent[q]] = lchild[q]
                parent[lchild[q]] = parent[q]
                lchild[q] = lchild[p]
                parent[lchild[p]] = q

            rchild[q] = rchild[p]
            parent[rchild[p]] = q

        parent[q] = parent[p]

        if rchild[parent[p]] == p:
            rchild[parent[p]] = q
        else:
            lchild[parent[p]] = q

        parent[p] = NIL


def compress(plain):
    global have_warned_about_slowness

    if not have_warned_about_slowness:
        have_warned_about_slowness = True
        warn('Using slow pure-Python LZSS compression')

    if not plain: return b''

    # Init the variables that get shared with the two closures below
    tree = Tree()
    text_buf = bytearray(N + F - 1); memset(text_buf, 0, N - F, ord(' '))
    match_length = match_position = 0

    # End of function defs, now onto the main attraction
    plain_len = len(plain)
    plain_i = 0

    # code_buf[1..16] saves eight units of code, and code_buf[0] works
    # as eight flags, "1" representing that the unit is an unencoded
    # letter (1 byte), "" a position-and-length pair (2 bytes).
    # Thus, eight units require at most 16 bytes of code.
    code_buf = bytearray(1)
    code_buf_list = [code_buf]
    mask = 1

    # Clear the buffer with any character that will appear often.
    s = 0;  r = N - F

    # Read F bytes into the last F bytes of the buffer
    tblen = 0
    while tblen < F and plain_i < plain_len:
        text_buf[r + tblen] = plain[plain_i]
        tblen += 1
        plain_i += 1

    # Insert the F strings, each of which begins with one or more
    # 'space' characters.  Note the order in which these strings are
    # inserted.  This way, degenerate trees will be less likely to occur.
    for i in range(1, F+1):
        tree.insert_node(r - i, text_buf)

    # Finally, insert the whole string just read.
    # The global variables match_length and match_position are set.
    match_position, match_length = tree.insert_node(r, text_buf)
    while 1:
        match_length = min(match_length, tblen)

        if match_length <= THRESHOLD:
            # Not long enough match.  Send one byte.
            match_length = 1
            code_buf[0] |= mask # 'send one byte' flag
            code_buf.append(text_buf[r]) # Send uncoded.
        else:
            # Send position and length pair. Note match_length > THRESHOLD.
            byte1 = match_position & 0xFF
            byte2 = (match_position >> 4 & 0xF0) | (match_length - THRESHOLD - 1)
            code_buf.append(byte1)
            code_buf.append(byte2)

        # Shift mask left one bit.
        mask = (mask << 1) & 0xFF
        # Send at most 8 units of code together
        if mask == 0:
            code_buf = bytearray(1)
            code_buf_list.append(code_buf)
            mask = 1

        last_match_length = match_length
        i = 0
        while i < last_match_length and plain_i < plain_len:
            tree.delete_node(s) # Delete old strings and
            c = plain[plain_i]; plain_i += 1
            text_buf[s] = c # read new bytes

            # If the position is near the end of buffer, extend the buffer
            # to make string comparison easier.
            if s < F - 1:
                text_buf[s + N] = c

            # Since this is a ring buffer, increment the position modulo N.
            s = (s + 1) % N
            r = (r + 1) % N

            # Register the string in text_buf[r..r+F-1]
            match_position, match_length = tree.insert_node(r, text_buf)

            i += 1

        while i < last_match_length:
            tree.delete_node(s)

            # After the end of text, no need to read,
            s = (s + 1) % N
            r = (r + 1) % N

            # but buffer may not be empty.
            tblen -= 1
            if tblen:
                match_position, match_length = tree.insert_node(r, text_buf)

            i += 1

        # until length of string to be processed is zero
        if tblen == 0: break

    if len(code_buf_list[-1]) == 1:
        code_buf_list.pop()

    return b''.join(code_buf_list)
