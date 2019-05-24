from tbxi.slow_lzss import decompress
from tbxi.fast_lzss import compress
import random

def test_random():
    the_len = 0
    while the_len < 4 * 1024 * 1024:
        the_len <<= 1
        the_len |= random.choice((1, 0))

        tryout = bytes(random.choice(range(256)) for x in range(the_len))

        assert decompress(compress(tryout)) == tryout
