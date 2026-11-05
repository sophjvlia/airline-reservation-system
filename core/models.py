from django.db import models
from django.conf import settings

class Airport(models.Model):
    """Airport hub with timezone support for route duration calculations."""
    code = models.CharField(max_length=3, unique=True, help_text="IATA code (e.g., KUL)")
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    timezone = models.CharField(max_length=50, default="UTC", help_text="IANA timezone (e.g., Asia/Kuala_Lumpur)")

    def __str__(self):
        return f"{self.code} - {self.city}, {self.country}"


class Flight(models.Model):
    """Scheduled commercial flight tracking timetables, delays, and capacity."""
    class FlightStatus(models.TextChoices):
        EXPECTED = 'EXPECTED', 'Expected'
        BOARDING = 'BOARDING', 'Boarding'
        GATE_CLOSED = 'GATE_CLOSED', 'Gate Closed'
        DEPARTED = 'DEPARTED', 'Departed'
        ARRIVED = 'ARRIVED', 'Arrived'
        DELAYED = 'DELAYED', 'Delayed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class CabinClass(models.TextChoices):
        ECONOMY = 'ECONOMY', 'Economy'
        BUSINESS = 'BUSINESS', 'Business'
        FIRST = 'FIRST', 'First Class'

    airline = models.CharField(max_length=100)
    callsign = models.CharField(max_length=20, unique=True)
    
    origin = models.ForeignKey(Airport, related_name="departures", on_delete=models.CASCADE)
    destination = models.ForeignKey(Airport, related_name="arrivals", on_delete=models.CASCADE)
    
    scheduled_departure_time = models.DateTimeField()
    estimated_departure_time = models.DateTimeField()
    scheduled_arrival_time = models.DateTimeField()
    estimated_arrival_time = models.DateTimeField()
    
    departure_gate = models.CharField(max_length=10, blank=True, null=True)
    arrival_gate = models.CharField(max_length=10, blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=FlightStatus.choices, default=FlightStatus.EXPECTED)
    
    cabin_class = models.CharField(max_length=20, choices=CabinClass.choices, default=CabinClass.ECONOMY)
    total_seats = models.IntegerField(default=150)
    available_seats = models.IntegerField(default=150)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.airline} ({self.callsign}): {self.origin.code} to {self.destination.code} [{self.status}]"


class Reservation(models.Model):
    """Confirmed passenger booking linked via PNR, locking in pricing and passenger data."""
    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PAID = 'PAID', 'Paid'
        REFUNDED = 'REFUNDED', 'Refunded'

    class ReservationStatus(models.TextChoices):
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    pnr = models.CharField(max_length=6, unique=True, help_text="Passenger Name Record (e.g., K9X2L4)")
    flight = models.ForeignKey(Flight, on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='reservations',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    
    passenger_name = models.CharField(max_length=100)
    passenger_email = models.EmailField()
    passport_number = models.CharField(max_length=20, blank=True, null=True)
    nationality = models.CharField(max_length=50, blank=True, null=True)
    seat_number = models.CharField(max_length=10)
    
    price_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PAID)
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    
    booked_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.CONFIRMED,
    )

    def __str__(self):
        return f"PNR: {self.pnr} - {self.passenger_name} ({self.flight.callsign})"