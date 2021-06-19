import config
import json
from src import node

try:
    with open('peers.json') as f:
        peer_list = json.loads(f.read())['peers']
    print('[*] Using existing peer list')
except FileNotFoundError as e:
    peer_list = [[config.network.PEER_HOST, config.network.PEER_PORT]]
    print('[*] Using hardcoded peers')

server_host, server_port = config.network.SERVER_HOST, config.network.SERVER_PORT
n = node.Node(server_host, server_port)

for (peer_host, peer_port) in peer_list:
    n.connect_to_peer(peer_host, peer_port)
