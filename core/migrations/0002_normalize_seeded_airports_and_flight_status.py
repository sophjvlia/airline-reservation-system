from django.db import migrations


AIRPORT_TIMEZONES = {
    'KUL': 'Asia/Kuala_Lumpur',
    'SIN': 'Asia/Singapore',
    'HND': 'Asia/Tokyo',
    'LHR': 'Europe/London',
    'JFK': 'America/New_York',
}


def normalize_seed_data(apps, schema_editor):
    Airport = apps.get_model('core', 'Airport')
    Flight = apps.get_model('core', 'Flight')

    for code, timezone_name in AIRPORT_TIMEZONES.items():
        Airport.objects.filter(code=code).update(timezone=timezone_name)

    Flight.objects.filter(status='ON_TIME').update(status='EXPECTED')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(normalize_seed_data, migrations.RunPython.noop),
    ]
