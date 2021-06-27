import json
import asyncore
import socket
import re
import threading
from time import sleep
from .network import Server
from .database import PenguinDB
from .blockchain import parse_object
import config
import logging
from nacl.signing import SigningKey


class Node:
    log = logging.getLogger('Node')

    def __init__(self, host, port, db_path):
        self.db = PenguinDB(db_path)

        self.server_host, self.server_port = host, port
        self.server = Server(host, port)

        t1 = threading.Thread(target=self.read_buffer)
        t1.start()

        if self.db.get('peers') == []:
            self.log.info('Using hardcoded peers')
            self.db.set('peers', [config.network.PEER_HOST + ':' + str(config.network.PEER_PORT)])

        for peer_id in self.db.get('peers'):
            self.connect_to_peer(peer_id)

        self.connected_peers = []

        self.privkey = SigningKey(config.blockchain.ACCOUNT_SEED)
        self.pubkey = self.privkey.verify_key

        asyncore.loop()

    def connect_to_peer(self, peer_id):
        (hostname, port) = peer_id.split(':')
        host = socket.gethostbyname(hostname)
        peer_id = ':'.join([host, port])

        if peer_id in self.server.peers.keys() or len(self.server.peers.keys()) == 5:
            self.log.debug('Peer %s already in list' % peer_id)
            return

        self.log.info('Connecting to peer %s' % peer_id)
        if self.server.connect_to_peer(peer_id):
            self.send_hello(peer_id)

    def send_hello(self, peer_id):
        self.log.info('Sending hello to %s' % peer_id)

        msg = {
            'type': 'hello',
            'version': config.node.VERSION,
            'agent': config.node.AGENT
        }

        peer = self.server.peers[peer_id]
        peer.say(msg)
        peer.hello_send = True

    def send_peers(self, peer_id):
        self.log.info('Sending peers to %s' % peer_id)

        msg = {'type': 'peers'}
        msg['peers'] = list(self.server.peers.keys())

        self.server.peers[peer_id].say(msg)

    def get_peers(self, peer_id):
        self.log.info('Requesting peers from %s' % peer_id)

        msg = {'type': 'getpeers'}
        self.server.peers[peer_id].say(msg)

    def get_mempool(self, peer_id):
        self.log.info('Requesting mempool from %s' % peer_id)

        msg = {'type': 'getmempool'}
        self.server.peers[peer_id].say(msg)

    def get_chaintip(self, peer_id):
        self.log.info('Requesting chaintip from %s' % peer_id)

        msg = {'type': 'getchaintip'}
        self.server.peers[peer_id].say(msg)

    def broadcast_object(self, obj_id):
        self.log.info('Broadcasting message: %s', obj_id)

        msg = {
            'type': 'ihaveobject',
            'objectid': obj_id
        }
        self.server.broadcast(msg)

    def send_object(self, peer_id, obj):
        self.log.info('Sending message %s to %s' % (str(obj), peer_id))

        msg = {
            'type': 'object',
            'object': obj
        }
        self.server.peers[peer_id].say(msg)

    def send_error(self, peer_id, error_message):
        self.log.info('Sending error message %s to %s' % (error_message, peer_id))

        msg = {
            'type': 'error',
            'error': error_message
        }
        self.server.peers[peer_id].say(msg)

    def request_object(self, peer_id, obj_id):
        self.log.info('Requesting object with id %s from %s' % (obj_id, peer_id))

        msg = {
            'type': 'getobject',
            'objectid': obj_id
        }
        self.server.peers[peer_id].say(msg)

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
                    try:
                        datalist = data.decode('utf-8').split('\n')
                        for d in datalist:
                            if d:
                                msg = json.loads(d)
                                self.parse_msg(msg, peer)
                    except json.decoder.JSONDecodeError:
                        self.log.error('Error decoding json data from peer %s: %s' % (peer.id, data))
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
            self.log.info('Received hello from %s' % peer.id)
            if not peer.hello_send:
                self.send_hello(peer.id)

            self.connected_peers.append(peer.id)
            self.db.set('peers', self.connected_peers)
            self.get_peers(peer.id)
            self.request_object(peer.id, config.blockchain.GENESIS_ID)
            self.get_mempool(peer.id)
            self.get_chaintip(peer.id)
        elif msg['type'] == 'getpeers':
            self.log.info('Received getpeers from %s' % peer.id)
            self.send_peers(peer.id)
        elif msg['type'] == 'peers':
            self.log.info('Received peers from %s' % peer.id)
            peer_list = msg['peers']
            for peer in peer_list:
                try:
                    self.connect_to_peer(peer)
                except (AttributeError, ValueError, socket.gaierror):
                    self.log.debug('Peer is malformed %s' % peer)
        elif msg['type'] == 'ihaveobject':
            obj_id = msg['objectid']
            self.log.info('Peer %s has object with id %s' % (peer.id, obj_id))
            self.request_object(peer.id, obj_id)
        elif msg['type'] == 'object':
            try:
                parse_object(msg['object'], self, peer.id)
            except AssertionError as error_msg:
                self.log.error(error_msg)
                self.send_error(peer.id, error_msg)
        elif msg['type'] == 'getobject':
            obj_id = msg['objectid']
            obj = self.db.get(obj_id)
            if obj:
                self.send_object(peer.id, obj)
        elif msg['type'] == 'mempool':
            self.log.info('Got mempool of %s: %s' % (peer.id, str(msg['txids'])))
            for tx_id in msg['txids']:
                self.request_object(peer.id, tx_id)
        elif msg['type'] == 'chaintip':
            self.log.info('Got chaintip id %s' % msg['blockid'])
            self.request_object(peer.id, msg['blockid'])
        elif msg['type'] == 'error':
            self.log.error('Got error message from %s: %s' % (peer.id, msg['error']))
        else:
            error_message = 'Unknown message type: %s' % msg['type']
            self.log.error(error_message)
            self.send_error(peer.id, error_message)
