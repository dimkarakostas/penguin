import socket
import json
import threading
import queue

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
                    break
        finally:
            self.close()

    def send(self, data):
        try:
            self.connection.sendall(bytes(data, encoding="utf-8"))
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

        self.peers = set()

        t = threading.Thread(target=self.listen)
        t.start()

    def listen(self):
        while True:
            connection, addr = self.sock.accept()
            self.peers.add(Peer(connection, addr))

    def connect(self, peer_host, peer_port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((peer_host, peer_port))
        p = Peer(sock, (peer_host, peer_port))
        self.peers.add(p)
        return p
