# -*- coding: utf-8 -*-

"""Utilities for the CLI."""

import logging

import click

__all__ = [
    'verbose_option',
]

logger = logging.getLogger(__name__)


def _debug_callback(_ctx, _param, value):
    if not value:
        logging.basicConfig(level=logging.WARNING)
    elif value == 1:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.DEBUG)
    logger.debug('debugging enabled')


verbose_option = click.option(
    '-v', '--verbose',
    count=True,
    callback=_debug_callback,
    expose_value=False,
)
