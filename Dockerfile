FROM ubuntu:16.10

MAINTAINER AyumuKasuga

RUN locale-gen en_US.UTF-8

ENV LANG en_US.UTF-8
ENV LC_CTYPE en_US.UTF-8
ENV LC_ALL en_US.UTF-8

ENV TZ=Europe/Moscow

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt-get update && apt-get upgrade -y && apt-get install python3 python3-venv -y

RUN mkdir /MoneyTracker

WORKDIR /MoneyTracker

COPY requirements.txt /MoneyTracker/

RUN /usr/bin/python3 -m venv /MoneyTracker/.venv
RUN chmod +x /MoneyTracker/.venv/bin/activate
RUN cd /MoneyTracker && /MoneyTracker/.venv/bin/pip install pip --upgrade && /MoneyTracker/.venv/bin/pip install -r requirements.txt

COPY *.py /MoneyTracker/

CMD /MoneyTracker/.venv/bin/python -u bot.py