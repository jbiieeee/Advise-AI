#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt
pip install pyjwt cryptography requests

python manage.py collectstatic --no-input
python manage.py migrate
python manage.py ensure_site
python manage.py seed_curriculum
