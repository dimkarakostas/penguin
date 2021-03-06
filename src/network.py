import asyncore
import collections
import logging
import socket
import queue
from library.Canonicalize import canonicalize


MAX_MESSAGE_LENGTH = 4096


class Client(asyncore.dispatcher):

    def __init__(self, host_address, id):
        asyncore.dispatcher.__init__(self)

        self.id = id
        self.log = logging.getLogger('(%s)' % self.id)

        self.buffer = queue.Queue()
        self.hello_send, self.hello_recv = False, False

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.outbox = collections.deque()

        self.log.info('Connecting to peer')
        try:
            self.connect(host_address)
        except OSError:
            self.log.debug('OSError in Connection')
            return

    def is_live(self):
        return (self.hello_send and self.hello_recv)

    def say(self, message):
        self.log.info('Sending %s' % message)
        self.outbox.append(canonicalize(message) + b'\n')

    def handle_write(self):
        if not self.outbox:
            return
        message = self.outbox.popleft()
        if len(message) > MAX_MESSAGE_LENGTH:
            raise ValueError('Message too long')
        self.send(message)

    def handle_read(self):
        try:
            message = self.recv(MAX_MESSAGE_LENGTH)
            if message == b'':
                self.close()
                self.hello_send = False
            else:
                self.buffer.put(message)
        except BlockingIOError:
            self.log.debug('IO Error')
            self.close()
            self.hello_send = False
        except OSError:
            self.log.debug('OS Error')
            self.close()
            self.hello_send = False


class RemoteClient(asyncore.dispatcher):
    def __init__(self, socket, host):
        asyncore.dispatcher.__init__(self, socket)
        self.host = host

        self.outbox = collections.deque()

        self.buffer = queue.Queue()

        self.hello_send, self.hello_recv = False, False

    def say(self, message):
        self.outbox.append(canonicalize(message) + b'\n')

    def handle_read(self):
        try:
            message = self.recv(MAX_MESSAGE_LENGTH)
            self.buffer.put(message)
        except BlockingIOError:
            self.log.debug('IO Error')
            self.close()
        except OSError:
            self.log.debug('OS Error')
            self.close()

    def handle_write(self):
        if not self.outbox:
            return
        message = self.outbox.popleft()
        if len(message) > MAX_MESSAGE_LENGTH:
            raise ValueError('Message too long')
        self.send(message)


class Host(asyncore.dispatcher):
    log = logging.getLogger('Server')

    def __init__(self, host, port, server):
        asyncore.dispatcher.__init__(self)

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.bind((host, port))
        self.listen(1)

        self.log.info('Server is listening on: %s' % str((host, port)))

        self.server = server

    def handle_accept(self):
        socket, (host, port) = self.accept()
        peer_id = ':'.join([host, str(port)])
        self.server.peers[peer_id] = RemoteClient(socket, self)
        self.log.info('Accepted peer %s' % str((host, port)))

    def handle_read(self):
        self.log.info('Received message: %s', self.read())


class Server:
    def __init__(self, host, port):
        self.log = logging.getLogger('Server')
        self.peers = {}
        self.host = Host(host, port, self)

        self.log.info('Server set up')

    def connect_to_peer(self, peer_id):
        (host, port) = peer_id.split(':')
        self.peers[peer_id] = Client((host, int(port)), peer_id)
        return True

    def broadcast(self, message):
        self.log.info('Broadcasting message: %s', message)
        for (peer_id, peer) in self.peers.items():
            if peer.is_live():
                peer.say(message)
