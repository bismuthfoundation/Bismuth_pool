from __future__ import print_function
import os
import ast
import time
import math
import logging as LOG
from random import shuffle

import gevent

from .common import Identity, IpPort, Abuse, load_consensus
from .pool import PeerManager, Miners, ResultsManager


def read_peers(peers_file):
    if not os.path.exists(peers_file):
        LOG.error('Cannot find peers file: %r', peers_file)
    # return []
    with open(peers_file, 'r') as handle:
        peers = [ast.literal_eval(row) for row in handle]
        shuffle(peers)
        return peers


class PooledBismuth(object):
    def __init__(self, cfg):
        self.cfg = cfg
        self._stop = False
        self._bootstrap_peers = read_peers(cfg.peers)
        self._bootstrap_thread = None
        self.identity = Identity(cfg.keyfile)
        self.peers = PeerManager(self.identity)
        self.miners = Miners(self.peers, cfg.miners_listen, cfg.max_miners) if cfg.miners_listen else None
        for consensus in load_consensus(cfg.ledger):
            ResultsManager.on_consensus(consensus)

    def _add_bootstrap_peers(self):
        """
        Gradually reintroduce a random set of 10 peers every 4 seconds
        """
        bootstrap_peers = self._bootstrap_peers
        while not self._stop:
            shuffle(bootstrap_peers)
            for sockaddr in bootstrap_peers[:10]:
                self.peers.add(IpPort(*sockaddr))
                time.sleep(0.2)
            time.sleep(2.0)

    def _tick_function(self):
        while True:
            Abuse.tick()
            time.sleep(1)

    def start(self):
        if not self._bootstrap_thread:
            self._bootstrap_thread = gevent.spawn(self._add_bootstrap_peers)

    def stop(self):
        self._stop = True
        if self._bootstrap_thread:
            self._bootstrap_thread.join()
        self.miners.stop()
        self.peers.stop()


def monitor(app):
    peers = app.peers
    while True:
        print("")
        print("------------------------------")
        consensus = peers.consensus()
        if len(consensus):
            print("\nConsensus")
            found_100 = 0
            for row in consensus:
                print(" %s %d %.3f" % (row[0], row[1], row[2]))
                if row[2] == 100:
                    found_100 += 1
                if found_100 > 3:
                    break
        if len(peers.peers):
            print("\nClients")
            for peer, client in peers.peers.items():
                print(" %r %r" % (peer, client.status()))
        difficulty = peers.difficulty()
        if difficulty:
            print("\nDifficulty:", difficulty)
        if len(ResultsManager.HEIGHTS):
            print("\nCandidates:")
            sorted_heights = sorted(ResultsManager.HEIGHTS.items())
            for diff, result in sorted_heights:
                print("\t%.2f = %r" % (diff, result))
            # Submit transaction with highest difficulty
            diff, result = sorted_heights[-1]
            for peer in peers.peers.values():
                if peer.synched and int(diff) >= math.floor(peer.difficulty):
                    new_txn = ResultsManager.sign_blocks(app.identity, result)
                    try:
                        peer.submit_block(new_txn)
                    except Exception:
                        LOG.exception('Peer %r - Error Submitting Block')
            print("")
        time.sleep(2)
