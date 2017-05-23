import hashlib
import logging as LOG

try:
    import quickbismuth
    LOG.info('Using QuickBismuth %r', quickbismuth.__version__)
except ImportError:
    LOG.warning('QuickBismuth not found, using slow Python version')
    quickbismuth = None


def _bin_convert(string):
    return ''.join(format(ord(x), 'b') for x in string)


def difficulty(address, nonce, db_block_hash):
    needle = _bin_convert(db_block_hash)
    input = address + nonce + db_block_hash
    haystack = _bin_convert(hashlib.sha224(input).hexdigest())
    return max([N for N in range(1, len(needle) - 1) if needle[:N] in haystack])


def verify(address, nonce, db_block_hash, diff_len):
    if quickbismuth:
        return quickbismuth.bismuth_verify(address, nonce, db_block_hash, diff_len)

    diff_len = int(diff_len)
    mining_search_bin = _bin_convert(db_block_hash)[0:diff_len]
    mining_input = address + nonce + db_block_hash
    mining_hash = hashlib.sha224(mining_input).hexdigest()
    mining_bin = _bin_convert(mining_hash)
    if mining_search_bin in mining_bin:
        return True
