import json
import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from getpass import getpass


class Configuration:
    CONFIGURATION_PATH = "configuration.json"
    CONF_RAPID7_API_KEY = "rapid7-api-key"
    CONF_CMOCL_API_URL = "cmocl-api-url"
    CONF_CMOCL_API_KEY = "cmocl-api-key"
    CONF_STORAGE_PATH = "storage-path"

    CONF_SMTP_HOST = "smtp-host"
    CONF_SMTP_PORT = "smtp-port"
    CONF_SMTP_USER = "smtp-user"
    CONF_SMTP_PASS = "smtp-pass"
    CONF_SMTP_FROM = "smtp-from"
    CONF_SMTP_TO = "smtp-to"

    CONF_CT_LOG_URL = "ct-log-url"
    CONF_CT_LAST_ENTRY = "ct-last-entry"
    
    def __init__(self):
        self.CONF_path = self.CONFIGURATION_PATH
        self.conf = self.load_configuration()

    def configuration_exists(self):
        return os.path.exists(self.CONF_path)

    def load_configuration(self):
        if self.configuration_exists():
            with open(self.CONF_path) as json_file:
                return json.load(json_file)
        raise Exception("Cannot load configuration.")

    def save_configuration(self):
        with open(self.CONF_path, "w") as json_file:
            return json.dump(self.conf, json_file)

    def get(self, key):
        if key in self.conf:
            return self.conf[key]
        raise Exception("Cannot load configuration key "+key+".")
    
    def exists(self, key):
        if key in self.conf:
            return True
        return False

    def update_ct_last_download_entry(self, entry):
        self.conf[self.CONF_CT_LAST_ENTRY] = entry
        self.save_configuration()

    def get_ct_last_download_entry(self):
        if self.CONF_CT_LAST_ENTRY in self.conf:
            return self.conf[self.CONF_CT_LAST_ENTRY]
        return 0

    def send_mail(self, email_text):
        if self.conf[self.CONF_SMTP_HOST]:
            try:
                with smtplib.SMTP_SSL(self.conf[self.CONF_SMTP_HOST], self.conf[self.CONF_SMTP_PORT]) as server:
                    server.login(self.conf[self.CONF_SMTP_USER], self.conf[self.CONF_SMTP_PASS])

                    message = MIMEMultipart("alternative")
                    message["Subject"] = "CMoCL Notification"
                    message["From"] = self.conf[self.CONF_SMTP_FROM]
                    message["To"] = self.conf[self.CONF_SMTP_TO]

                    message.attach(MIMEText(email_text, "plain"))
                    server.sendmail(self.conf[self.CONF_SMTP_FROM], self.conf[self.CONF_SMTP_TO], message.as_string())
            except ssl.SSLError as ssl_error:
                logging.error("Cannot send a notification thought smtp: ")
                logging.error(str(ssl_error))

    def prepare_and_send_mail(self, message):
        stdout_string = message.getvalue()
        if len(stdout_string) > 0:
            email_text = "CMoCL Notification: \n------\n"
            email_text += stdout_string + "\n------\n"
            self.send_mail(email_text)

    @staticmethod
    def configure():
        print("CONFIGURATION:")
        storage = input("Storage path: ")
        print("Rapid7")
        rapid7_key = getpass("  API key: ")
        print("Certificate Transparency")
        ct_url = input("  Log API url: ")
        print("CMoCL")
        cmocl_url = input("  API url: ")
        cmocl_key = getpass("  API key: ")
        print("SMTP (leave empty for not using notifications)")
        smtp_host = input("  Server: ")

        conf = {
            Configuration.CONF_RAPID7_API_KEY: rapid7_key,
            Configuration.CONF_CT_LOG_URL: ct_url,
            Configuration.CONF_CMOCL_API_URL: cmocl_url,
            Configuration.CONF_CMOCL_API_KEY: cmocl_key,
            Configuration.CONF_STORAGE_PATH: storage,
            Configuration.CONF_SMTP_HOST: smtp_host
        }
        if smtp_host != "":
            smtp_port = int(input("  Port: "))
            smtp_username = input("  Username: ")
            smtp_password = getpass("  Password: ")
            smtp_from = input("  Email from: ")
            smtp_to = input("  Email to: ")
            conf[Configuration.CONF_SMTP_PORT] = smtp_port
            conf[Configuration.CONF_SMTP_USER] = smtp_username
            conf[Configuration.CONF_SMTP_PASS] = smtp_password
            conf[Configuration.CONF_SMTP_FROM] = smtp_from
            conf[Configuration.CONF_SMTP_TO] = smtp_to
        with open(Configuration.CONFIGURATION_PATH, 'w') as outfile:
            json.dump(conf, outfile)
