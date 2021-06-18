import json
import threading
from time import sleep
from .network import Server


class Node:
    def __init__(self, host, port):
        self.server_host, self.server_port = host, port
        self.server = Server(host, port)

        t = threading.Thread(target=self.read_buffer)
        t.start()

    def connect_to_peer(self, host, port):
        peer = self.server.connect(host, port)
        self.send_hello(peer)

    def send_hello(self, peer):
        print('[*] Sending hello to new peer', peer.id)
        msg = {
            "type": "hello",
            "version": "0.2.0",
            "agent": "Marabu-Core Client 0.7"
        }
        data = json.dumps(msg, indent=4)
        peer.send(data)

    def remove_peer(self, peer_id):
        p = self.server.peers.pop(peer_id)
        if not p.closed:
            p.close()

    def read_buffer(self):
        while True:
            for peer in list(self.server.peers):
                print('[*] Checking buffer', peer.id)
                while not peer.buffer.empty():
                    data = peer.buffer.get()

                    if data == b'':
                        self.remove_peer(peer.id)
                        break
                    try:
                        msg = json.loads(data.decode('utf-8'))
                        self.parse_msg(msg, peer)
                    except Exception as e:
                        print('[!] Error', e)
                        self.remove_peer(peer.id)
            sleep(1)

    def parse_msg(self, msg, peer):
        if not peer.hello_recv:
            assert 'type' in msg.keys(), '"type" not in hello message'
            assert msg['type'] == 'hello', '"type" not "hello"'
            assert 'version' in msg.keys(), '"version" not in hello message'
            assert msg['version'] == '0.2.0', 'Wrong hello version'

            peer.hello_recv = True
            if not peer.hello_send:
                self.send_hello(peer)
            print('[*] Hello with peer completed', peer.id)
