import collections
import json
from hashlib import sha224
from json import JSONDecodeError


class Key:
    def __init__(self, source, n, e, count=1):
        self.source = source
        self.n = n
        self.e = e
        self.count = count

    def get_as_string(self):
        js = collections.OrderedDict()
        js['source'] = self.source
        js['n'] = '0x%x' % self.n
        js['e'] = '0x%x' % self.e
        js['count'] = self.count
        return json.dumps(js)

    @staticmethod
    def parse_from_string(string):
        js = json.loads(string)
        return Key(js['source'], int(js['n'], 16), int(js['e'], 16), js['count'])

    def fingerprint(self):
        return sha224(str(self.n).encode('ASCII')+str(self.e).encode('ASCII')).hexdigest()[:16]


class Dataset:
    def __init__(self, path=None):
        if path is None:
            self.keys = []
        else:
            self.load_from_file(path)

    def load_from_file(self, path):
        self.keys = []
        with open(path) as fp:
            for k in self.file_keys(fp):
                self.keys.append(k)

    @staticmethod
    def file_keys(fp):
        while True:
            try:
                line = fp.readline()
                if not line:
                    break
                yield Key.parse_from_string(line)
            except UnicodeDecodeError as e:
                print("Error with decoding line: "+e.reason)
            except JSONDecodeError as e:
                print("Error with decoding line: " + e.msg)

    @staticmethod
    def compute_counts(fp):
        hashes = {}
        for k in Dataset.file_keys(fp):
            fingerprint = k.fingerprint()
            if fingerprint in hashes:
                hashes[fingerprint] += 1
            else:
                hashes[fingerprint] = 1
        return hashes

    @staticmethod
    def statistics(fp):
        stats = {
            "keys": 0,
            "duplicities": 0,
            "exponents": {}
        }
        for k in Dataset.file_keys(fp):
            stats["keys"] += 1
            stats["duplicities"] += (k.count - 1)
            e = str(k.e)
            if e not in stats["exponents"]:
                stats["exponents"][e] = 0
            stats["exponents"][e] += 1
        return stats

    @staticmethod
    def remove_duplicities(file_in, file_out):
        with open(file_in) as fp:
            hashes = Dataset.compute_counts(fp)

        duplicities = {}
        with open(file_out, "w") as fop:
            with open(file_in) as fp:
                for k in Dataset.file_keys(fp):
                    fingerprint = k.fingerprint()

                    # If there left only one key
                    if hashes[fingerprint] == 1:
                        # If it had a duplicities, compute new key with all sources and counts
                        if fingerprint in duplicities:
                            sources = list(dict.fromkeys(duplicities[fingerprint]["sources"]+k.source))
                            k = Key(sources, k.n, k.e, duplicities[fingerprint]["count"])
                            duplicities.pop(fingerprint)
                        fop.write(k.get_as_string() + "\n")
                        hashes.pop(fingerprint)
                    else:
                        # If we found this key first time, save number of counts we expect
                        if fingerprint not in duplicities:
                            duplicities[fingerprint] = {"sources": [], "count": hashes[fingerprint]}
                        sources = list(dict.fromkeys(duplicities[fingerprint]["sources"] + k.source))
                        duplicities[fingerprint]["sources"] = sources
                        hashes[fingerprint] -= 1
