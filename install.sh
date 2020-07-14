#!/usr/bin/env bash

rm -rf .venv
virtualenv -p python3 venv
source venv/bin/activate
pip install -r requirements.txt
