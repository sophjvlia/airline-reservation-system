from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import Airport, Flight

class Command(BaseCommand):
    help = 'Populates the database with comprehensive test airports and flights.'

    def handle(self, *args, **options):
        self.stdout.write('Clearing existing data and seeding test scenarios...')

        # Clear old records
        Flight.objects.all().delete()
        Airport.objects.all().delete()

        # 1. Create Key Hub Airports
        kul = Airport.objects.create(code='KUL', name='Kuala Lumpur International Airport', city='Kuala Lumpur', country='Malaysia', timezone='Asia/Kuala_Lumpur')
        sin = Airport.objects.create(code='SIN', name='Changi Airport', city='Singapore', country='Singapore', timezone='Asia/Singapore')
        hnd = Airport.objects.create(code='HND', name='Haneda Airport', city='Tokyo', country='Japan', timezone='Asia/Tokyo')
        lhr = Airport.objects.create(code='LHR', name='Heathrow Airport', city='London', country='United Kingdom', timezone='Europe/London')
        jfk = Airport.objects.create(code='JFK', name='John F. Kennedy International Airport', city='New York', country='USA', timezone='America/New_York')

        now = timezone.now()

        # --- Test Case 1: Direct Flight Today (KUL -> SIN) ---
        dep_1 = now + timedelta(hours=3)
        arr_1 = now + timedelta(hours=4, minutes=30)
        Flight.objects.create(
            airline='Python Airlines',
            callsign='PA-101',
            origin=kul,
            destination=sin,
            scheduled_departure_time=dep_1,
            estimated_departure_time=dep_1,
            scheduled_arrival_time=arr_1,
            estimated_arrival_time=arr_1,
            base_price=320.00,
            available_seats=150,
            status=Flight.FlightStatus.EXPECTED,
            departure_gate='C12'
        )

        # --- Test Case 2: Direct Flight Tomorrow (KUL -> HND) ---
        dep_2 = now + timedelta(days=1, hours=6)
        arr_2 = now + timedelta(days=1, hours=13)
        Flight.objects.create(
            airline='Python Airlines',
            callsign='PA-202',
            origin=kul,
            destination=hnd,
            scheduled_departure_time=dep_2,
            estimated_departure_time=dep_2,
            scheduled_arrival_time=arr_2,
            estimated_arrival_time=arr_2,
            base_price=1850.00,
            available_seats=180,
            status=Flight.FlightStatus.EXPECTED,
            departure_gate='A5'
        )

        # --- Test Case 3: Connecting Leg 1 (KUL -> SIN) ---
        dep_3a = now + timedelta(days=2, hours=8)
        arr_3a = now + timedelta(days=2, hours=9, minutes=30)
        Flight.objects.create(
            airline='Python Airlines',
            callsign='PA-301',
            origin=kul,
            destination=sin,
            scheduled_departure_time=dep_3a,
            estimated_departure_time=dep_3a,
            scheduled_arrival_time=arr_3a,
            estimated_arrival_time=arr_3a,
            base_price=280.00,
            available_seats=120,
            status=Flight.FlightStatus.EXPECTED,
            departure_gate='B2'
        )
        
        # --- Test Case 3: Connecting Leg 2 (SIN -> LHR) ---
        dep_3b = now + timedelta(days=2, hours=12)
        arr_3b = now + timedelta(days=2, hours=20)
        Flight.objects.create(
            airline='Python Airlines',
            callsign='PA-302',
            origin=sin,
            destination=lhr,
            scheduled_departure_time=dep_3b,
            estimated_departure_time=dep_3b,
            scheduled_arrival_time=arr_3b,
            estimated_arrival_time=arr_3b,
            base_price=2400.00,
            available_seats=90,
            status=Flight.FlightStatus.EXPECTED,
            departure_gate='F10'
        )

        # --- Test Case 4: Low Inventory & Delayed Flight (SIN -> JFK) ---
        dep_4 = now + timedelta(days=3, hours=2)
        arr_4 = now + timedelta(days=3, hours=19)
        Flight.objects.create(
            airline='Python Airlines',
            callsign='PA-909',
            origin=sin,
            destination=jfk,
            scheduled_departure_time=dep_4,
            estimated_departure_time=dep_4 + timedelta(hours=1), # Delayed by 1h
            scheduled_arrival_time=arr_4,
            estimated_arrival_time=arr_4 + timedelta(hours=1),
            base_price=3400.00,
            available_seats=2,
            status='DELAYED',
            departure_gate='E4'
        )

        self.stdout.write(self.style.SUCCESS('Successfully populated test database with airports and flights!'))