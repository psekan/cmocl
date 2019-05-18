import gzip
import json
import logging
import os
import shutil
import sys
import requests
import hashlib


class Rapid7Error(Exception):
    """Connection failed, or returned an error."""
    pass


class Rapid7:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://us.api.insight.rapid7.com/opendata"
        self.data_url = self.base_url + "/studies/sonar.ssl/"
        self.quota_url = self.base_url + "/quota/"
        self.data_suffix = "_443_certs.gz"
        self.response_key = "sonarfile_set"

    @staticmethod
    def data_set_date(data_set_file: str) -> str:
        date_compact = data_set_file.replace("-", "")[0:8]
        return date_compact[0:4]+"-"+date_compact[4:6]+"-"+date_compact[6:8]

    def get_data_sets_list(self) -> dict:
        """Get list of all data sets

        :return: list of names of data sets
        :raise: Rapid7Error
        """
        response = requests.get(self.data_url, headers={"X-Api-Key": self.api_key})
        if response.ok:
            response_json = json.loads(response.content)

            if self.response_key in response_json:
                result = {}
                for file_name in response_json[self.response_key]:
                    if file_name.endswith(self.data_suffix):
                        result[self.data_set_date(file_name)] = file_name
                return result
            else:
                logging.error("Rapid7 API - get_data_sets: Unknown response.")
                logging.error(response.content)
                raise Rapid7Error("get_data_sets - Unknown response.")
        else:
            logging.error("Rapid7 API - get_data_sets: Request failed.")
            logging.error(response.content)
            raise Rapid7Error("get_data_sets - request failed")

    def get_quota_info(self):
        response = requests.get(self.quota_url, headers={"X-Api-Key": self.api_key})
        if response.ok:
            return json.loads(response.content)
        else:
            logging.error("Rapid7 API - get_quota_info: Request failed.")
            logging.error(response.content)
            raise Rapid7Error("get_quota_info - request failed")

    def get_data_info(self, data_name) -> dict:
        """Get info about a data set

        :param data_name:
        :return: dictionary with keys `size` and `fingerprint`
        :raise: Rapid7Error
        """
        response = requests.get(self.data_url + data_name + "/", headers={"X-Api-Key": self.api_key})
        if response.ok:
            return response.json()
        else:
            logging.error("Rapid7 API - get_data_info: Request failed.")
            logging.error(response.content)
            raise Rapid7Error("get_data_info - request failed")

    def download(self, data_name, out_path, info=None, show_progress=False):
        """Download

        :param data_name: Name of data sets
        :param out_path:  Path to a file, where should be dataset stored
        :param info:      Dictionary obtained by get_data_info with keys `size` and `fingerprint`
        :param show_progress: Show progress to stdout
        :raise: Rapid7Error
        """
        response = requests.get(self.data_url + data_name + "/download/", headers={"X-Api-Key": self.api_key})
        if response.ok:
            response_json = response.json()

            if "url" in response_json:
                url = response_json["url"]
                with requests.get(url, stream=True) as r:
                    total_length = int(r.headers.get('content-length'))
                    if info is not None and total_length != info["size"]:
                        logging.error("Rapid7 API - download: different size.")
                        logging.error("Expected: "+str(info["size"])+", Real: "+str(total_length))
                        raise Rapid7Error("download - downloading file does not have expected size")

                    if show_progress:
                        print("Downloading " + data_name + " ["+str(total_length)+" B]")
                        dl = 0

                    hash_calc = hashlib.sha1()
                    with open(out_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                hash_calc.update(chunk)

                                if show_progress:
                                    dl += len(chunk)
                                    done = int(50 * dl / total_length)
                                    sys.stdout.write("\r[%s%s]" % ('=' * done, ' ' * (50 - done)))
                                    sys.stdout.flush()
                    if show_progress:
                        sys.stdout.write("\n")

                    fingerprint = hash_calc.hexdigest()
                    if info is not None and fingerprint != info["fingerprint"]:
                        logging.error("Rapid7 API - download: different size.")
                        logging.error("Expected: "+str(info["size"])+", Real: "+str(total_length))
                        raise Rapid7Error("download - downloading file does not have expected size")
            else:
                logging.error("Rapid7 API - download: unknown response.")
                logging.error(response.content)
                raise Rapid7Error("download - unknown response")
        else:
            logging.error("Rapid7 API - download: Request failed.")
            logging.error(response.content)
            raise Rapid7Error("download - request failed")

    @staticmethod
    def decompress(file_in, file_out=None):
        """Decompress gz archive

        :param file_in:  Path to archive
        :param file_out: Where store the decompressed data
        :return:
        """
        if file_out is None:
            file_out = os.path.splitext(file_in)[0]
        with gzip.open(file_in, 'rb') as f_in:
            with open(file_out, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

    class Converter:
        @staticmethod
        def get_dn_part(subject, oid=None):
            if subject is None:
                return None
            if oid is None:
                raise ValueError('Disobey wont be tolerated')

            for sub in subject:
                if oid is not None and sub.oid == oid:
                    return sub.value

        @staticmethod
        def try_get_cname(certificate):
            from cryptography.x509.oid import NameOID
            try:
                return Rapid7.Converter.get_dn_part(certificate.subject, NameOID.COMMON_NAME)
            except ValueError:
                pass
            return None

        @staticmethod
        def convert(file_in, file_out):
            import base64
            from dataset import Key
            from cryptography.x509.base import load_der_x509_certificate
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

            results = {"rsa": 0, "all": 0, "errors": 0}
            with open(file_in) as fp:
                with open(file_out, "w") as fop:
                    for cnt, line in enumerate(fp):
                        results["all"] += 1
                        try:
                            cert64 = line.split(",")[1]
                            cert_bin = base64.b64decode(cert64)
                            cert = load_der_x509_certificate(cert_bin, default_backend())
                            pub = cert.public_key()

                            if isinstance(pub, RSAPublicKey):
                                not_before = cert.not_valid_before
                                cname = Rapid7.Converter.try_get_cname(cert)

                                pub_num = pub.public_numbers()
                                key = Key([cname, not_before.strftime('%Y-%m-%d')], pub_num.n, pub_num.e, 1)
                                fop.write(key.get_as_string() + "\n")
                                results["rsa"] += 1
                        except Exception as e:
                            results["errors"] += 1
                            logging.warning('Processing of dataset %s: %s, line %d' % (file_in, e, cnt))
            return results
