# base image
FROM python:3.8-alpine

RUN apk update && apk add postgresql-dev gcc python3-dev musl-dev libffi-dev

WORKDIR /usr/src/app
COPY . /usr/src/app/
RUN pip3 install .

RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
