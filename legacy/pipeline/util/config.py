#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Legacy config. Secrets are read from the environment; see .env.example.

NOTE: the credentials that used to be hardcoded here were committed to a public
repo and must be treated as compromised. They have been revoked/rotated.
"""

import os

config = {
    'api_key':     os.environ.get('ALPHAVANTAGE_API_KEY', ''),
    'api_key2':    os.environ.get('ALPHAVANTAGE_API_KEY_2', ''),
    'secret':      os.environ.get('IEX_SECRET_KEY', ''),
    'symbol':      'AAPL',
    'kafka_broker': os.environ.get('KAFKA_BOOTSTRAP', 'localhost:9092'),
    # to transmit min data
    'topic_name1': 'stock_streaming1',
    # to transmit second data
    'topic_name2': 'stock_streaming2',
    'key_space':   'stocks',
}

path = './'
timeZone = 'US/Eastern'
