'''
Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance with
the License. A copy of the License is located at
    http://aws.amazon.com/apache2.0/
or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and
limitations under the License.
'''

import logging
import os
import json
import requests
import boto3
import aws_secrets
from requests import HTTPError, ConnectionError, RequestException

log_level = os.environ['LOG_LEVEL'].upper()
logging.getLogger().setLevel(getattr(logging, log_level))


def handler(event, context):
    logging.info(f"************ BEGIN NewRelicDataSync ************")
    logging.debug(context)

    event_type = os.environ['NEW_RELIC_APP_NAME']
    logging.debug(f"NEWRELIC EVENT_TYPE: {event_type}")

    events = []
    total_records = len(event['Records'])
    logging.info(f"RECEIVED MESSAGE(S): {total_records}")

    if total_records == 0:
        logging.warning(
            f"STREAM DOES NOT CONTAIN RECORD(S). EMPTY LAMBDA INVOCATION!")
        return

    # try to pull the accounts friendly names from AWS Organizations API
    accounts = get_accounts_info()

    for record in event['Records']:
        logging.debug(record)

        # only process new records added to DynamoDB table
        if record['eventName'] == 'INSERT':

            data = record['dynamodb']['NewImage']
            # parse the record
            message_id = get_value(data, 'MessageId')
            limit_name = get_value(data, 'LimitName')
            service = get_value(data, 'Service')
            region = get_value(data, 'Region')
            limit_amount = get_value(data, 'LimitAmount')
            current_usage = get_value(data, 'CurrentUsage')
            account_id = get_value(data, 'AccountId')
            status = get_value(data, 'Status')

            event = {
                "eventType": event_type,
                "message_id": message_id,
                "account_id": account_id,
                "account_name": accounts[account_id] if account_id in accounts else "UNKNOWN",
                "current_usage": current_usage,
                "limit_amount": limit_amount,
                "limit_name": limit_name,
                "region": region,
                "service": service,
                "status": status
            }

            events.append(event)

    logging.info(f"PROCESSED MESSAGE(S): {len(events)}")
    if len(events) == 0:
        logging.info(f"Nothing to report to NewRelic")
        logging.info(f"************ END NewRelicDataSync ************")
        return

    logging.info(f"Getting NewRelic API Keys from Secret Manager")
    secret_name = os.environ['AWS_SECRETS_KEY_NAME']
    logging.debug(f"SECRET NAME: {secret_name}")

    secret_region = os.environ['AWS_SECRET_REGION']
    logging.debug(f"AWS REGION: {secret_region}")

    newrelic_key = aws_secrets.get_secret_key(
        secret_name, secret_region, "NEWRELIC-KEY")
    logging.debug(f"NEWRELIC KEY: {newrelic_key[:6]}...")

    headers = {
        'Content-Type': 'application/json',
        'X-Insert-Key': newrelic_key
    }

    logging.info(f"Sending request to NewRelic Event API")
    # https://docs.newrelic.com/docs/telemetry-data-platform/ingest-manage-data/ingest-apis/use-event-api-report-custom-events

    endpoint = os.environ['NEW_RELIC_API_ENDPOINT']
    logging.debug(f"NEWRELIC ENDPOINT: {endpoint}")

    logging.debug(f"DATA: {json.dumps(events)}")
    logging.info(f"DATA COUNT: {len(events)}")

    response = send_events(endpoint, headers, events)
    logging.info(f"MESSAGE: {response}")

    logging.info(f"************ END NewRelicDataSync ************")


def get_value(data, key: str, type_c: str = "S") -> str:
    if key in data:
        obj = data[key]
        if type_c in obj:
            return obj[type_c]
        else:
            return None
    else:
        return None


def send_events(endpoint: str, headers: object, data) -> object:
    try:
        response = requests.post(
            endpoint, headers=headers, data=json.dumps(data))
        logging.info(f"RESPONSE: {response}")

        if response:
            return response.json()

    except HTTPError as e:
        logging.error(e)
        raise e

    except ConnectionError as e:
        logging.error(e)
        raise e

    except RequestException as e:
        logging.error(e)
        raise e


def get_accounts_info() -> object:
    """ Get Accounts information from AWS Organizations """

    # check if account is part of organization, if it is part of organization, pull the accounts friendly name and pass it to NewRelic
    logging.info(f"Checking for AWS Organization accounts...")
    org = boto3.client('organizations')
    kwargs = {}
    accounts = {}

    while True:
        try:
            accounts_page = org.list_accounts(**kwargs)
            logging.debug(f"Accounts: {accounts_page}")
        except Exception as e:
            logging.error(e)
            break

        for account in accounts_page['Accounts']:
            key = account['Id']
            value = account['Name']
            logging.debug(f"Account ({key}) = {value}")
            accounts[key] = value

        if 'NextToken' in accounts_page:
            kwargs['NextToken'] = accounts_page['NextToken']
        else:
            break

    return accounts
