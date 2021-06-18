import config
from src import node

server_host, server_port = config.network.SERVER_HOST, config.network.SERVER_PORT
n = node.Node(server_host, server_port)

peer_host, peer_port = config.network.PEER_HOST, config.network.PEER_PORT
n.connect_to_peer(peer_host, peer_port)
