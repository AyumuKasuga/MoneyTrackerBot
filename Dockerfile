FROM alpine:latest

MAINTAINER AyumuKasuga

RUN apk add --no-cache python3 && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --upgrade pip setuptools && \
    rm -r /root/.cache

RUN mkdir /MoneyTracker

WORKDIR /MoneyTracker

COPY requirements.txt /MoneyTracker/

RUN pip3 install -r requirements.txt

COPY *.py /MoneyTracker/

CMD python3 -u bot.py
