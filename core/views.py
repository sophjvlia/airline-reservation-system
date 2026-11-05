from datetime import datetime
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from .forms import SignUpForm
from .models import Airport, Flight, Reservation
from .services import (
    search_itineraries,
    create_reservation,
    get_booked_seats,
    cancel_reservation,
)

def flight_search_view(request):
    origin_code = request.GET.get('origin', '').strip().upper()
    dest_code = request.GET.get('destination', '').strip().upper()
    date_str = request.GET.get('date', '').strip()

    airports = Airport.objects.all()
    itineraries = []
    searched = False

    if origin_code and dest_code and date_str:
        searched = True
        try:
            search_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            searched = False
            messages.error(request, "Please enter a valid departure date.")
        else:
            itineraries = search_itineraries(origin_code, dest_code, search_date)

    # Fetch up to 5 upcoming flights as featured/fallback options
    upcoming_flights = Flight.objects.filter(
        estimated_departure_time__gte=timezone.now(),
        status__in=[Flight.FlightStatus.EXPECTED, Flight.FlightStatus.DELAYED],
        available_seats__gt=0,
    ).order_by('estimated_departure_time')[:5]

    context = {
        'airports': airports,
        'itineraries': itineraries,
        'upcoming_flights': upcoming_flights,
        'searched': searched,
        'origin': origin_code,
        'destination': dest_code,
        'date': date_str,
    }
    return render(request, 'core/search.html', context)


def seat_selection_view(request, flight_id):
    flight = get_object_or_404(Flight, id=flight_id)
    booked_seats = get_booked_seats(flight_id)
    valid_seats = {f'{row}{column}' for row in range(1, 11) for column in 'ABCDEF'}

    # Define a standard 6-column single-aisle cabin layout (Rows 1 to 10)
    rows = range(1, 11)
    columns = ['A', 'B', 'C', 'D', 'E', 'F']

    if request.method == 'POST':
        selected_seat = request.POST.get('seat_number', '').strip().upper()
        if selected_seat not in valid_seats or selected_seat in booked_seats:
            messages.error(request, "Please select an available seat.")
            return redirect('seat_selection', flight_id=flight.id)
        
        # Store selected seat in session temporarily and redirect to checkout
        request.session[f'flight_{flight_id}_seat'] = selected_seat
        return redirect('checkout', flight_id=flight.id)

    context = {
        'flight': flight,
        'rows': rows,
        'columns': columns,
        'booked_seats': booked_seats,
    }
    return render(request, 'core/seat_selection.html', context)


def checkout_view(request, flight_id):
    flight = get_object_or_404(Flight, id=flight_id)
    seat_session_key = f'flight_{flight_id}_seat'
    selected_seat = request.session.get(seat_session_key, '')
    if not selected_seat:
        messages.error(request, "Please choose a seat before continuing to checkout.")
        return redirect('seat_selection', flight_id=flight.id)

    if request.method == 'POST':
        passenger_data = {
            'name': request.POST.get('name'),
            'email': request.POST.get('email'),
            'passport': request.POST.get('passport'),
            'nationality': request.POST.get('nationality'),
            'seat_number': selected_seat,
            'user': request.user if request.user.is_authenticated else None,
        }

        try:
            reservation = create_reservation(flight.id, passenger_data)
            request.session.pop(seat_session_key, None)
            return render(request, 'core/confirmation.html', {'reservation': reservation})
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('checkout', flight_id=flight.id)

    context = {
        'flight': flight,
        'selected_seat': selected_seat,
    }

    return render(request, 'core/checkout.html', context)


def confirmation_view(request, pnr):
    reservation = get_object_or_404(Reservation, pnr=pnr.upper())
    if not request.user.is_authenticated or reservation.user_id != request.user.id:
        messages.error(request, "Sign in to view the full e-ticket for an account booking.")
        return redirect(f"{reverse('pnr_lookup')}?pnr={reservation.pnr}")
    return render(request, 'core/confirmation.html', {'reservation': reservation})


def pnr_lookup_view(request):
    pnr = request.GET.get('pnr', '').strip().upper()
    reservation = None
    not_found = False

    if pnr:
        try:
            reservation = Reservation.objects.get(pnr=pnr)
        except Reservation.DoesNotExist:
            not_found = True

    context = {
        'reservation': reservation,
        'pnr': pnr,
        'not_found': not_found,
        'can_manage': bool(
            reservation
            and request.user.is_authenticated
            and reservation.user_id == request.user.id
        ),
    }
    return render(request, 'core/lookup.html', context)


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('my_bookings')

    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('my_bookings')

    return render(request, 'core/registration/signup.html', {'form': form})


@login_required
def my_bookings_view(request):
    reservations = Reservation.objects.filter(user=request.user).select_related(
        'flight__origin',
        'flight__destination',
    ).order_by('-booked_at')
    now = timezone.now()
    bookings = [
        {
            'reservation': reservation,
            'can_cancel': (
                reservation.status == Reservation.ReservationStatus.CONFIRMED
                and reservation.flight.estimated_departure_time > now
            ),
        }
        for reservation in reservations
    ]
    return render(
        request,
        'core/my_bookings.html',
        {'bookings': bookings},
    )


@login_required
def booking_manage_view(request, pnr):
    reservation = Reservation.objects.filter(pnr=pnr.upper()).first()
    if reservation is None or reservation.user_id != request.user.id:
        messages.error(
            request,
            "This booking is not linked to your account. Guest bookings cannot be claimed.",
        )
        return redirect(f"{reverse('pnr_lookup')}?pnr={pnr.upper()}")
    return redirect('my_bookings')


@login_required
def cancel_booking_view(request, pnr):
    if request.method != 'POST':
        return redirect('my_bookings')

    try:
        cancel_reservation(pnr.upper(), request.user)
    except (Reservation.DoesNotExist, Flight.DoesNotExist):
        messages.error(request, "This booking could not be found.")
    except ValueError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Your booking has been cancelled.")

    return redirect('my_bookings')