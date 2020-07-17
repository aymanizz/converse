FROM python:3.7-alpine

WORKDIR /usr/src/app

COPY requirements.txt .
RUN pip install -rrequirements.txt

COPY . .

CMD python -m converse
