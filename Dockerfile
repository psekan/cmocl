FROM python:3

RUN apt update && apt install -y default-jre openjfx cron

RUN mkdir /app
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY *.jar ./
COPY classification-table.json ./
COPY cron-jobs /etc/cron.d/crob-jobs

RUN chmod -R 0777 /app
RUN chmod 0644 /etc/cron.d/crob-jobs
RUN crontab /etc/cron.d/crob-jobs

CMD ["cron", "-f"]
