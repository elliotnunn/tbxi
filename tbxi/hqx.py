try:
    # Hook for future C extension.
    from .fast_hqx import a2b, b2a, crc, rle_decode, rle_encode, Incomplete
except ImportError:
    from .slow_hqx import a2b, b2a, crc, rle_decode, rle_encode, Incomplete
