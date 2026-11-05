from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.urls import path
from . import views
from .forms import StyledAuthenticationForm

urlpatterns = [
    path('', views.flight_search_view, name='flight_search'),
    path('healthz', lambda request: HttpResponse('ok'), name='health_check'),
    path('accounts/signup/', views.signup_view, name='signup'),
    path('accounts/login/', auth_views.LoginView.as_view(
        template_name='core/registration/login.html',
        authentication_form=StyledAuthenticationForm,
        redirect_authenticated_user=True,
    ), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('my-bookings/', views.my_bookings_view, name='my_bookings'),
    path('booking/<str:pnr>/manage/', views.booking_manage_view, name='booking_manage'),
    path('booking/<str:pnr>/cancel/', views.cancel_booking_view, name='cancel_booking'),
    path('flight/<int:flight_id>/select-seat/', views.seat_selection_view, name='seat_selection'),
    path('flight/<int:flight_id>/book/', views.checkout_view, name='checkout'),
    path('booking/<str:pnr>/', views.confirmation_view, name='confirmation'),
    path('lookup/', views.pnr_lookup_view, name='pnr_lookup'),
]