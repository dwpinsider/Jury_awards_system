from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views
from .forms import StaffLoginForm, StaffPasswordResetForm, StaffSetPasswordForm

app_name = 'staff'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(
        template_name='staff/login.html', redirect_authenticated_user=True,
        authentication_form=StaffLoginForm,
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='staff:login'), name='logout'),

    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='staff/password_reset.html',
        email_template_name='staff/password_reset_email.txt',
        subject_template_name='staff/password_reset_subject.txt',
        form_class=StaffPasswordResetForm,
        success_url=reverse_lazy('staff:password_reset_done'),
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='staff/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='staff/password_reset_confirm.html',
        form_class=StaffSetPasswordForm,
        success_url=reverse_lazy('staff:password_reset_complete'),
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='staff/password_reset_complete.html',
    ), name='password_reset_complete'),

    path('', views.nominations, name='nominations'),
    path('rankings/', views.rankings, name='rankings'),
    path('winners/', views.winners, name='winners'),
    path('analytics/', views.analytics, name='analytics'),
    path('jury-reviews/', views.jury_reviews, name='jury_reviews'),
    path('recently-viewed/', views.recently_viewed, name='recently_viewed'),
    path('scorecard/<int:pk>/', views.scorecard, name='scorecard'),
    path('nomination/<int:pk>/result/', views.edit_result, name='edit_result'),
]