from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Airport, Flight


class Command(BaseCommand):
    help = (
        'Adds repeatable sample flights for November 2026 through January 2027 '
        'without deleting existing data.'
    )

    airport_data = {
        'KUL': {
            'name': 'Kuala Lumpur International Airport',
            'city': 'Kuala Lumpur',
            'country': 'Malaysia',
            'timezone': 'Asia/Kuala_Lumpur',
        },
        'SIN': {
            'name': 'Changi Airport',
            'city': 'Singapore',
            'country': 'Singapore',
            'timezone': 'Asia/Singapore',
        },
        'HND': {
            'name': 'Haneda Airport',
            'city': 'Tokyo',
            'country': 'Japan',
            'timezone': 'Asia/Tokyo',
        },
        'LHR': {
            'name': 'Heathrow Airport',
            'city': 'London',
            'country': 'United Kingdom',
            'timezone': 'Europe/London',
        },
        'JFK': {
            'name': 'John F. Kennedy International Airport',
            'city': 'New York',
            'country': 'USA',
            'timezone': 'America/New_York',
        },
    }

    routes = (
        ('KUL', 'SIN', time(8), timedelta(hours=1, minutes=30), 320),
        ('KUL', 'HND', time(9), timedelta(hours=7), 1850),
        ('SIN', 'LHR', time(13), timedelta(hours=13), 2400),
        ('SIN', 'JFK', time(16), timedelta(hours=18), 3400),
    )

    months = ((2026, 11), (2026, 12), (2027, 1))

    @transaction.atomic
    def handle(self, *args, **options):
        airports = {
            code: Airport.objects.get_or_create(
                code=code,
                defaults=defaults,
            )[0]
            for code, defaults in self.airport_data.items()
        }

        created_count = 0
        for year, month in self.months:
            departure_date = date(year, month, 15)
            for origin_code, destination_code, departure_time, duration, price in self.routes:
                origin = airports[origin_code]
                destination = airports[destination_code]
                local_departure = datetime.combine(
                    departure_date,
                    departure_time,
                    tzinfo=ZoneInfo(origin.timezone),
                )
                departure = local_departure.astimezone(ZoneInfo('UTC'))
                arrival = departure + duration
                callsign = f'PA{year % 100:02d}-{month:02d}-{origin_code}{destination_code}'

                _, created = Flight.objects.get_or_create(
                    callsign=callsign,
                    defaults={
                        'airline': 'Python Airlines',
                        'origin': origin,
                        'destination': destination,
                        'scheduled_departure_time': departure,
                        'estimated_departure_time': departure,
                        'scheduled_arrival_time': arrival,
                        'estimated_arrival_time': arrival,
                        'base_price': price,
                        'total_seats': 150,
                        'available_seats': 150,
                        'status': Flight.FlightStatus.EXPECTED,
                    },
                )
                created_count += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f'Created {created_count} future sample flight(s); '
                'existing airports and flights were left unchanged.'
            )
        )
