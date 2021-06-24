import config
from src import node

server_host, server_port = config.network.SERVER_HOST, config.network.SERVER_PORT
n = node.Node(server_host, server_port, config.node.DB_PATH)
