from __future__ import print_function
import sqlite3
import os
import json
from collections import defaultdict

from .common import Identity
from . import bismuth


def double_N(value, times):
    for N in range(0, times):
        value *= 2
    return value


def load_block(blockno_or_hash):
    filename = 'data/done/%s.block' % (str(blockno_or_hash),)
    if not os.path.exists(filename):
        return None
    with open(filename, 'rb') as handle:
        proofs = []
        for proof in handle:
            proof = json.loads(proof)
            proofs.append(proof)
    return proofs


def proof_histogram(proofs, pool_address):
    # max_height = max([X[2] for X in proofs])
    min_height = min([X[2] for X in proofs])
    share_dist = defaultdict(int)
    work_counts = defaultdict(int)
    total_shares = 0
    named_shares = 0
    for proof in proofs:
        # Calculate payout relative to highest scoring Proof of Work
        gap = abs(proof[2] - min_height)
        share = double_N(1.0, gap)
        total_shares += share
        if proof[1] is None:
            proof[1] = pool_address
        else:
            named_shares += share
        work_counts[proof[1]] += 1
        share_dist[proof[1]] += share
    return total_shares, named_shares, share_dist, work_counts, len(proofs)


myid = Identity('.bismuth.key')


pooldb = sqlite3.connect('data/pool.db')
pooldb.text_factory = str
poolcur = pooldb.cursor()
poolcur.executescript("""
CREATE TABLE IF NOT EXISTS workproof (
    block_id INTEGER NOT NULL,
    address_id INTEGER NOT NULL,
    shares INTEGER NOT NULL,
    workcount INTEGER NOT NULL,
    shmeckles INTEGER DEFAULT 0,
    PRIMARY KEY (block_id, address_id)
);

CREATE TABLE IF NOT EXISTS addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address VARCHAR(56) NOT NULL,
    total_reward DECIMAL DEFAULT 0,
    sent_reward DECIMAL DEFAULT 0,
    paid_upto INTEGER,
    total_work INTEGER,
    UNIQUE (address)
);

CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER NOT NULL PRIMARY KEY,
    stamp INTEGER NOT NULL,
    won INTEGER NOT NULL,
    total_shares INTEGER NOT NULL,
    nonce VARCHAR(32) NOT NULL,
    reward TEXT NOT NULL,
    address TEXT NOT NULL,
    difficulty INTEGER,
    total_work INTEGER,
    named_work INTEGER,
    named_shares INTEGER NOT NULL,
    pool_balance INTEGER NOT NULL,
    pool_shmeckles INTEGER NOT NULL
);
""")


def make_address_ids(poolcur, addresses):
    placeholders = ','.join(['?'] * len(addresses))
    sql = "SELECT address, id FROM addresses WHERE address IN (%s)" % (placeholders,)
    poolcur.execute(sql, addresses)
    found = dict(poolcur.fetchall())
    for address in addresses:
        if address not in found:
            poolcur.execute("INSERT INTO addresses (address) VALUES (?)", (address,))
            found[address] = poolcur.lastrowid
    return found


ledgerdb = sqlite3.connect("../Bismuth/static/ledger.db")  # open to select the last tx to create a new hash from
ledgerdb.text_factory = str
ledgercon = ledgerdb.cursor()
ledgercon.execute("""
    SELECT block_height, reward, openfield, timestamp, address, amount, fee, recipient, block_hash FROM transactions
    WHERE block_height > 90000
""")  # , (myid.public_key_hashed,))
result = ledgercon.fetchall()


pool_balance = 0
pool_shmeckles = 0

prev_block_hash = None

for row in result:
    address = row[4]
    blockno = row[0]
    openfield = row[2]
    reward = float(row[1])
    amount = float(row[5])
    fees = float(row[6])
    recipient = row[7]
    block_hash = row[8]

    debit = 0
    credit = 0
    if recipient == myid.address:
        credit = amount
    else:
        debit = amount

    if recipient == myid.address or address == myid.address:
        pool_balance += credit - debit - fees + reward

    if recipient != address:
        continue

    proofs = load_block(blockno).extend(load_block(prev_block_hash))
    total_shares = 0
    total_work = 0
    named_shares = 0
    share_dist = dict()
    if proofs:
        total_shares, named_shares, share_dist, work_counts, total_work = proof_histogram(proofs, myid.address)
        pool_shmeckles += 1
    named_work = 0
    did_win = myid.address == address

    # Calculate difficulty
    difficulty = None
    if prev_block_hash:
        difficulty = bismuth.difficulty(address, openfield, prev_block_hash)
    prev_block_hash = block_hash

    # balance = bismuth_balance(ledgercon, blockno, myid.address)
    # shmecks = total_shmeckles(poolcur, blockno)

    address_ids = make_address_ids(poolcur, share_dist.keys())
    workproof_rows = list()
    for address, shares in share_dist.items():
        if address == myid.address:
            continue
        address_id = address_ids[address]
        shmeckles = round(shares / named_shares, 6)
        work_count = work_counts[address]
        named_work += work_count
        workproof_rows.append((blockno, address_id, shares, work_count, shmeckles))

    poolcur.executemany("REPLACE INTO workproof VALUES (?, ?, ?, ?, ?)", workproof_rows)

    poolcur.execute("""
    REPLACE INTO blocks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (blockno, row[3], int(did_win), total_shares, row[2], reward, row[4], difficulty,
          total_work, named_work, named_shares, pool_balance, pool_shmeckles))

    # Openfield cost:
    # float(len(db_openfield)) / 100000

pooldb.commit()
