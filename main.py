import os
import sys
import logging
import subprocess
from io import StringIO
from os import listdir
from os.path import join

from datetime import date

from cmocl import CMoCL, CMoCLError
from configuration import Configuration
from dataset import Dataset
from rapid7 import Rapid7
from ct import CertificateTransparency

CMOCL_RAPID7_SOURCE = "rapid7"
CMOCL_RAPID7_PERIOD = CMoCL.PERIOD_OCCASIONAL

CMOCL_CT_SOURCE = "ct"
CMOCL_CT_PERIOD = CMoCL.PERIOD_DAY

# Load configuration
try:
    conf = Configuration()
except Exception as e:
    logging.error("Application is not properly configured.")
    logging.error(str(e))
    sys.exit(1)

# Use notification
redirect_output_to_mail = False
for i in range(1, len(sys.argv)):
    if sys.argv[i] == "-n":
        redirect_output_to_mail = True
    else:
        print("Unknown argument '"+sys.argv[i]+"'")

# Redirect output for capturing
old_stdout = sys.stdout
old_stderr = sys.stderr
stdout_buffer = StringIO()
if redirect_output_to_mail:
    sys.stdout = stdout_buffer
    sys.stderr = stdout_buffer

# Prepare CMoCL submodule
cmocl = None
try:
    cmocl = CMoCL(conf.get(conf.CONF_CMOCL_API_URL), conf.get(conf.CONF_CMOCL_API_KEY))
except Exception as e:
    logging.error("Cannot.")
    logging.error(str(e))
if cmocl is None:
    sys.stdout = old_stdout
    sys.stderr = old_stderr
    if redirect_output_to_mail:
        conf.prepare_and_send_mail(stdout_buffer)
    sys.exit(2)


# Prepare storage for results
storage_path = "storage"
if conf.exists(conf.CONF_STORAGE_PATH):
    conf.get(conf.CONF_STORAGE_PATH)
if not os.path.exists(storage_path):
    os.makedirs(storage_path)

# Rapid7
try:
    # Temporary data folder
    temporary_path = "temp-rapid7"
    if not os.path.exists(temporary_path):
        os.makedirs(temporary_path)

    # Load Rapid7 API
    rapid7 = Rapid7(conf.get(conf.CONF_RAPID7_API_KEY))
    rapid7_quotas = rapid7.get_quota_info()
    if "quota_left" not in rapid7_quotas:
        logging.error("An unexpected response from Rapid7 quota endpoint.")
        rapid7 = None
    elif rapid7_quotas["quota_left"] <= 0:
        logging.error("Your Rapid7 quota is currently exhausted.")
        rapid7 = None

    # Process Rapid7 dataset
    if rapid7 is not None:
        # Get list of 5 oldest not processed Rapid7 data sets
        data_sets = rapid7.get_data_sets_list()
        to_process = {}
        for _date in reversed(list(data_sets)):
            if not cmocl.exists(CMOCL_RAPID7_SOURCE, CMOCL_RAPID7_PERIOD, _date):
                to_process[_date] = data_sets[_date]
            if len(to_process) >= min(rapid7_quotas["quota_left"], 5):
                break

        # Process Rapid7 data sets
        for _date in to_process:
            print("Rapid7 " + _date)
            out_path = storage_path + "/rapid7-" + _date + "/prior_probability.json"
            tmp_path = temporary_path + "/rapid7-" + _date
            if not os.path.exists(out_path):
                if not os.path.exists(tmp_path):
                    try:
                        info = rapid7.get_data_info(to_process[_date])
                        print("Downloading")
                        rapid7.download(to_process[_date], tmp_path + ".gz", info)
                        print("Decompressing")
                        rapid7.decompress(tmp_path + ".gz", tmp_path + ".txt")
                        os.remove(tmp_path + ".gz")
                        print("Converting")
                        rapid7.Converter.convert(tmp_path + ".txt", tmp_path + ".json")
                        os.remove(tmp_path + ".txt")
                        print("Removing duplicities")
                        Dataset.remove_duplicities(tmp_path + ".json", tmp_path)
                        os.remove(tmp_path + ".json")
                    except Exception as e:
                        if os.path.exists(tmp_path + ".gz"):
                            os.remove(tmp_path + ".gz")
                        if os.path.exists(tmp_path + ".txt"):
                            os.remove(tmp_path + ".txt")
                        if os.path.exists(tmp_path + ".json"):
                            os.remove(tmp_path + ".json")
                        logging.error("An error occurs during downloading " + _date + ": ")
                        logging.error(str(e))
                        continue
                print("Statistics: ")
                with open(tmp_path) as fp:
                    stats = Dataset.statistics(fp)
                    print("  Unique keys: " + str(stats["keys"]))
                    print("  Duplicities: " + str(stats["duplicities"]))
                try:
                    print("Estimation prior probability")
                    subprocess.run(["java", "-jar", "classify_rsa_key.jar",
                                    "-c", "-t", "classification-table.json",
                                    "-i", tmp_path, "-o", storage_path,
                                    "-p", "estimate", "-b", "none", "-e", "none"],
                                   stdout=subprocess.DEVNULL)
                except Exception as e:
                    logging.error("A critical error occurs during classification, Rapid7 " + _date + ": ")
                    logging.error(str(e))
                    continue
                os.remove(tmp_path)
            try:
                print("Uploading results to CMoCL Database")
                res = cmocl.upload(CMOCL_RAPID7_SOURCE, CMOCL_RAPID7_PERIOD, _date, out_path)
                if not res:
                    logging.error("Cannot upload results to CMoCL, Rapid7 " + _date + ".")
                else:
                    print("Rapid7 " + _date + " successfully processed.\n")
            except CMoCLError as e:
                logging.error("A critical error occurs during communication with CMoCL, Rapid7 " + _date + ": ")
                logging.error(str(e))
                sys.exit(1)
except Exception as e:
    logging.error("A critical error occurs in Rapid7 process: ")
    logging.error(str(e))

# CT log
try:
    # Temporary data folder
    temporary_path = "temp-ct"
    if not os.path.exists(temporary_path):
        os.makedirs(temporary_path)
    ct_days_path = "temp-ct-days"
    if not os.path.exists(ct_days_path):
        os.makedirs(ct_days_path)
    ct_days_unique_path = "temp-ct-days-unique"
    if not os.path.exists(ct_days_unique_path):
        os.makedirs(ct_days_unique_path)

    today = date.today()
    ct_last_entry = conf.get_ct_last_download_entry()
    ct_client = CertificateTransparency(conf.get(conf.CONF_CT_LOG_URL),
                                        "ctlog.jar", "classify_rsa_key.jar")
    ct_entries = ct_client.get_log_size()

    # Download new certificates
    print("Certificate Transparency monitor")
    print("Downloading "+str(ct_entries-ct_last_entry)+" entries from CT")
    temp_path = join(temporary_path, str(ct_last_entry)+"-"+str(ct_entries)+".json")
    ret = ct_client.download(ct_last_entry, ct_entries, temp_path)
    if ret != 0:
        os.remove(temp_path)
        raise Exception("Downloading exits with an error.")

    # Process to dates
    print("Processing to dates files")
    CertificateTransparency.process_temporary(temporary_path, ct_days_path)
    conf.update_ct_last_download_entry(ct_entries)
    os.remove(temp_path)

    # Process all past days
    for f in listdir(ct_days_path):
        path = join(ct_days_path, f)
        unique_path = join(ct_days_unique_path, "ct-"+f)
        d = date(int(f[0:4]), int(f[5:7]), int(f[8:10]))
        if cmocl.exists(CMOCL_CT_SOURCE, CMOCL_CT_PERIOD, d.isoformat()):
            logging.error("CT "+f+" is already in CMoCL")
            os.remove(path)
            continue
        try:
            if d >= today:
                continue
            print("Processing "+f)
            print("Removing duplicities "+f)
            Dataset.remove_duplicities(path, unique_path)

            print("Statistics: ")
            with open(unique_path) as fp:
                stats = Dataset.statistics(fp)
                print("  Unique keys: " + str(stats["keys"]))
                print("  Duplicities: " + str(stats["duplicities"]))

            out_path = storage_path + "/ct-" + f + "/prior_probability.json"
            try:
                print("Estimation prior probability")
                subprocess.run(["java", "-jar", "classify_rsa_key.jar",
                                "-c", "-t", "classification-table.json",
                                "-i", unique_path, "-o", storage_path,
                                "-p", "estimate", "-b", "none", "-e", "none"],
                               stderr=subprocess.PIPE)
            except Exception as e:
                logging.error("A critical error occurs during classification, CT " + d.isoformat() + ": ")
                logging.error(str(e))
                os.remove(unique_path)
                continue
            try:
                print("Uploading results to CMoCL Database")
                res = cmocl.upload(CMOCL_CT_SOURCE, CMOCL_CT_PERIOD, d.isoformat(), out_path)
                if not res:
                    logging.error("Cannot upload results to CMoCL, Rapid7 " + d.isoformat() + ".")
                else:
                    print("CT " + d.isoformat() + " successfully processed.\n")
                    os.remove(path)
            except CMoCLError as e:
                logging.error("A critical error occurs during communication with CMoCL, CT " + d.isoformat() + ": ")
                logging.error(str(e))
                os.remove(unique_path)
                sys.exit(1)
        except (OSError, OverflowError) as e:
            logging.error("Wrong format of file name "+f+".")
            logging.error(str(e))
        except Exception as e:
            logging.error("An error occurs during processing CT " + f + ": ")
            logging.error(str(e))
        if os.path.exists(unique_path):
            os.remove(unique_path)
except Exception as e:
    logging.error("A critical error occurs in CT process: ")
    logging.error(str(e))

# Send stdout and stderr
sys.stdout = old_stdout
sys.stderr = old_stderr
if redirect_output_to_mail:
    conf.prepare_and_send_mail(stdout_buffer)
