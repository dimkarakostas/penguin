import json
import socket
import re
import threading
from time import sleep
from .network import Server
from .database import PenguinDB
import config
import logging


class Node:
    log = logging.getLogger('Node')

    def __init__(self, host, port, db_path):
        self.db = PenguinDB(db_path)

        self.server_host, self.server_port = host, port
        self.server = Server(host, port)

        t1 = threading.Thread(target=self.read_buffer)
        t1.start()
        t2 = threading.Thread(target=self.log_peers)
        t2.start()

        if self.db.get('peers') == []:
            self.log.info('Using hardcoded peers')
            self.db.set('peers', [[config.network.PEER_HOST, config.network.PEER_PORT]])

        for [peer_host, peer_port] in self.db.get('peers'):
            t = threading.Thread(target=self.connect_to_peer, args=(peer_host, peer_port))
            t.start()

    def connect_to_peer(self, hostname, port):
        host = socket.gethostbyname(hostname)
        if (host, port) in self.server.peers.keys() or len(self.server.peers.keys()) == 5:
            self.log.error('Peer %s already in list' % str((hostname, port)))
            return

        peer_id = ':'.join([host, str(port)])
        self.log.info('Connecting to peer %s' % peer_id)
        if self.server.connect(host, port):
            self.send_hello(peer_id)

            peer = self.server.peers[peer_id]

            if not peer.hello_recv:
                for _ in range(5):
                    sleep(2)
            if not peer.hello_recv:
                self.log.error('Did not receive hello back %s' % peer_id)
                self.remove_peer(peer)
            else:
                self.get_peers(peer_id)

    def send_hello(self, peer_id):
        self.log.info('Sending hello to %s' % peer_id)

        msg = {
            'type': 'hello',
            'version': config.node.VERSION,
            'agent': config.node.AGENT
        }

        peer = self.server.peers[peer_id]
        peer.send(msg)
        peer.hello_send = True

    def send_peers(self, peer_id):
        self.log.info('Sending peers to %s' % peer_id)

        msg = {
            'type': 'peers'
        }
        msg['peers'] = [':'.join([i[0], str(i[1])]) for i in self.server.peers.keys()]

        self.server.peers[peer_id].send(msg)

    def log_peers(self):
        while True:
            sleep(60)
            self.db.set('peers', list(self.server.peers.keys()))
            for peer_id in self.server.peers.keys():
                if self.server.peers[peer_id]:
                    self.get_peers(peer_id)

    def get_peers(self, peer_id):
        self.log.info('Requesting peers from %s' % peer_id)

        msg = {
            'type' : 'getpeers'
        }
        self.server.peers[peer_id].send(msg)

    def remove_peer(self, peer):
        self.server.peers[peer.id] = None

    def read_buffer(self):
        while True:
            for (_, peer) in list(self.server.peers.items()):
                if peer is None:
                    continue
                while not peer.buffer.empty():
                    data = peer.buffer.get()

                    if data == b'':
                        self.remove_peer(peer)
                        break
                    msg = json.loads(data.decode('utf-8'))
                    self.parse_msg(msg, peer)
            sleep(1)

    def parse_msg(self, msg, peer):
        if not peer.hello_recv:
            try:
                assert msg['type'] == 'hello', 'type not hello'
                assert re.match(config.node.VERSION_REGEX, msg['version']), 'Wrong hello version'
            except AssertionError:
                peer.close()
                return

            peer.hello_recv = True
            if not peer.hello_send:
                self.send_hello(peer.id)
            self.log.info('Received hello from %s' % peer.id)
        elif msg['type'] == 'getpeers':
            self.log.info('Received getpeers from %s' % peer.id)
            self.send_peers(peer.id)
        elif msg['type'] == 'peers':
            self.log.info('Received peers message from %s' % peer.id)
            peer_list = msg['peers']
            for peer in peer_list:
                (host, port) = peer.split(':')
                try:
                    self.connect_to_peer(host, int(port))
                except (AttributeError, ValueError):
                    self.log.error('Host is malformed %s' % ((host, port)))
        else:
            self.log.error('Message type unknown %s' % str(msg['type']))
