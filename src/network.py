import socket
import json
import threading
import queue
from library.Canonicalize import canonicalize

class Peer:
    def __init__(self, connection, id):
        self.connection = connection
        self.id = id

        print('[*] Client established:', id)
        self.closed = False

        self.hello_send, self.hello_recv = False, False

        self.buffer = queue.Queue()

        t = threading.Thread(target=self.listen)
        t.start()

    def listen(self):
        try:
            while True:
                data = self.connection.recv(4096)
                self.buffer.put(data)
                if data == b'':
                    print('[*] Received closing signal', self.id)
                    break
        finally:
            self.close()

    def send(self, data):
        try:
            self.connection.sendall(canonicalize(data))
        except Exception as e:
            print('[!] Error in peer.send', e)
            self.close()

    def close(self):
        print('[*] Closing connection with', self.id)
        self.connection.close()
        self.closed = True


class Server:
    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.sock.bind((host, port))
        self.sock.listen(1)

        print('[*] Server is listening on:', host, port)

        self.peers = {}

        t = threading.Thread(target=self.listen)
        t.start()

    def listen(self):
        while True:
            connection, peer_id = self.sock.accept()
            self.peers[peer_id] = Peer(connection, peer_id)

    def connect(self, peer_host, peer_port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        peer_id = (peer_host, peer_port)
        sock.connect(peer_id)
        self.peers[peer_id] = Peer(sock, peer_id)
