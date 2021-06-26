from library.Canonicalize import canonicalize
from hashlib import sha256


def parse_object(obj, node, peer_id):
    obj_id = sha256(canonicalize(obj)).hexdigest()
    node.log.info('Peer %s sent object %s with id %s' % (peer_id, obj, obj_id))
    if not node.db.get(obj_id):
        node.db.set(obj_id, obj)
        node.broadcast_object(obj_id)
