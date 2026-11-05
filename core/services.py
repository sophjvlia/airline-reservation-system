import random
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.db import transaction
from django.utils import timezone
from .models import Flight, Airport, Reservation

def search_itineraries(origin_code, destination_code, search_date):
    """
    Searches for direct flights and 1-stop connecting itineraries
    matching the origin, destination, and travel date.
    """
    results = []

    # Normalize search parameters
    origin_code = origin_code.upper()
    destination_code = destination_code.upper()

    if isinstance(search_date, str):
        search_date = datetime.strptime(search_date, "%Y-%m-%d").date()

    origin = Airport.objects.filter(code=origin_code).first()
    if origin is None:
        return []

    origin_timezone = ZoneInfo(origin.timezone)
    day_start = datetime.combine(search_date, time.min, tzinfo=origin_timezone)
    day_end = datetime.combine(search_date + timedelta(days=1), time.min, tzinfo=origin_timezone)
    now = timezone.now()
    searchable_statuses = [Flight.FlightStatus.EXPECTED, Flight.FlightStatus.DELAYED]

    # 1. Search Direct Flights
    direct_flights = Flight.objects.filter(
        origin=origin,
        destination__code=destination_code,
        scheduled_departure_time__gte=day_start,
        scheduled_departure_time__lt=day_end,
        estimated_departure_time__gte=now,
        status__in=searchable_statuses,
        available_seats__gt=0,
    )

    for flight in direct_flights:
        results.append({
            'type': 'DIRECT',
            'flights': [flight],
            'total_price': flight.base_price,
            'total_duration': flight.scheduled_arrival_time - flight.scheduled_departure_time
        })

    # 2. Search 1-Stop Connecting Flights
    # Find all first-leg flights leaving the origin on the search date
    first_legs = Flight.objects.filter(
        origin=origin,
        scheduled_departure_time__gte=day_start,
        scheduled_departure_time__lt=day_end,
        estimated_departure_time__gte=now,
        status__in=searchable_statuses,
        available_seats__gt=0,
    )

    for leg1 in first_legs:
        hub = leg1.destination

        # Don't loop back to destination as a stop if it's already direct
        if hub.code == destination_code:
            continue

        # Layover rules: Minimum 1 hour, Maximum 12 hours connection time
        min_connection = leg1.estimated_arrival_time + timedelta(hours=1)
        max_connection = leg1.estimated_arrival_time + timedelta(hours=12)

        second_legs = Flight.objects.filter(
            origin=hub,
            destination__code=destination_code,
            scheduled_departure_time__gte=min_connection,
            scheduled_departure_time__lte=max_connection,
            estimated_departure_time__gte=now,
            status__in=searchable_statuses,
            available_seats__gt=0,
        )

        for leg2 in second_legs:
            total_price = leg1.base_price + leg2.base_price
            total_duration = leg2.scheduled_arrival_time - leg1.scheduled_departure_time
            layover_duration = leg2.scheduled_departure_time - leg1.scheduled_arrival_time

            results.append({
                'type': '1-STOP',
                'flights': [leg1, leg2],
                'total_price': total_price,
                'total_duration': total_duration,
                'layover_duration': layover_duration
            })

    return results


def generate_pnr():
    """
    Generates a unique 6-character Passenger Name Record (PNR).
    Excludes ambiguous characters (0, O, 1, I) to prevent human typos.
    """
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    while True:
        pnr = "".join(random.choices(chars, k=6))
        if not Reservation.objects.filter(pnr=pnr).exists():
            return pnr


@transaction.atomic
def create_reservation(flight_id, passenger_data):
    """
    Handles atomic booking creation:
    1. Locks the flight row to prevent concurrent race conditions.
    2. Validates seat availability.
    3. Generates a unique PNR and locks in the base price.
    4. Decrements available seats safely.
    """
    try:
        # Lock this specific flight row until the transaction completes
        flight = Flight.objects.select_for_update().get(id=flight_id)
    except Flight.DoesNotExist:
        raise ValueError("Selected flight does not exist.")

    # 1. Validate Seat Availability
    if flight.available_seats <= 0:
        raise ValueError("Sorry, this flight is fully booked.")

    seat_number = (passenger_data.get('seat_number') or '').strip().upper()
    if not seat_number:
        raise ValueError("Please select a seat before booking.")
    if Reservation.objects.filter(
        flight=flight,
        seat_number=seat_number,
        status=Reservation.ReservationStatus.CONFIRMED,
    ).exists():
        raise ValueError("That seat has already been booked. Please select another seat.")

    # 2. Generate PNR
    pnr = generate_pnr()

    # 3. Create the Reservation Record
    reservation = Reservation.objects.create(
        pnr=pnr,
        flight=flight,
        user=passenger_data.get('user'),
        passenger_name=passenger_data.get('name'),
        passenger_email=passenger_data.get('email'),
        passport_number=passenger_data.get('passport', ''),
        nationality=passenger_data.get('nationality', ''),
        seat_number=seat_number,
        price_paid=flight.base_price,
        payment_status=Reservation.PaymentStatus.PAID,
        status=Reservation.ReservationStatus.CONFIRMED
    )

    # 4. Decrement available seats on the flight inventory
    flight.available_seats -= 1
    flight.save()

    return reservation


def get_booked_seats(flight_id):
    """Returns a set of already reserved seat numbers for a given flight."""
    return set(
        Reservation.objects.filter(
            flight_id=flight_id,
            status=Reservation.ReservationStatus.CONFIRMED,
        ).values_list('seat_number', flat=True)
    )


@transaction.atomic
def cancel_reservation(pnr, user):
    """Cancel an owned future reservation and return its seat to inventory."""
    reservation_flight = Reservation.objects.filter(
        pnr=pnr,
        user=user,
    ).values_list('flight_id', flat=True).first()
    if reservation_flight is None:
        raise ValueError("This booking is not associated with your account.")

    flight = Flight.objects.select_for_update().get(id=reservation_flight)
    reservation = Reservation.objects.select_for_update().get(
        pnr=pnr,
        user=user,
    )

    if reservation.status != Reservation.ReservationStatus.CONFIRMED:
        raise ValueError("This booking is not confirmed.")
    if flight.estimated_departure_time <= timezone.now():
        raise ValueError("Bookings can only be cancelled before departure.")

    reservation.status = Reservation.ReservationStatus.CANCELLED
    reservation.save(update_fields=['status'])
    flight.available_seats = min(flight.total_seats, flight.available_seats + 1)
    flight.save(update_fields=['available_seats'])

    return reservation