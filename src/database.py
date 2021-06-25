import json
import logging

class PenguinDB:
    log = logging.getLogger('DB')

    def __init__(self, location):
        self.location = location
        try:
            self.db = json.loads(open(location).read())
        except FileNotFoundError:
            self.db = {'peers': []}
            self.dumpdb()

    def dumpdb(self):
        open(self.location, 'w').write(json.dumps(self.db))

    def set(self, key, value):
        self.db[str(key)] = value
        self.dumpdb()
        return True

    def get(self, key):
        try:
            return self.db[str(key)]
        except KeyError:
            self.log.error('No key %s found in db' % str(key))
            return False

    def delete(self, key):
        if key not in self.db.keys():
            return False
        del self.db[key]
        self.dumpdb()
        return True
