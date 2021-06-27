from library.Canonicalize import canonicalize
from hashlib import sha256
from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import HexEncoder
import logging
import config


class UTxO:
    log = logging.getLogger('UTxO')

    def __init__(self, outpoint, node):
        self.tx_id = outpoint['txid']
        self.index = outpoint['index']

        tx = self.node.db.get(self.tx_id)
        assert tx, 'Transaction %s not in db' % self.tx_id

        self.pubkey = tx['outputs'][self.index]['pubkey']
        self.value = tx['outputs'][self.index]['value']


class Transaction:
    log = logging.getLogger('Transaction')

    def __init__(self, obj, node, coinbase=False):
        self.id = sha256(canonicalize(obj)).hexdigest()
        if coinbase:
            assert all([
                'inputs' not in obj,
                len(obj['outputs']) == 1,
                obj['outputs'][0]['value'] == config.blockchain.COINBASE_VALUE
            ]), 'Coinbase tx %s is malformed' % self.id
            self.valid = True
            return

        self.conservation = 0
        self.check_inputs()
        self.outputs = obj['outputs']
        for output in self.outputs:
            self.conservation += output['value']
        assert self.conservation == 0, 'Tx %s does not respect law of conservation' % self.id

    def check_inputs(self):
        tx = dict(obj)
        for inp in tx['inputs']:
            inp['sig'] = None
        self.inputs = obj['inputs']
        for inp in self.inputs:
            sig_bytes = bytes(inp['sig'], 'utf-8')
            try:
                utxo = UTxO(inp['outpoint'], node)
            except AssertionError:
                self.log.debug('UTxO not found for tx %s' % inp['outpoint']['txid'])
                self.valid = False
                return
            try:
                utxo.pubkey.verify(canonicalize(tx), HexEncoder.decode(sig_bytes), encoder=HexEncoder)
            except nacl.exceptions.BadSignatureError:
                assert False, 'Invalid signature for tx %s, UTxO index %d' % (self.id, utxo.index)
            self.conservation -= utxo.value


class Block:
    log = logging.getLogger('Block')

    def __init__(self, obj, node):
        self.valid = False


def parse_object(obj_dict, node, peer_id):
    obj_id = sha256(canonicalize(obj_dict)).hexdigest()
    if obj_dict['type'] == 'transaction':
        node.log.info('%s sent tx %s with id %s' % (peer_id, obj_dict, obj_id))
        try:
            obj = Transaction(obj_dict, node)
        except KeyError:
            assert False, 'Transaction %s is malformed' % obj_id
    elif obj_dict['type'] == 'block':
        node.log.info('%s sent block %s with id %s' % (peer_id, obj_dict, obj_id))
        obj = Block(obj_dict, node)
        if obj_id == config.blockchain.GENESIS_ID:
            obj.valid = True
    else:
        assert False, 'Unknown object type with id %s' % obj_id

    if obj.valid and not node.db.get(obj_id):
        node.log.info('Adding object %s to db' % obj_id)
        node.db.set(obj_id, obj_dict)
        node.broadcast_object(obj_id)
