#!/usr/bin/env python
from __future__ import print_function

from gevent import monkey, spawn
monkey.patch_all()
from gevent.pool import Pool
from gevent.socket import wait_read
from gevent.server import StreamServer

import os
import re
import ast
import time
import json
import string
import socket
import hashlib
import threading
import logging as LOG
from random import shuffle
from collections import defaultdict

from Crypto.Hash import SHA

from .common import Abuse, IpPort, ProtocolBase, MinerResult, Identity, calc_diff, ConsensusBlock
from .common import POOL_PORT, MINER_TUNE_GOAL, MINER_TUNE_HISTORY, MINER_VERSION_ROOT, PROTO_VERSION, CONNECT_TIMEOUT, LOWEST_DIFFICULTY
from . import bismuth


# TODO: when there is no consensus, or we're behind ..
#   run server.stop_accepting or server.start_accepting
class Miners(object):
    def __init__(self, peers, bind=None, max_conns=5000):
        if bind is None:
            bind = ('127.0.0.1', POOL_PORT)
        elif isinstance(bind, str):
            bind = bind.split(':')
            bind[1] = int(bind[1])
        self.peers = peers
        self.pool = Pool(max_conns)
        self.server = StreamServer(tuple(bind), self._on_connect, spawn=self.pool)
        self.server.start()

    def on_found(self, result, miner):
        # Ensure that the work delivered is exactly what was requested
        valid = bismuth.verify(result.address, result.nonce, result.block, result.diff)
        if not valid:
            Abuse.strike(miner.sockaddr)
            if Abuse.blocked(miner.sockaddr):
                miner.close()
            LOG.error('Invalid block submitted! %r %r', result, miner.diff, valid)
            return False
        # The miner will not be punished for providing
        # training blocks which don't match the right
        # hash... but they won't be rewarded for the work
        return ResultsManager.on_result(result, miner)

    def stop(self):
        self.server.stop()
        self.pool.kill()

    def _on_connect(self, socket, address):
        peer = IpPort(*address)
        if Abuse.blocked(peer):
            LOG.debug('Miner %r - accept() blocked: abuse', address)
            socket.close()
            return
        client = MinerServer(socket, self)
        client.run()


# Don't allow client to submit same block twice
# Verify that clients don't submit each others blocks
# Verify that the block difficulty matches or is above that set by this code (the pool)
class MinerServer(ProtocolBase):
    def __init__(self, sock, manager):
        super(MinerServer, self).__init__(sock, manager)
        self._reward_address = None
        self._history = []
        self._diff = None
        self._last_found = None

    def __repr__(self):
        return "Miner(%r)" % (self.sockaddr,)

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    @property
    def address(self):
        return self._reward_address

    def _tune(self):
        # Fine-tune the difficulty so the miner finds at least 1 block every N seconds
        # Use a rolling history of block find times to get the average difficulty
        peers_diff = self.manager.peers.difficulty()
        if peers_diff is None:
            print('No peer diff')
            return False
        hist_time = defaultdict(int)
        hist_count = defaultdict(int)
        for diff, duration in self._history:
            hist_time[diff] += duration
            hist_count[diff] += 1.0
        ideal_diff = self._diff if self._diff is not None else 40
        best_time = 0
        for diff, total_time in hist_time.items():
            avg_time = total_time / hist_count[diff]
            if avg_time > best_time and avg_time < MINER_TUNE_GOAL:
                best_time = avg_time
                ideal_diff = diff
        if best_time > MINER_TUNE_GOAL:
            ideal_diff -= 1
        else:
            if self._last_found > (time.time() - MINER_TUNE_GOAL):
                ideal_diff += 0.5
        #
        our_height = ResultsManager.highest_difficulty()
        self._diff = min([our_height + 1, sum([peers_diff, ideal_diff]) / 2])
        # Trim history
        if len(self._history) > MINER_TUNE_HISTORY:
            self._history = self._history[0 - MINER_TUNE_HISTORY:]

    def _cmd_sendsync(self):
        # They've mistaken us for a regular node, no a pool
        pass

    def _cmd_version(self):
        """
        Check client version string, and save their reward address
        """
        version = self._recv().split('.')
        rewards = self._recv()
        if version[0] != MINER_VERSION_ROOT:
            self._send('notok')
            return self.close()
        is_hex = all(c in string.hexdigits for c in rewards)
        if len(rewards) == 56 and is_hex:
            self._reward_address = rewards
        LOG.info('Client connected: version="%r" address="%r"', version, self._reward_address)
        self._send('ok')

    def _cmd_miner_fetch(self):
        if self._diff is None:
            self._tune()
            return self._send('wait')
        LOG.info('%r - Fetch Job', self)
        peers = self.manager.peers
        consensus = peers.consensus()
        if len(consensus):
            self._send(int(self._diff), peers.identity.address, consensus[0][0][1])
        else:
            # Send training data when there is no consensus
            self._send(int(self._diff), peers.identity.address, os.urandom(28).encode('hex'))

    def _cmd_miner_exch(self):
        items = None
        try:
            items = (self._recv(), self._recv(), self._recv())
            result = MinerResult(int(items[0]), self.manager.peers.identity.address, items[1], items[2])
        except Exception as ex:
            LOG.exception("Miner %r - Rejecting Items: %r - %r", self.sockaddr, items, ex)
            Abuse.strike(self.sockaddr)
            return self._cmd_miner_fetch()  # wat u send, thafuq?
        if result:
            if self.manager.on_found(result, self):
                if self._last_found is not None:
                    mine_duration = time.time() - self._last_found
                    self._history.append((self._diff, mine_duration))
                self._last_found = time.time()
            # Finally, re-calculate the diff rate etc...
            self._tune()
        return self._cmd_miner_fetch()

    def _cmd_status(self):
        self._send(str(self.manager.status()))

    def run(self):
        try:
            while self.sock:
                try:
                    wait_read(self.sock.fileno(), timeout=10)
                except socket.timeout:
                    continue
                cmd_name = self._recv()
                if not cmd_name:
                    break
                cmd_func = getattr(self, '_cmd_' + cmd_name, None)
                if not cmd_func:
                    raise RuntimeError('Miner %r - Unknown CMD: %r' % (self.sockaddr, cmd_name))
                cmd_func()
        except Exception as ex:
            LOG.exception("Miner %r - Error running: %r", self.sockaddr, ex)
            Abuse.strike(self.sockaddr)
        finally:
            self.close()


class BismuthClient(ProtocolBase):
    def __init__(self, sock, manager):
        super(BismuthClient, self).__init__(sock, manager)

        toplist = manager.consensus()
        if not len(toplist):
            raise RuntimeError('Invalid state - no consensus')
        self.blocks = [
            (row[0].height, row[0].hash, None, row[0].stamp)
            for row in reversed(toplist)
        ]

        assert len(self.blocks) > 0
        self.blockheight = self.blocks[-1][0]
        self.blockhash = self.blocks[-1][1]
        self.their_blockheight = 0
        self.their_blockhash = ''
        self.peers = None

    def __repr__(self):
        return "BismuthClient(%r)" % (self.sockaddr,)

    @property
    def difficulty(self):
        if len(self.blocks):
            newest_block = self.blocks[-1]
            if newest_block[2] is not None:
                latest_block_time = float(max([X[0] for X in newest_block[2]]))
            else:
                latest_block_time = float(self.blocks[-1][3])
            assert latest_block_time > 0
            latest_time = float(latest_block_time)
            now = time.time()
            return calc_diff(self.blocks, now, latest_time)

    def _trim_blocks(self):
        # Remove unnecessary blocks
        # TODO: pop off end of list, by time, ensure 30 mins
        if len(self.blocks) > 120:
            self.blocks = self.blocks[-120:]

    def status(self):
        if not self.sock:
            return "dead"
        if not self.synched:
            return "synching" + " (%d <- %d[%s])" % (self.their_blockheight, self.blockheight, self.blockhash[:10])
        diff = self.difficulty
        if diff:
            diff = ' (%.2f diff)' % (diff,)
        else:
            diff = ''

        return "active" + diff + " (%d[%s])" % (self.blockheight, self.blockhash[:10])

    def submit_block(self, new_txns):
        self._send('block', str(new_txns))

    def pushpeers(self):
        shuffle(self.peers)
        self._send("peers", "\n".join(map(str, self.peers[:10])))

    def connect(self):
        try:
            self._send("version", PROTO_VERSION)
            data = self._recv()
            if data != "ok":
                raise RuntimeError("Peer %r - protocol mismatch: %r %r" % (self.sockaddr, data, PROTO_VERSION))
                return False
        except Exception as ex:
            Abuse.strike(self.sockaddr)
            LOG.warning("Peer %r - Connect/Hello error: %r", self.sockaddr, ex)
            return False
        LOG.info('Peer %r - Connected', self.sockaddr)
        return True

    def _cmd_nonewblk(self):
        pass

    def _cmd_peers(self):
        subdata = self._recv()
        self.peers = re.findall("'([\d\.]+)', '([\d]+)'", subdata)
        # TODO: filter peers and stuff

    def _cmd_blocksfnd(self):
        self._send("blockscf")
        block_list = ast.literal_eval(self._recv())
        block = None
        for transaction_list in block_list:
            # TODO: verify transactions
            self.blockhash = hashlib.sha224(str(transaction_list) + self.blockhash).hexdigest()
            self.blockheight += 1
            block = (self.blockheight, self.blockhash, transaction_list)

            for txn in transaction_list:
                assert txn[0] is not None

            self.blocks.append(block)
            if self.blockheight == self.their_blockheight:
                self.their_blockhash = self.blockhash

        self._trim_blocks()
        # XXX: speed up initial sync... instead of at other ends leisure
        #      request more sync until our expected and their actual are the same
        if self.blockheight != self.their_blockheight:
            self._send("sendsync")

    def _cmd_blocknf(self):
        block_hash_delete = self._recv()
        # print("XXX: Asked to delete block", block_hash_delete)
        self.blocks = filter(lambda x: x[1] != block_hash_delete, self.blocks)
        if block_hash_delete in (self.blockhash, self.their_blockhash):
            if len(self.blocks):
                # print("XXX: Deleting block:", self.blocks, block_hash_delete, self.blockhash, self.their_blockhash)
                self.blockhash = self.blocks[-1][1]
                self.blockheight = self.blocks[-1][0]

    def _cmd_sync(self):
        self._send("blockheight", self.blockheight)
        self.their_blockheight = int(self._recv())
        if self.their_blockheight == self.blockheight:
            self.their_blockhash = self.blockhash
        update_me = (self.their_blockheight >= self.blockheight)
        if update_me:
            self._send(self.blockhash)
        else:
            self.their_blockhash = self._recv()
            if self.their_blockhash != self.blockhash:
                cut = 0
                for N, txn in enumerate(reversed(self.blocks)):
                    if txn[1] == self.their_blockhash:
                        self.blockheight = self.their_blockheight = txn[0]
                        self.blockhash = txn[1]
                        cut = N
                        break
                if cut:
                    self.blocks = self.blocks[:0 - cut]

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    @property
    def synched(self):
        return (self.blockheight == self.their_blockheight) and (self.blockhash == self.their_blockhash)

    def run(self):
        sync_interval = 10
        sync_last = time.time()
        while self.sock:
            try:
                wait_read(self.sock.fileno(), timeout=sync_interval)
            except socket.timeout:
                # After initial synching, send periodic sync requests
                now = time.time()
                if sync_last < (now - sync_interval):
                    self._send("sendsync")
                    sync_last = now

            cmd_name = self._recv()
            if not cmd_name:
                break
            cmd_func = getattr(self, '_cmd_' + cmd_name, None)

            if not cmd_func:
                LOG.warning('Peer %r - Unknown CMD: %r' % (self.sockaddr, cmd_name))
                self.close()
                return False

            LOG.debug("Peer %r - Received command: %r", self.sockaddr, cmd_name)
            cmd_func()
        return True


class ResultsManager(object):
    LOCK = threading.Lock()
    HEIGHTS = dict()
    BLOCK = None
    HIGHEST = 0
    LOGHANDLE = None
    LOGFILENAME = None
    HISTORY = list()

    @classmethod
    def reset(cls):
        cls.LOCK.acquire()
        try:
            cls.HEIGHTS = dict()
            cls.BLOCK = None
            cls.HIGHEST = 0
            cls.LOGHANDLE = None
            cls.LOGFILENAME = None
            cls.HISTORY = list()
        finally:
            cls.LOCK.release()

    @classmethod
    def _history_add(cls, consensus, now=None):
        assert consensus.stamp is not None
        assert isinstance(consensus.stamp, (int, float))

        if now is None:
            now = time.time()
        half_hour_ago = now - (60*30)

        history = cls.HISTORY
        trim_end = len(history)
        if len(history):
            for N, row in enumerate(reversed(history)):
                if row.height < consensus.height:
                    break
                trim_end -= 1
                if trim_end <= 0:
                    LOG.warning('XXX History trim fail! N:%r  ROW:%r  CONSENSUS:%r  HISTORY:%r', N, row, consensus, history)
                assert trim_end > 0

        history = history[:trim_end]
        history.append(consensus)

        history = filter(lambda x: x.stamp > half_hour_ago, history)

        cls.HISTORY = history

    @classmethod
    def history_fetch(cls, oldest_time, height=None):
        cls.LOCK.acquire()
        try:
            results = list()
            for consensus in reversed(cls.HISTORY):
                if consensus.stamp < oldest_time:
                    break
                if height and consensus.height > height:
                    continue
                results.append(consensus)
        finally:
            cls.LOCK.release()
        return results

    @classmethod
    def highest_difficulty(cls):
        heights = sorted(cls.HEIGHTS.keys())
        if len(heights):
            return heights[-1]
        return LOWEST_DIFFICULTY

    @classmethod
    def on_consensus(cls, consensus, now=None):
        assert consensus.stamp is not None
        assert isinstance(consensus.stamp, (int, float))

        if cls.BLOCK == consensus:
            return

        cls.LOCK.acquire()
        try:
            LOG.info('New consensus %r', consensus)
            cls._history_add(consensus, now)

            cls.HEIGHTS = dict()
            cls.BLOCK = consensus
            cls.HIGHEST = 0

            if cls.LOGHANDLE:
                cls.LOGHANDLE.flush()
                cls.LOGHANDLE.close()
                done_filename = 'data/done/%s' % (os.path.basename(cls.LOGHANDLE.name),)
                if cls.LOGFILENAME is not None and not os.path.exists(done_filename):
                    os.rename(cls.LOGFILENAME, done_filename)
                else:
                    LOG.warning('Merging block logs: %r -> %r', cls.LOGHANDLE.name, done_filename)
                    with open(done_filename, 'a') as handle_output:
                        with open(cls.LOGFILENAME, 'r') as handle_input:
                            while True:
                                data = handle_input.read(4096)
                                if not data:
                                    break
                                handle_output.write(data)
                    os.unlink(cls.LOGFILENAME)

            filename = 'data/audit/%s.block' % (consensus.hash,)
            cls.LOGHANDLE = open(filename, 'a')
            cls.LOGFILENAME = filename
            LOG.warning('New consensus: %r', consensus)
        finally:
            cls.LOCK.release()

    @classmethod
    def on_result(cls, result, miner):
        if not cls.BLOCK or result.block != cls.BLOCK[1]:
            # If no latest consensus block - ignore, it's training data
            return False

        cls.LOCK.acquire()
        try:
            if result.diff > cls.HIGHEST:
                cls.HIGHEST = result.diff
                cls.HEIGHTS[int(result.diff)] = result
                LOG.warning('New highest for %s: %d', result.block, result.diff)
            if cls.LOGHANDLE:
                cls.LOGHANDLE.write(json.dumps([
                    time.time(), miner.address, int(result.diff), result.nonce
                ]) + "\n")
        finally:
            cls.LOCK.release()
        return True

    @classmethod
    def sign_blocks(cls, identity, result):
        block_send = list()

        block_timestamp = '%.2f' % time.time()
        transaction_reward = (str(block_timestamp), str(result.address[:56]), str(result.address[:56]),
                              '%.8f' % float(0), "0", str(result.nonce))  # only this part is signed!

        transaction_hash = SHA.new(str(transaction_reward))
        signature_b64 = identity.sign(transaction_hash)

        block_send.append((str(block_timestamp), str(result.address[:56]), str(result.address[:56]), '%.8f' % float(0), str(signature_b64),
                           str(identity.public_key_hashed), "0", str(result.nonce)))  # mining reward tx
        return block_send


class PeerManager(object):
    def __init__(self, identity=None):
        if identity is None:
            identity = Identity()
        self.peers = dict()
        self.identity = identity

    def status(self):
        active_peers = filter(lambda x: x.synched, self.peers)
        consensus = self.consensus()
        if consensus:
            consensus = consensus[0]
        return dict(
            peers=(len(active_peers), len(self.manager.peers)),
            diff=self.difficulty(),
            block=consensus,
        )

    def add(self, peer):
        assert isinstance(peer, IpPort)
        if peer not in self.peers and not Abuse.blocked(peer):
            return spawn(self._run, peer)

    def difficulty(self):
        values = filter(None, [peer.difficulty for peer in self.peers.values()])
        if len(values):
            return sum(values) / float(len(values))

    def stop(self):
        for peer in self.peers.values():
            peer.close()

    def consensus(self):
        """
        Highest block consensus information for all peers
        Returns tuple of:
          * Block Height
          * Number of Votes
          * Percentage of votes
        """
        total_peers = 0
        blocks = list()
        for peer in self.peers.values():
            assert len(peer.blocks) > 0
            if not peer.synched:
                continue
            total_peers += 1
            blocks.extend(peer.blocks)
        # blocks = [peer.blocks[-1] for peer in self.peers.values()
        #           if len(peer.blocks) and peer.synched]

        counts = defaultdict(int)
        heights = dict()
        timestamps = dict()
        for block in blocks:
            heights[block[1]] = block[0]
            counts[block[1]] += 1
            # Retrieve newest timestamp for block
            if block[2] is not None:
                stamp = max([float(X[0]) for X in block[2]])
                assert stamp is not None
                timestamps[block[1]] = stamp
            else:
                timestamps[block[1]] = block[3]

        result = list()
        for block_hash, num in counts.items():
            block_height = heights[block_hash]
            consensus_pct = (num / float(total_peers)) * 100.0
            row = (ConsensusBlock(int(block_height), block_hash, timestamps[block_hash]), num, consensus_pct)
            result.append(row)

        results = sorted(result, lambda x, y: int(y[0].height - x[0].height))
        half_hour_ago = time.time() - (60*30)
        if len(results):
            # If there isn't enough data to get an accurate Difficulty rating
            # (requires 30 mins of data), then fill out with stuff from Ledger DB
            oldest_result = results[-1]
            oldest_time = min([X[0].stamp for X in results])
            if oldest_time < half_hour_ago:
                merge_rows = ResultsManager.history_fetch(half_hour_ago, oldest_result[0].height)
                for row in merge_rows:
                    results.append((row, 0, 100))
        else:
            results = [(row, 0, 100) for row in ResultsManager.history_fetch(half_hour_ago)]

        # Verify consensus is above 50%, and notify result manager
        if results[0][2] >= 50:
            # LOG.warning('XXX adding new consensus peers:%r %r', total_peers, results)
            ResultsManager.on_consensus(results[0][0])

        return results

    def _run_client(self, peer, client):
        fail = False
        try:
            if not client.connect():
                fail = True
            else:
                self.peers[peer] = client
        except Exception as ex:
            fail = True
            Abuse.strike(peer)
            LOG.info("Peer %r - Handshake error (%d strikes) - %r",
                     peer, Abuse.strikes(peer), ex)
        else:
            Abuse.reset(peer)
            client.run()
        if fail:
            client.close()
            client = None
        return client

    def _run(self, peer, client=None):
        sock = None
        if not client:
            try:
                sock = socket.create_connection(peer, timeout=CONNECT_TIMEOUT)
                sock.settimeout(None)
                client = BismuthClient(sock, self)
            except socket.error as ex:
                Abuse.strike(peer)
                LOG.info("Peer %r - Connect Error (%d strikes): %r",
                         peer, Abuse.strikes(peer), ex)
        try:
            if client:
                client = self._run_client(peer, client)
        except socket.error as ex:
            LOG.warning('Peer %r - Socket Error: %r', peer, ex)
        except Exception as ex:
            LOG.exception("Peer %r - Run Error %r", peer, ex)
        finally:
            try:
                if client:
                    client.close()
                elif sock:
                    sock.close()
            except Exception:
                LOG.exception("While closing peer")
            if peer in self.peers:
                del self.peers[peer]
