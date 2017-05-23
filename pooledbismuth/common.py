from __future__ import print_function

import os
import time
import socket
import base64
import hashlib
import logging as LOG
import sqlite3
from collections import namedtuple, defaultdict

from Crypto import Random
from Crypto.Signature import PKCS1_v1_5
from Crypto.PublicKey import RSA


PROTO_VERSION = "mainnnet0009"
MINER_VERSION_ROOT = "morty"

LOWEST_DIFFICULTY = 37

MONITOR_PORT = 5654
POOL_PORT = 5657
STRIKE_TIME = 60
STRIKE_COUNT = 3
CONNECT_TIMEOUT = 5

MINER_TUNE_GOAL = 10
MINER_TUNE_HISTORY = 10


MinerJob = namedtuple('MinerJob', ('diff', 'address', 'block'))
MinerResult = namedtuple('MinerResult', ('diff', 'address', 'block', 'nonce'))

ConsensusBlock = namedtuple('ConsensusBlock', ('height', 'hash', 'stamp'))

IpPort = namedtuple('IpPort', ('ip', 'port'))


def load_consensus(ledger_path):
    ledgerdb = sqlite3.connect(ledger_path)  # open to select the last tx to create a new hash from
    ledgerdb.text_factory = str
    ledgercon = ledgerdb.cursor()
    ledgercon.execute("""
        SELECT * FROM transactions
        WHERE reward > 0
        ORDER BY block_height DESC
        LIMIT 120
    """)  # , (myid.public_key_hashed,))
    results_list = ledgercon.fetchall()

    return reversed([
        ConsensusBlock(int(result[0]), result[7], float(result[1]))
        for result in results_list
    ])


class Abuse(object):
    ip_strikes = defaultdict(int)
    ip_blocked = defaultdict(int)

    @classmethod
    def tick(cls):
        """Maintain abuse mechanisms, preventing build-up of data"""
        now = time.time()
        remove_ips = set()
        for ip, block_until in cls.ip_blocked.items():
            if block_until < now:
                remove_ips.add(ip)
        for ip, strikes in cls.ip_strikes.items():
            if strikes == 0 and ip not in cls.ip_blocked:
                remove_ips.add(ip)
        for ip in remove_ips:
            cls.reset(IpPort(ip, None))

    @classmethod
    def strikes(cls, ip):
        return cls.ip_strikes.get(ip, 0)

    @classmethod
    def strike(cls, peer):
        ip = peer.ip
        if ip == '127.0.0.1':
            return False
        cls.ip_strikes[ip] += 1
        strikes = cls.ip_strikes[ip]
        if strikes >= STRIKE_COUNT:
            cls.ip_blocked[ip] = time.time() + (STRIKE_TIME * STRIKE_COUNT)
            LOG.warning('IP %r - Blocked (%d strikes)', ip, strikes)
            return True
        return False

    @classmethod
    def reset(cls, peer):
        ip = peer.ip
        if ip in cls.ip_blocked:
            del cls.ip_blocked[ip]
        if ip in cls.ip_strikes:
            del cls.ip_strikes[ip]

    @classmethod
    def blocked(cls, peer):
        ip = peer.ip
        strikes = cls.ip_strikes.get(ip, 0)
        blocked_until = cls.ip_blocked.get(ip, None)
        if blocked_until is not None:
            now = time.time()
            if blocked_until < now:
                cls.reset(peer)
                return False
        return strikes >= STRIKE_COUNT


class Identity(object):
    def __init__(self, keyfile=None, keydata=None):
        if keyfile and keydata is None:
            if not os.path.exists(keyfile):
                random_generator = Random.new().read
                secret = RSA.generate(1024, random_generator)
                with open(keyfile, 'wb') as handle:
                    handle.write(str(secret.exportKey()))
            else:
                with open(keyfile, 'rb') as handle:
                    keydata = handle.read()
        if keydata:
            secret = RSA.importKey(keydata)

        self.secret = secret
        self.public = secret.publickey()
        public_key_readable = str(self.public.exportKey())
        self.public_key_hashed = base64.b64encode(public_key_readable)
        self.address = hashlib.sha224(self.public_key_hashed).hexdigest()
        self.signer = PKCS1_v1_5.new(self.secret)

    def sign(self, data):
        return base64.b64encode(self.signer.sign(data))


class ProtocolBase(object):
    def __init__(self, sock, manager):
        self.sockaddr = IpPort(*sock.getpeername())
        self.sock = sock
        self.manager = manager

    def _send(self, *args):
        for data in args:
            data = str(data)
            self.sock.sendall((str(len(data))).zfill(10))
            self.sock.sendall(data)
            LOG.debug('%r - sent: %r', self, data)

    def _recv(self, datalen=10):
        data = self.sock.recv(datalen)
        if not data:
            raise socket.error("Socket connection broken")
        data = int(data)

        chunks = []
        bytes_recd = 0
        while bytes_recd < data:
            chunk = self.sock.recv(min(data - bytes_recd, 2048))
            if chunk == b'':
                raise socket.error("Socket connection broken")
            chunks.append(chunk)
            bytes_recd = bytes_recd + len(chunk)
        segments = b''.join(chunks)
        LOG.debug('%r - received: %r', self, segments)
        return segments


def calc_diff(block_history, time_now, db_timestamp_last):
    half_hour_ago = time_now - (60*30)
    blocks_per_30 = 0
    for row in block_history:
        if row[2] is not None:
            stamp = float(row[2][0][0])
        else:
            stamp = row[3]
        if stamp > half_hour_ago:
            blocks_per_30 += 1

    if not blocks_per_30:
        return None

    diff = blocks_per_30 * 2
    drop_factor = (60*2)  # drop 0,5 diff per minute #hardfork
    if time_now > db_timestamp_last + (60*2):  # start dropping after 2 minutes
        diff = diff - (time_now - db_timestamp_last) / drop_factor  # drop 0,5 diff per minute (1 per 2 minutes)
        # drop diff per minute if over target
    if time_now > db_timestamp_last + (60*6) or diff < LOWEST_DIFFICULTY:  # 5 m lim
        diff = LOWEST_DIFFICULTY  # 5 m lim
    return int(diff)
