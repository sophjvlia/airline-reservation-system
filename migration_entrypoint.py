import os
from lambda_entrypoint import load_secrets
import django


def handler(event, context):
    action = event.get('action', 'migrate') if isinstance(event, dict) else None
    actions = {'migrate', 'seed_future_flights'}
    if action not in actions:
        raise ValueError(f'Unsupported migration Lambda action: {action!r}')

    load_secrets()
    os.environ.setdefault(
        'DJANGO_SETTINGS_MODULE',
        'airline_reservation_system.settings',
    )
    django.setup()
    from django.core.management import call_command

    if action == 'migrate':
        call_command('migrate', interactive=False)
        return {'status': 'migrations applied'}

    call_command('seed_future_flights')
    return {'status': 'future flights seeded'}
