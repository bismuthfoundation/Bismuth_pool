from gevent import monkey
monkey.patch_all()

import sys
import argparse
import logging as LOG


from .common import POOL_PORT


def parse_args():
    parser = argparse.ArgumentParser(description='PooledBismuth Server Node')
    parser.add_argument('-v', '--verbose', action='store_const',
                        dest="loglevel", const=LOG.INFO,
                        help="Log informational messages")
    parser.add_argument('--debug', action='store_const', dest="loglevel",
                        const=LOG.DEBUG, default=LOG.WARNING,
                        help="Log debugging messages")
    parser.add_argument('--keyfile', default='.bismuth.key', help="Load/save file for miner secret identity", metavar='PATH')
    parser.add_argument('--max-miners', help="Maximum number of miner connections", default=1000, metavar='M')
    parser.add_argument('-p', '--peers', help="Load/save file for found peers", default='peers.txt', metavar='PATH')
    parser.add_argument('-l', '--ledger', help="Bismuth ledger database path", default='../Bismuth/static/ledger.db', metavar='PATH')
    parser.add_argument('-m', '--miners-listen', dest='miners_listen', metavar="LISTEN",
                        default='0.0.0.0:' + str(POOL_PORT), help="Listener port for miners")
    cfg = parser.parse_args()
    LOG.basicConfig(level=cfg.loglevel)
    return cfg


def main():
    cfg = parse_args()

    from .app import PooledBismuth, monitor
    app = PooledBismuth(cfg)
    app.start()

    try:
        monitor(app)
    except KeyboardInterrupt:
        print("Caught Ctrl+C - stopping gracefully")
        app.stop()

if __name__ == "__main__":
    sys.exit(main())
