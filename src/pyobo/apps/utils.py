# -*- coding: utf-8 -*-

"""Utilities for web applications."""

from typing import NoReturn, Optional

from flask import Flask
from more_click import make_gunicorn_app

__all__ = [
    'run_app',
]


def run_app(app: Flask, host: str, port: str, with_gunicorn: bool, workers: Optional[int] = None) -> NoReturn:
    """Run the flask app, either with gunicorn or the werkzeug debugger server."""
    if with_gunicorn:
        gunicorn_app = make_gunicorn_app(app, host, port, workers)
        gunicorn_app.run()
    else:
        app.run(host=host, port=port)
