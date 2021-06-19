import socket
import json
import threading
import queue
from library.Canonicalize import canonicalize

class Peer:
    def __init__(self, connection, id):
        self.connection = connection
        self.id = id

        self.buffer = queue.Queue()
        t = threading.Thread(target=self.listen)
        t.start()

        print('[*] Connection established:', id)
        self.closed = False
        self.hello_send, self.hello_recv = False, False

    def listen(self):
        try:
            while True:
                try:
                    data = self.connection.recv(4096)
                except ConnectionResetError:
                    print('[!] Connection reset', self.id)
                    break
                except OSError as e:
                    print('[!] Unexpected error in recv', self.id)
                    break
                self.buffer.put(data)
                if data == b'':
                    print('[*] Received closing signal', self.id)
                    break
        finally:
            self.close()

    def send(self, data):
        try:
            self.connection.sendall(canonicalize(data) + b'\n')
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
            connection, (client_host, client_port) = self.sock.accept()
            self.peers[(client_host, client_port)] = Peer(connection, (client_host, client_port))

    def connect(self, peer_host, peer_port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        peer_id = (peer_host, peer_port)
        try:
            sock.settimeout(10)
            sock.connect(peer_id)
            sock.settimeout(None)
            self.peers[peer_id] = Peer(sock, peer_id)
            return True
        except socket.timeout:
            print('[!] Connection timed out', peer_host, peer_port)
            return False
        except ConnectionRefusedError:
            print('[!] Connection refused', peer_host, peer_port)
            return False
