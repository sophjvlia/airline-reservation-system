from datetime import date, datetime, time, timedelta, timezone as datetime_timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from .forms import SignUpForm
from .models import Airport, Flight, Reservation
from .services import cancel_reservation, get_booked_seats, search_itineraries
from migration_entrypoint import handler as migration_lambda_handler


class FlightSearchTests(TestCase):
    def setUp(self):
        self.kul = Airport.objects.create(
            code='KUL',
            name='Kuala Lumpur International Airport',
            city='Kuala Lumpur',
            country='Malaysia',
            timezone='Asia/Kuala_Lumpur',
        )
        self.sin = Airport.objects.create(
            code='SIN',
            name='Changi Airport',
            city='Singapore',
            country='Singapore',
            timezone='Asia/Singapore',
        )

    def create_flight(self, callsign, departure, status=Flight.FlightStatus.EXPECTED, seats=10):
        arrival = departure + timedelta(hours=2)
        return Flight.objects.create(
            airline='Python Airlines',
            callsign=callsign,
            origin=self.kul,
            destination=self.sin,
            scheduled_departure_time=departure,
            estimated_departure_time=departure,
            scheduled_arrival_time=arrival,
            estimated_arrival_time=arrival,
            status=status,
            available_seats=seats,
            base_price=320,
        )

    def test_search_uses_origin_airport_local_date(self):
        utc_departure = datetime.combine(
            timezone.now().date() + timedelta(days=1),
            time(18),
            tzinfo=datetime_timezone.utc,
        )
        local_departure_date = utc_departure.astimezone(
            ZoneInfo(self.kul.timezone)
        ).date()
        flight = self.create_flight('PA-101', utc_departure)

        itineraries = search_itineraries('KUL', 'SIN', local_departure_date)

        self.assertEqual(len(itineraries), 1)
        self.assertEqual(itineraries[0]['flights'][0], flight)

    def test_search_includes_delayed_and_excludes_cancelled_or_full_flights(self):
        departure = datetime.combine(
            timezone.now().date() + timedelta(days=1),
            time(18),
            tzinfo=datetime_timezone.utc,
        )
        local_departure_date = departure.astimezone(ZoneInfo(self.kul.timezone)).date()
        expected = self.create_flight('PA-101', departure)
        delayed = self.create_flight(
            'PA-102', departure + timedelta(hours=1), Flight.FlightStatus.DELAYED
        )
        self.create_flight(
            'PA-103', departure + timedelta(hours=2), Flight.FlightStatus.CANCELLED
        )
        self.create_flight('PA-104', departure + timedelta(hours=3), seats=0)

        itineraries = search_itineraries('KUL', 'SIN', local_departure_date)
        found_callsigns = {itin['flights'][0].callsign for itin in itineraries}

        self.assertEqual(found_callsigns, {expected.callsign, delayed.callsign})

    def test_search_excludes_flights_that_have_departed_today(self):
        local_timezone = ZoneInfo(self.kul.timezone)
        now = datetime(2026, 5, 10, 10, tzinfo=local_timezone)
        departed = self.create_flight('PA-105', now - timedelta(hours=1))
        future = self.create_flight('PA-106', now + timedelta(hours=1))

        with patch('core.services.timezone.now', return_value=now):
            itineraries = search_itineraries('KUL', 'SIN', now.date())

        found_callsigns = {itin['flights'][0].callsign for itin in itineraries}
        self.assertEqual(found_callsigns, {future.callsign})
        self.assertNotIn(departed.callsign, found_callsigns)

    def test_invalid_date_shows_search_error(self):
        response = self.client.get(
            reverse('flight_search'),
            {'origin': 'KUL', 'destination': 'SIN', 'date': 'not-a-date'},
        )

        self.assertContains(response, 'Please enter a valid departure date.')

    def test_search_results_use_card_layout(self):
        departure = timezone.now() + timedelta(days=2)
        self.create_flight('PA-107', departure)
        search_date = departure.astimezone(
            ZoneInfo(self.kul.timezone)
        ).date().isoformat()

        response = self.client.get(
            reverse('flight_search'),
            {'origin': 'KUL', 'destination': 'SIN', 'date': search_date},
        )

        self.assertContains(response, 'Available flight options')
        self.assertContains(response, 'Choose journey')
        self.assertContains(response, 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4')
        self.assertNotContains(response, '→')
        self.assertContains(response, '<svg aria-hidden="true"', html=False)

    def test_mobile_navigation_spans_viewport_and_stacks_links(self):
        response = self.client.get(reverse('flight_search'))

        self.assertContains(
            response,
            'fixed left-0 right-0 top-16 z-50 flex w-full flex-col items-stretch',
        )
        self.assertContains(response, "primaryNavigation.classList.toggle('is-open', !expanded)")
        self.assertContains(response, 'menu-icon__line--top')
        self.assertContains(response, 'prefers-reduced-motion: reduce')
        self.assertContains(response, 'bg-slate-900/90')
        self.assertContains(response, 'md:ml-8 md:flex md:flex-1 md:flex-row md:items-center md:justify-between')

    def test_search_page_uses_local_cloud_backdrop_and_glass_cards(self):
        response = self.client.get(reverse('flight_search'))

        self.assertContains(response, 'fluffy-clouds.jpg')
        self.assertContains(response, 'backdrop-blur-2xl')
        self.assertContains(response, 'The world is waiting')
        self.assertContains(response, 'bg-slate-950/55')
        self.assertContains(response, '<svg aria-hidden="true"', html=False)

    def test_primary_booking_actions_use_amber(self):
        response = self.client.get(reverse('flight_search'))
        self.assertContains(response, 'bg-amber-200')


class SeatCheckoutTests(TestCase):
    def setUp(self):
        self.origin = Airport.objects.create(
            code='KUL',
            name='Kuala Lumpur International Airport',
            city='Kuala Lumpur',
            country='Malaysia',
            timezone='Asia/Kuala_Lumpur',
        )
        self.destination = Airport.objects.create(
            code='SIN',
            name='Changi Airport',
            city='Singapore',
            country='Singapore',
            timezone='Asia/Singapore',
        )
        departure = timezone.now() + timedelta(days=1)
        self.flight = Flight.objects.create(
            airline='Python Airlines',
            callsign='PA-201',
            origin=self.origin,
            destination=self.destination,
            scheduled_departure_time=departure,
            estimated_departure_time=departure,
            scheduled_arrival_time=departure + timedelta(hours=2),
            estimated_arrival_time=departure + timedelta(hours=2),
            available_seats=10,
            base_price=320,
        )

    def test_selected_seat_is_prefilled_and_saved(self):
        seat_response = self.client.post(
            reverse('seat_selection', args=[self.flight.id]),
            {'seat_number': '2C'},
        )
        self.assertRedirects(
            seat_response,
            reverse('checkout', args=[self.flight.id]),
        )

        checkout_response = self.client.get(reverse('checkout', args=[self.flight.id]))
        self.assertContains(checkout_response, 'name="seat_number" value="2C"')

        confirmation_response = self.client.post(
            reverse('checkout', args=[self.flight.id]),
            {
                'name': 'Taylor Example',
                'email': 'taylor@example.com',
                'passport': 'P1234567',
                'nationality': 'Malaysian',
                'seat_number': '2C',
            },
        )

        self.assertEqual(confirmation_response.status_code, 200)
        self.assertTrue(
            Reservation.objects.filter(flight=self.flight, seat_number='2C').exists()
        )

    def test_duplicate_seat_is_rejected(self):
        self.client.post(
            reverse('seat_selection', args=[self.flight.id]),
            {'seat_number': '2C'},
        )
        passenger_data = {
            'name': 'Taylor Example',
            'email': 'taylor@example.com',
            'seat_number': '2C',
        }
        Reservation.objects.create(
            pnr='ABC234',
            flight=self.flight,
            passenger_name='Existing Passenger',
            passenger_email='existing@example.com',
            seat_number='2C',
            price_paid=self.flight.base_price,
        )

        response = self.client.post(
            reverse('checkout', args=[self.flight.id]),
            passenger_data,
        )

        self.assertRedirects(
            response,
            reverse('checkout', args=[self.flight.id]),
            fetch_redirect_response=False,
        )
        self.assertContains(
            self.client.get(reverse('checkout', args=[self.flight.id])),
            'That seat has already been booked.',
        )


class FutureFlightSeedTests(TestCase):
    def test_seed_adds_twelve_future_flights_repeatably_without_clearing_data(self):
        kul = Airport.objects.create(
            code='KUL',
            name='Kuala Lumpur International Airport',
            city='Kuala Lumpur',
            country='Malaysia',
            timezone='Asia/Kuala_Lumpur',
        )
        sin = Airport.objects.create(
            code='SIN',
            name='Changi Airport',
            city='Singapore',
            country='Singapore',
            timezone='Asia/Singapore',
        )
        departure = timezone.now() + timedelta(days=2)
        existing_flight = Flight.objects.create(
            airline='Python Airlines',
            callsign='KEEP-001',
            origin=kul,
            destination=sin,
            scheduled_departure_time=departure,
            estimated_departure_time=departure,
            scheduled_arrival_time=departure + timedelta(hours=2),
            estimated_arrival_time=departure + timedelta(hours=2),
            available_seats=10,
            total_seats=10,
            base_price=320,
        )
        reservation = Reservation.objects.create(
            pnr='KEEP01',
            flight=existing_flight,
            passenger_name='Existing Passenger',
            passenger_email='existing@example.com',
            seat_number='1A',
            price_paid=existing_flight.base_price,
        )

        call_command('seed_future_flights', verbosity=0)
        call_command('seed_future_flights', verbosity=0)

        self.assertEqual(Flight.objects.count(), 13)
        self.assertEqual(Airport.objects.count(), 5)
        self.assertTrue(Flight.objects.filter(pk=existing_flight.pk).exists())
        self.assertTrue(Reservation.objects.filter(pk=reservation.pk).exists())
        self.assertEqual(
            Flight.objects.filter(callsign__startswith='PA26-11').count(),
            4,
        )
        self.assertEqual(
            Flight.objects.filter(callsign__startswith='PA26-12').count(),
            4,
        )
        self.assertEqual(
            Flight.objects.filter(callsign__startswith='PA27-01').count(),
            4,
        )

    def test_seeded_flights_support_connecting_search(self):
        call_command('seed_future_flights', verbosity=0)

        itineraries = search_itineraries('KUL', 'LHR', date(2026, 11, 15))

        self.assertEqual(len(itineraries), 1)
        self.assertEqual(itineraries[0]['type'], '1-STOP')
        self.assertEqual(
            [flight.callsign for flight in itineraries[0]['flights']],
            ['PA26-11-KULSIN', 'PA26-11-SINLHR'],
        )


class MigrationLambdaActionTests(TestCase):
    @patch('migration_entrypoint.load_secrets')
    @patch('django.setup')
    @patch('django.core.management.call_command')
    def test_default_action_runs_migrations(self, call_command, setup, load_secrets):
        response = migration_lambda_handler({}, None)

        self.assertEqual(response, {'status': 'migrations applied'})
        load_secrets.assert_called_once_with()
        setup.assert_called_once_with()
        call_command.assert_called_once_with('migrate', interactive=False)

    @patch('migration_entrypoint.load_secrets')
    @patch('django.setup')
    @patch('django.core.management.call_command')
    def test_seed_action_runs_only_future_flight_seeder(
        self,
        call_command,
        setup,
        load_secrets,
    ):
        response = migration_lambda_handler({'action': 'seed_future_flights'}, None)

        self.assertEqual(response, {'status': 'future flights seeded'})
        load_secrets.assert_called_once_with()
        setup.assert_called_once_with()
        call_command.assert_called_once_with('seed_future_flights')

    @patch('migration_entrypoint.load_secrets')
    def test_unknown_action_fails_before_loading_secrets(self, load_secrets):
        with self.assertRaisesMessage(ValueError, 'Unsupported migration Lambda action'):
            migration_lambda_handler({'action': 'seed_data'}, None)

        load_secrets.assert_not_called()


class AccountBookingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='traveler',
            email='traveler@example.com',
            password='strong-test-password-123',
        )
        self.other_user = get_user_model().objects.create_user(
            username='another-traveler',
            email='another@example.com',
            password='another-strong-password-123',
        )
        self.origin = Airport.objects.create(
            code='KUL',
            name='Kuala Lumpur International Airport',
            city='Kuala Lumpur',
            country='Malaysia',
            timezone='Asia/Kuala_Lumpur',
        )
        self.destination = Airport.objects.create(
            code='SIN',
            name='Changi Airport',
            city='Singapore',
            country='Singapore',
            timezone='Asia/Singapore',
        )
        departure = timezone.now() + timedelta(days=5)
        self.flight = Flight.objects.create(
            airline='Python Airlines',
            callsign='PA-301',
            origin=self.origin,
            destination=self.destination,
            scheduled_departure_time=departure,
            estimated_departure_time=departure,
            scheduled_arrival_time=departure + timedelta(hours=2),
            estimated_arrival_time=departure + timedelta(hours=2),
            available_seats=9,
            total_seats=10,
            base_price=320,
        )

    def create_reservation(self, user=None, pnr='ABC234', seat='1A', flight=None):
        return Reservation.objects.create(
            pnr=pnr,
            flight=flight or self.flight,
            user=user,
            passenger_name='Private Passenger Name',
            passenger_email='passenger@example.com',
            passport_number='PRIVATE123',
            nationality='Malaysian',
            seat_number=seat,
            price_paid=self.flight.base_price,
        )

    def test_booking_and_auth_pages_use_light_glass_and_amber_actions(self):
        for page_name in ('pnr_lookup', 'login', 'signup'):
            response = self.client.get(reverse(page_name))
            self.assertContains(response, 'account-page-body')
            self.assertContains(response, 'account-glass-panel')
            self.assertContains(response, 'rgba(224, 242, 254, 0.62)')
            self.assertContains(response, 'bg-amber-200')

        self.client.force_login(self.user)
        response = self.client.get(reverse('my_bookings'))
        self.assertContains(response, 'account-page-body')
        self.assertContains(response, 'bg-white/75')
        self.assertContains(response, 'bg-amber-200')

    def test_signup_creates_user_and_signs_them_in(self):
        response = self.client.post(
            reverse('signup'),
            {
                'username': 'newtraveler',
                'email': 'newtraveler@example.com',
                'password1': 'new-strong-password-123',
                'password2': 'new-strong-password-123',
            },
        )

        self.assertRedirects(response, reverse('my_bookings'))
        self.assertTrue(
            get_user_model().objects.filter(username='newtraveler').exists()
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_signup_fields_are_required_and_username_has_clear_limits(self):
        form = SignUpForm()

        for field_name in ('username', 'email', 'password1', 'password2'):
            self.assertTrue(form.fields[field_name].required)
        self.assertEqual(form.fields['username'].max_length, 20)
        self.assertEqual(
            form.fields['username'].help_text,
            'Up to 20 characters. Use letters and numbers, plus @, ., +, - or _.',
        )
        self.assertNotIn('/', form.fields['username'].help_text)

        invalid_username = SignUpForm(
            data={
                'username': 'invalid username',
                'email': 'traveler@example.com',
                'password1': 'strong-password-123',
                'password2': 'strong-password-123',
            }
        )
        self.assertFalse(invalid_username.is_valid())
        self.assertEqual(
            invalid_username.errors['username'],
            ['Enter a valid username'],
        )

        overlong_username = SignUpForm(
            data={
                'username': 'a' * 21,
                'email': 'traveler@example.com',
                'password1': 'strong-password-123',
                'password2': 'strong-password-123',
            }
        )
        self.assertFalse(overlong_username.is_valid())
        self.assertIn('username', overlong_username.errors)

    def test_signup_template_marks_required_fields_and_shows_password_criteria(self):
        response = self.client.get(reverse('signup'))

        self.assertContains(response, 'aria-hidden="true">*</span>')
        self.assertContains(response, 'class="sr-only"> (required)</span>')
        self.assertContains(response, 'text-xs leading-relaxed text-slate-500')
        self.assertContains(response, '<ul>', html=False)
        self.assertContains(response, 'at least 8 characters')

    def test_login_template_marks_required_fields(self):
        response = self.client.get(reverse('login'))

        self.assertContains(response, 'aria-hidden="true">*</span>')
        self.assertContains(response, 'class="sr-only"> (required)</span>')

    def test_authenticated_checkout_attaches_reservation_to_account(self):
        self.client.force_login(self.user)
        session = self.client.session
        session[f'flight_{self.flight.id}_seat'] = '2A'
        session.save()

        response = self.client.post(
            reverse('checkout', args=[self.flight.id]),
            {
                'name': 'Account Passenger',
                'email': 'account@example.com',
                'passport': 'P1234567',
                'nationality': 'Malaysian',
            },
        )

        self.assertEqual(response.status_code, 200)
        reservation = Reservation.objects.get(passenger_email='account@example.com')
        self.assertEqual(reservation.user, self.user)

    def test_cancellation_releases_seat_and_cannot_be_repeated(self):
        reservation = self.create_reservation(user=self.user)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('cancel_booking', args=[reservation.pnr]),
        )

        self.assertRedirects(response, reverse('my_bookings'))
        reservation.refresh_from_db()
        self.flight.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.ReservationStatus.CANCELLED)
        self.assertEqual(self.flight.available_seats, 10)
        self.assertNotIn('1A', get_booked_seats(self.flight.id))

        second_response = self.client.post(
            reverse('cancel_booking', args=[reservation.pnr]),
        )
        self.assertRedirects(second_response, reverse('my_bookings'))
        self.flight.refresh_from_db()
        self.assertEqual(self.flight.available_seats, 10)

    def test_user_cannot_cancel_another_users_reservation(self):
        reservation = self.create_reservation(user=self.user)
        self.client.force_login(self.other_user)

        self.client.post(reverse('cancel_booking', args=[reservation.pnr]))

        reservation.refresh_from_db()
        self.flight.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.ReservationStatus.CONFIRMED)
        self.assertEqual(self.flight.available_seats, 9)

    def test_cannot_cancel_after_estimated_departure(self):
        reservation = self.create_reservation(user=self.user)
        self.flight.estimated_departure_time = timezone.now() - timedelta(minutes=1)
        self.flight.save(update_fields=['estimated_departure_time'])
        self.client.force_login(self.user)

        with self.assertRaisesMessage(ValueError, 'Bookings can only be cancelled before departure.'):
            cancel_reservation(reservation.pnr, self.user)

        reservation.refresh_from_db()
        self.flight.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.ReservationStatus.CONFIRMED)
        self.assertEqual(self.flight.available_seats, 9)

    def test_guest_lookup_hides_passenger_details(self):
        reservation = self.create_reservation()

        response = self.client.get(
            reverse('pnr_lookup'),
            {'pnr': reservation.pnr},
        )

        self.assertContains(response, reservation.flight.callsign)
        self.assertNotContains(response, 'Private Passenger Name')
        self.assertNotContains(response, 'PRIVATE123')
        self.assertContains(response, 'Sign in to manage')
        self.assertContains(response, 'account-glass-panel')

    def test_guest_confirmation_url_does_not_expose_full_ticket(self):
        reservation = self.create_reservation()

        response = self.client.get(reverse('confirmation', args=[reservation.pnr]))

        self.assertRedirects(
            response,
            f"{reverse('pnr_lookup')}?pnr={reservation.pnr}",
        )

    def test_existing_guest_booking_is_not_claimed_after_login(self):
        reservation = self.create_reservation()
        self.client.force_login(self.user)

        response = self.client.get(reverse('booking_manage', args=[reservation.pnr]))

        self.assertRedirects(
            response,
            f"{reverse('pnr_lookup')}?pnr={reservation.pnr}",
        )
        self.assertIsNone(reservation.user)

    def test_sample_reservation_command_is_repeatable_and_owner_aware(self):
        call_command('seed_reservations', username=self.user.username, verbosity=0)
        self.flight.refresh_from_db()
        seats_after_first_run = self.flight.available_seats

        call_command('seed_reservations', username=self.user.username, verbosity=0)

        samples = Reservation.objects.filter(pnr__in=['PYT234', 'PYT235'])
        self.flight.refresh_from_db()
        self.assertEqual(samples.count(), 2)
        self.assertEqual(samples.filter(user=self.user).count(), 2)
        self.assertEqual(self.flight.available_seats, seats_after_first_run)
