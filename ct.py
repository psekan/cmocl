import json
import logging
import subprocess
from json import JSONDecodeError
from os import listdir
from os.path import isfile, join

from datetime import date


class CertificateTransparency:

    def __init__(self, url, downloader_path, classifier_path):
        self.url = url
        self.downloader_path = downloader_path
        self.classifier_path = classifier_path

    @staticmethod
    def process_temporary(storage_temporary, storage_days):
        opened_fp = {}
        for f in listdir(storage_temporary):
            path = join(storage_temporary, f)
            if isfile(path):
                with open(path) as fp:
                    lines = 0
                    while True:
                        try:
                            line = fp.readline()
                            if not line:
                                break
                            js = json.loads(line)
                            if "timestamp" not in js:
                                logging.warning(
                                    "File " + path + " does not contains timestamp attribute in keys. Skipping.")
                                break
                            dt_object = date.fromtimestamp(int(js["timestamp"] / 1000))
                            d = dt_object.strftime('%Y-%m-%d')
                            if d not in opened_fp:
                                try:
                                    opened_fp[d] = open(join(storage_days, d + ".json"), "a")
                                except IOError as e:
                                    logging.error("Cannot open file " + path + ": " + e.msg)
                            if d in opened_fp:
                                opened_fp[d].write(line)
                                lines += 1
                        except UnicodeDecodeError as e:
                            logging.error("Error with decoding line: " + e.reason)
                        except JSONDecodeError as e:
                            logging.error("Error with decoding line: " + e.msg)
                    print("Processed " + str(lines) + " lines")
        for d in opened_fp:
            opened_fp[d].close()

    def download(self, index_from, index_to, out_path):
        ret = subprocess.run(["java", "-jar", self.downloader_path,
                              "download", self.url, out_path,
                              str(index_from), str(index_to)],
                             stdout=subprocess.DEVNULL)
        return ret.returncode

    def get_log_size(self):
        proc = subprocess.run(["java", "-jar", self.downloader_path,
                               "state", self.url],
                              stdout=subprocess.PIPE)
        if proc.stdout[0:16] != b'Current treeSize':
            return None
        return int(proc.stdout[18:])
