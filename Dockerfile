FROM python:3.8
ADD . /app
WORKDIR /app
USER root

ARG PYOBO_SQLALCHEMY_URI
ENV PYOBO_SQLALCHEMY_URI=${PYOBO_SQLALCHEMY_URI}

RUN python -m pip install --upgrade pip
RUN python -m pip install .

# The following command loads all of the data into the database at ``PYOBO_SQLALCHEMY_URI``
RUN python -m pyobo.database.sql.loader -v

ENTRYPOINT python -m pyobo.apps.resolver --port 80 --host "0.0.0.0" --gunicorn --sql
