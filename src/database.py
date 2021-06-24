import json

class PenguinDB:
    def __init__(self, location):
        self.location = location
        try:
            self.db = json.loads(open(location).read())
        except FileNotFoundError:
            self.db = {}
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
            print('[!] No key found in db', str(key))
            return False

    def delete(self, key):
        if key not in self.db.keys():
            return False
        del self.db[key]
        self.dumpdb()
        return True
