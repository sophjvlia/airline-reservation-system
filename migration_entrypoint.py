import os
from lambda_entrypoint import load_secrets
import django


def handler(event, context):
    load_secrets()
    os.environ.setdefault(
        'DJANGO_SETTINGS_MODULE',
        'airline_reservation_system.settings',
    )
    django.setup()
    from django.core.management import call_command

    call_command('migrate', interactive=False)
    return {'status': 'migrations applied'}
