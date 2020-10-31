#!/bin/bash 

# move to customization directory to install python packages
poetry config virtualenvs.in-project true --local
poetry config --list

poetry env use 3.8
poetry install --no-dev 

ls -la

# delete `dist` directory
rm -rf dist/ && mkdir dist

# since zip works in the base-directory, so we have to navigate to the packages directory
cd ./.venv/lib/python3.8/site-packages/

# zip everything under site-packages / Thats where poetry install all dependencies
zip -r ../../../../dist/newrelic-datasync-service.zip *

# move back to customization folder
cd ../../../../

# add lambda handler and utility functions to zip archive
zip -r ./dist/newrelic-datasync-service.zip index.py aws_secrets.py
