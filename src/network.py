import socket
import json
import threading
import queue
from time import sleep
from library.Canonicalize import canonicalize
import logging

class Peer:
    def __init__(self, connection, id):
        self.connection = connection
        self.id = id

        self.log = logging.getLogger('%s' % self.id)

        self.buffer = queue.Queue()
        t = threading.Thread(target=self.listen)
        t.start()

        self.log.info('Connection established')
        self.hello_send, self.hello_recv = False, False

    def listen(self):
        try:
            while True:
                try:
                    data = self.connection.recv(4096)
                except ConnectionResetError:
                    self.log.error('Connection reset')
                    break
                except OSError as e:
                    self.log.error('Unexpected error in recv')
                    break
                self.buffer.put(data)
                if data == b'':
                    self.log.info('Received closing signal')
                    break
        finally:
            self.close()

    def send(self, data):
        try:
            self.connection.sendall(canonicalize(data) + b'\n')
        except Exception as e:
            self.log.error('Error in peer.send: %s' % str(e))
            self.close()

    def close(self):
        self.log.info('Closing connection')
        self.connection.close()


class Server:
    def __init__(self, host, port):
        self.log = logging.getLogger('Server')

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.sock.bind((host, port))
        self.sock.listen(1)

        self.log.info('[*] Server is listening on: %s' % str((host, port)))

        self.peers = {}

        t1 = threading.Thread(target=self.listen)
        t1.start()

    def listen(self):
        while True:
            connection, (client_host, client_port) = self.sock.accept()
            self.peers[(client_host, client_port)] = Peer(connection, (client_host, client_port))

    def connect(self, peer_host, peer_port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        peer_id = ':'.join([peer_host, str(peer_port)])
        try:
            sock.settimeout(10)
            sock.connect((peer_host, peer_port))
            sock.settimeout(None)
            self.peers[peer_id] = Peer(sock, peer_id)
            return True
        except socket.timeout:
            self.log.error('Connection timed out: %s' % str((peer_host, peer_port)))
            self.peers[peer_id] = None
            return False
        except (ConnectionRefusedError, OSError) as e:
            self.log.error('Connection refused: %s %s' % (e, str(peer_host, peer_port)))
            self.peers[peer_id] = None
            return False
