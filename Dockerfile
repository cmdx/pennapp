FROM python:latest

# for debugging
RUN apt-get update
RUN apt-get install -y iputils-tracepath curl vim

WORKDIR /app

COPY . /app/

RUN unzip -j data.zip

RUN pip install -r requirements.txt

EXPOSE 5000

RUN groupadd -r moberg
RUN useradd --no-log-init -r -g moberg moberg

RUN chown -R moberg:moberg /app

USER moberg

CMD [ "python", "demoServer.py" ]
