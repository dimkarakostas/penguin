from library.Canonicalize import canonicalize
from hashlib import sha256
from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import HexEncoder
from nacl import exceptions as nacl_exceptions
import logging
import config
import copy
from .exceptions import BlockhainError


class UTxO:
    log = logging.getLogger('UTxO')

    def __init__(self, outpoint, db):
        self.db = db

        self.tx_id = outpoint['txid']
        self.index = outpoint['index']

        tx = self.db.get(self.tx_id)
        if not tx:
            raise BlockhainError('Transaction %s not in db' % self.tx_id)

        self.pubkey = VerifyKey(tx['outputs'][self.index]['pubkey'], encoder=HexEncoder)
        self.value = tx['outputs'][self.index]['value']


class Transaction:
    log = logging.getLogger('Transaction')

    def __init__(self, obj, db, coinbase=False):
        self.id = sha256(canonicalize(obj)).hexdigest()
        self.db = db
        if coinbase:
            if not all([
                'inputs' not in obj,
                len(obj['outputs']) == 1,
                obj['outputs'][0]['value'] == config.blockchain.COINBASE_VALUE
            ]):
                raise BlockhainError('Coinbase tx %s is malformed' % self.id)
            self.valid = True
            return

        self.conservation = 0
        self.check_inputs(obj)
        self.outputs = obj['outputs']
        for output in self.outputs:
            self.conservation += output['value']
        if not self.conservation <= 0:
            raise BlockhainError('Tx %s does not respect law of conservation' % self.id)

        self.valid = True

    def check_inputs(self, obj):
        tx = copy.deepcopy(obj)
        for inp in tx['inputs']:
            inp['sig'] = None

        self.inputs = obj['inputs']
        for inp in self.inputs:
            sig_bytes = bytes(inp['sig'], 'utf-8')
            try:
                utxo = UTxO(inp['outpoint'], self.db)
            except BlockhainError:
                self.log.debug('UTxO not found for tx %s' % inp['outpoint']['txid'])
                self.valid = False
                return
            try:
                utxo.pubkey.verify(sig_bytes + bytes(canonicalize(tx).hex(), 'utf-8'), encoder=HexEncoder)
            except nacl_exceptions.BadSignatureError:
                raise BlockhainError('Invalid signature for tx %s, UTxO index %d' % (self.id, utxo.index))
            self.conservation -= utxo.value


class Block:
    log = logging.getLogger('Block')

    def __init__(self, obj, db):
        self.id = sha256(canonicalize(obj)).hexdigest()
        self.db = db

        self.valid = False


def parse_object(obj_dict, node, peer_id, coinbase=False):
    log = logging.getLogger('Parser')
    db = node.db

    obj_id = sha256(canonicalize(obj_dict)).hexdigest()
    if obj_dict['type'] == 'transaction':
        log.info('%s sent tx %s with id %s' % (peer_id, obj_dict, obj_id))
        try:
            obj = Transaction(obj_dict, db, coinbase)
        except KeyError:
            raise BlockhainError('Transaction %s is malformed' % obj_id)
    elif obj_dict['type'] == 'block':
        log.info('%s sent block %s with id %s' % (peer_id, obj_dict, obj_id))
        obj = Block(obj_dict, db)
        if obj_id == config.blockchain.GENESIS_ID:
            obj.valid = True
    else:
        raise BlockhainError('Unknown object type with id %s' % obj_id)

    if obj.valid and not db.get(obj_id):
        log.info('Adding object %s to db' % obj_id)
        db.set(obj_id, obj_dict)
        node.broadcast_object(obj_id)
