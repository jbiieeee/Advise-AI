#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt
pip install pyjwt cryptography requests
# Copy templates from parent frontend folder during build
# This ensures that Render (with Root Directory: django) can see them
cp -r ../frontend/templates ./templates_prod

python manage.py collectstatic --no-input
python manage.py migrate
python manage.py ensure_site
python manage.py seed_curriculum
