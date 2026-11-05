from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from core.models import Flight, Reservation


class Command(BaseCommand):
    help = 'Adds repeatable sample reservations without changing flight or airport data.'

    sample_bookings = (
        {
            'pnr': 'PYT234',
            'passenger_name': 'Alex Morgan',
            'passenger_email': 'alex@example.com',
            'passport_number': 'P1234567',
            'nationality': 'Malaysian',
        },
        {
            'pnr': 'PYT235',
            'passenger_name': 'Jamie Lee',
            'passenger_email': 'jamie@example.com',
            'passport_number': 'P7654321',
            'nationality': 'Singaporean',
        },
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            help='Associate sample bookings with this existing account.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        user = None
        username = options.get('username')
        if username:
            try:
                user = get_user_model().objects.get(username=username)
            except get_user_model().DoesNotExist as error:
                raise CommandError(f'No account found for username "{username}".') from error

        created_count = 0
        for sample in self.sample_bookings:
            if Reservation.objects.filter(pnr=sample['pnr']).exists():
                continue

            flight = Flight.objects.select_for_update().filter(
                estimated_departure_time__gt=timezone.now(),
                status__in=[Flight.FlightStatus.EXPECTED, Flight.FlightStatus.DELAYED],
                available_seats__gt=0,
            ).order_by('estimated_departure_time').first()
            if flight is None:
                raise CommandError(
                    'No future flights with available seats were found. Run seed_data first.'
                )

            booked_seats = set(
                Reservation.objects.filter(
                    flight=flight,
                    status=Reservation.ReservationStatus.CONFIRMED,
                ).values_list('seat_number', flat=True)
            )
            seat_number = next(
                (
                    f'{row}{column}'
                    for row in range(1, 11)
                    for column in 'ABCDEF'
                    if f'{row}{column}' not in booked_seats
                ),
                None,
            )
            if seat_number is None:
                raise CommandError(
                    f'No unoccupied seat could be assigned on flight {flight.callsign}.'
                )

            Reservation.objects.create(
                **sample,
                flight=flight,
                user=user,
                seat_number=seat_number,
                price_paid=flight.base_price,
                payment_status=Reservation.PaymentStatus.PAID,
                status=Reservation.ReservationStatus.CONFIRMED,
            )
            flight.available_seats -= 1
            flight.save(update_fields=['available_seats'])
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Created {created_count} sample reservation(s); existing samples were left unchanged.'
            )
        )
