# -*- coding: utf-8 -*-

"""Utilities for web applications."""

from typing import NoReturn, Optional

import click
from flask import Flask

__all__ = [
    'run_app',
    'host_option',
    'port_option',
    'gunicorn_option',
]

host_option = click.option('--host', type=str, help='host on which the app is run')
port_option = click.option('--port', type=int, help='port on which the app is served')
gunicorn_option = click.option(
    '--gunicorn',
    is_flag=True,
    help='Run the web application using gunicorn',
)


def run_app(app: Flask, host: str, port: int, gunicorn: bool, workers: Optional[int] = None) -> NoReturn:
    """Run the flask app, either with gunicorn or the werkzeug debugger server."""
    if gunicorn:
        run_with_gunicorn(app=app, host=host, port=port, workers=workers)
    else:
        app.run(port=port, host=host)


def run_with_gunicorn(app: Flask, host: str, port: int, workers: Optional[int] = None) -> NoReturn:
    """Run a flask app with Gunicorn."""
    gunicorn_app = make_gunicorn_app(app=app, host=host, port=port, workers=workers)
    gunicorn_app.run()


def make_gunicorn_app(app: Flask, host: str, port: int, workers: Optional[int] = None):
    """Make a GUnicorn App.

    :rtype: gunicorn.app.base.BaseApplication
    """
    if not host:
        raise ValueError('Must specify host')
    if not port:
        raise ValueError('Must specify port')

    import gunicorn.app.base

    class StandaloneApplication(gunicorn.app.base.BaseApplication):
        def __init__(self, options=None):
            self.options = options or {}
            self.application = app
            super().__init__()

        def load_config(self):
            for key, value in self.options.items():
                if key in self.cfg.settings and value is not None:
                    self.cfg.set(key.lower(), value)

        def load(self):
            return self.application

    config = {
        'bind': f'{host}:{port}',
    }
    if workers is not None:
        config['workers'] = workers

    return StandaloneApplication(config)
