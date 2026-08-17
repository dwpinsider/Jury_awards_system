from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_request, name='login'),
    path('verify/', views.verify_otp, name='verify_otp'),
    path('resend/', views.resend_otp, name='resend_otp'),
    path('nda/', views.nda_view, name='nda'),
    path('logout/', views.logout_view, name='logout'),
]
