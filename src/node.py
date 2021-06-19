import json
import socket
import re
import threading
from time import sleep
from .network import Server
import config


class Node:
    def __init__(self, host, port):
        self.server_host, self.server_port = host, port
        self.server = Server(host, port)

        t = threading.Thread(target=self.read_buffer)
        t.start()

        t = threading.Thread(target=self.log_peers)
        t.start()

    def connect_to_peer(self, hostname, port):
        host = socket.gethostbyname(hostname)
        if (host, port) in self.server.peers.keys() or len(self.server.peers.keys()) == 5:
            print('[!] Peer already connected', host, port)
            return

        peer_id = (host, port)
        print('[*] Connecting to peer', peer_id)
        if self.server.connect(host, port):
            self.send_hello(peer_id)

            peer = self.server.peers[peer_id]
            for _ in range(5):
                sleep(2)
            if not peer.hello_recv:
                self.remove_peer(peer)
            else:
                self.get_peers(peer_id)

    def send_hello(self, peer_id):
        print('[*] Sending hello to', peer_id)

        msg = {
            'type': 'hello',
            'version': config.node.VERSION,
            'agent': config.node.AGENT
        }

        peer = self.server.peers[peer_id]
        peer.send(msg)
        peer.hello_send = True

    def send_peers(self, peer_id):
        print('[*] Sending peers to', peer_id)

        msg = {
            'type': 'peers'
        }
        msg['peers'] = [':'.join([i[0], str(i[1])]) for i in self.server.peers.keys()]

        self.server.peers[peer_id].send(msg)

    def log_peers(self):
        while True:
            open('peers.json', 'w').write(
                json.dumps(
                    {'peers': list(self.server.peers.keys())}
                )
            )
            sleep(5)

    def get_peers(self, peer_id):
        print('[*] Requesting peers from', peer_id)

        msg = {
            'type' : 'getpeers'
        }
        self.server.peers[peer_id].send(msg)

    def remove_peer(self, peer):
        p = self.server.peers.pop(peer.id)
        if not p.closed:
            p.close()

    def read_buffer(self):
        while True:
            for (_, peer) in list(self.server.peers.items()):
                if peer.closed:
                    self.remove_peer(peer)
                    continue
                print('[*] Checking buffer', peer.id)
                while not peer.buffer.empty():
                    data = peer.buffer.get()

                    if data == b'':
                        self.remove_peer(peer)
                        break
                    try:
                        msg = json.loads(data.decode('utf-8'))
                        self.parse_msg(msg, peer)
                    except Exception as e:
                        print('[!] Message Parsing Error:', e)
                        self.remove_peer(peer)
            sleep(1)

    def parse_msg(self, msg, peer):
        if not peer.hello_recv:
            assert msg['type'] == 'hello', 'type not hello'
            assert re.match(config.node.VERSION_REGEX, msg['version']), 'Wrong hello version'

            peer.hello_recv = True
            if not peer.hello_send:
                self.send_hello(peer.id)
            print('[*] Received hello from', peer.id)
        elif msg['type'] == 'getpeers':
            print('[*] Received getpeers from', peer.id)
            self.send_peers(peer.id)
        elif msg['type'] == 'peers':
            print('[*] Received peers message from', peer.id)
            peer_list = msg['peers']
            for peer in peer_list:
                (host, port) = peer.split(':')
                self.connect_to_peer(host, int(port))
