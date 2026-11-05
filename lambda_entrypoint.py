import json
import os

import boto3


def load_secrets():
    database_secret_arn = os.environ.get('DB_SECRET_ARN')
    django_secret_arn = os.environ.get('DJANGO_SECRET_ARN')
    if not database_secret_arn or not django_secret_arn:
        raise RuntimeError(
            'DB_SECRET_ARN and DJANGO_SECRET_ARN must be configured for Lambda.'
        )

    client = boto3.client('secretsmanager')
    database_secret = json.loads(
        client.get_secret_value(SecretId=database_secret_arn)['SecretString']
    )
    os.environ['DB_USER'] = database_secret['username']
    os.environ['DB_PASSWORD'] = database_secret['password']
    os.environ['DJANGO_SECRET_KEY'] = client.get_secret_value(
        SecretId=django_secret_arn
    )['SecretString']


def main():
    load_secrets()
    os.execvp(
        'gunicorn',
        [
            'gunicorn',
            'airline_reservation_system.wsgi:application',
            '--bind',
            '0.0.0.0:8000',
            '--workers',
            '1',
            '--threads',
            '2',
            '--timeout',
            '120',
        ],
    )


if __name__ == '__main__':
    main()
