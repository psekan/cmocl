import json
import logging
import requests


class CMoCLError(Exception):
    """An error occurs"""
    pass


class CMoCL:
    """Class for communication with CMoCL API"""

    PERIOD_DAY = "day"
    PERIOD_WEEK = "week"
    PERIOD_MONTH = "month"
    PERIOD_OCCASIONAL = "occasional"

    def __init__(self, url, api_key):
        self.url = url
        self.api_key = api_key

    def entries(self, source, period, date_from, date_to) -> list:
        response = requests.get(self.url+"/"+source+"/"+period+"/"+date_from+"/"+date_to)
        if response.ok:
            return response.json()
        elif response.status_code == 404:
            return []
        elif response.status_code == 400:
            try:
                content = response.json()
                message = content["message"]
                logging.warning("CMoCL GET - "+message)
            except ValueError:
                pass
            return []
        else:
            message = str(response.status_code)
            try:
                content = response.json()
                message = content["message"]
            except ValueError:
                logging.error("CMoCL GET - An error occurs.")
            raise CMoCLError("GET An error occurs: "+message)

    def dates(self, source, period) -> list:
        response = requests.get(self.url+"/"+source+"/"+period)
        if response.ok:
            return response.json()
        elif response.status_code == 404:
            return []
        elif response.status_code == 400:
            try:
                content = response.json()
                message = content["message"]
                logging.warning("CMoCL GET - "+message)
            except ValueError:
                pass
            return []
        else:
            message = str(response.status_code)
            try:
                content = response.json()
                message = content["message"]
            except ValueError:
                logging.error("CMoCL GET - An error occurs.")
            raise CMoCLError("GET An error occurs: "+message)

    def exists(self, source, period, date) -> bool:
        """Check if a record already exists in CMoCL database

        :param source:
        :param period:
        :param date:
        :return: True if a record exists, False otherwise
        """
        response = requests.get(self.url+"/"+source+"/"+period+"/"+date)
        if response.ok:
            return True
        elif response.status_code == 404:
            return False
        elif response.status_code == 400:
            try:
                content = response.json()
                message = content["message"]
                logging.warning("CMoCL GET - "+message)
            except ValueError:
                pass
            return False
        else:
            message = str(response.status_code)
            try:
                content = response.json()
                message = content["message"]
            except ValueError:
                logging.error("CMoCL GET - An error occurs.")
            raise CMoCLError("GET An error occurs: "+message)

    def upload(self, source, period, date, file_path) -> bool:
        """Upload estimation to

        :param source:
        :param period:
        :param date:
        :param file_path:
        :return:
        """
        with open(file_path) as fp:
            content = json.load(fp)
        request = {
            "source": source,
            "period": period,
            "date": date,
            "estimation": content
        }
        response = requests.post(self.url+"/", json=request, headers={"Authorization": "Bearer " + self.api_key})
        if response.ok:
            return True
        elif response.status_code == 400 or response.status_code == 403 or response.status_code == 409:
            if response.status_code == 400:
                head = "Incorrect format of estimation"
            elif response.status_code == 403:
                head = "Authorization error"
            else:
                head = "Already existed record"
            try:
                content = response.json()
                message = content["message"]
                logging.error("CMoCL POST - "+head+": " + message)
            except ValueError:
                logging.error("CMoCL POST - "+head+".")
            return False
        else:
            message = str(response.status_code)
            try:
                content = response.json()
                message = content["message"]
            except ValueError:
                logging.error("CMoCL POST - An error occurs.")
            raise CMoCLError("POST An error occurs: "+message)
