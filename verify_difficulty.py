#!/usr/bin/env python
from __future__ import print_function
import sqlite3
from pooledbismuth import bismuth

ledgerdb = sqlite3.connect("../Bismuth/static/ledger.db")  # open to select the last tx to create a new hash from
ledgerdb.text_factory = str
ledgercon = ledgerdb.cursor()
ledgercon.execute("""
    SELECT timestamp, block_height, block_hash, address, openfield, fee, reward FROM transactions
    WHERE block_height > 90000 AND address = recipient AND fee = 0
    ORDER BY block_height ASC
""")  # , (myid.public_key_hashed,))
result = ledgercon.fetchall()


def calc_diff(block_history, time_drop, db_timestamp_last):
    halfhour_ago = db_timestamp_last - (60 * 30)
    while len(block_history):
        hist_stamp = float(block_history[0][0])
        if hist_stamp <= halfhour_ago:
            block_history.pop(0)
            continue
        break

    blocks_per_30 = len(block_history)
    diff = blocks_per_30 * 2
    drop_factor = 120  # drop 0,5 diff per minute #hardfork
    if time_drop > db_timestamp_last + 120:  # start dropping after 2 minutes
        diff = diff - (time_drop - db_timestamp_last) / drop_factor  # drop 0,5 diff per minute (1 per 2 minutes)
        # drop diff per minute if over target
    if time_drop > db_timestamp_last + 300 or diff < 37:  # 5 m lim
        diff = 37  # 5 m lim
    return int(diff)


block_history = list()
prev_hash = None
prev_timestamp = None
for row in result:
    timestamp, block_height, block_hash, address, nonce, fee, reward = row
    timestamp = float(timestamp)
    if prev_hash is not None:
        diff = calc_diff(block_history, timestamp, prev_timestamp)
        actual_diff = bismuth.difficulty(address, nonce, prev_hash)
        # if actual_diff < diff:
        print(round(timestamp - prev_timestamp, 2), row, diff, actual_diff, len(block_history))
    prev_hash = block_hash
    block_history.append(row)
    prev_timestamp = timestamp
