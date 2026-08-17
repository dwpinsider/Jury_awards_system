from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.urls import reverse

from .forms import EmailLoginForm, OTPVerifyForm
from .models import Juror, OTPCode


def _send_otp_email(juror, otp):
    subject = 'Your GOV HR & Youth Awards jury verification code'
    message = (
        f'Hello {juror.full_name},\n\n'
        f'Your one-time verification code is: {otp.code}\n'
        f'This code expires in {settings.OTP_VALIDITY_MINUTES} minutes.\n\n'
        f'If you did not request this, you can ignore this email.\n\n'
        f'GOV HR & Youth Awards - Jury Portal'
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [juror.email], fail_silently=True)


def login_request(request):
    """Step 1: juror enters their email; we email them a one-time code."""
    if request.session.get('juror_id') and request.session.get('juror_verified'):
        return redirect('jury:dashboard')

    if request.method == 'POST':
        form = EmailLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            try:
                juror = Juror.objects.get(email__iexact=email, is_active=True)
            except Juror.DoesNotExist:
                messages.error(
                    request,
                    'We could not find an active jury account for that email address. '
                    'Please contact the awards secretariat.',
                )
                return render(request, 'accounts/login.html', {'form': form})

            otp = OTPCode.issue_for(juror)
            _send_otp_email(juror, otp)

            request.session['pending_juror_id'] = juror.id
            request.session['otp_sent_at'] = timezone.now().isoformat()
            messages.success(request, f'A 6-digit verification code has been sent to {juror.email}.')
            return redirect('accounts:verify_otp')
    else:
        form = EmailLoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def verify_otp(request):
    """Step 2: juror enters the code emailed to them."""
    pending_id = request.session.get('pending_juror_id')
    if not pending_id:
        return redirect('accounts:login')

    juror = Juror.objects.filter(id=pending_id).first()
    if not juror:
        return redirect('accounts:login')

    if request.method == 'POST':
        form = OTPVerifyForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code'].strip()
            otp = OTPCode.objects.filter(juror=juror, code=code).order_by('-created_at').first()
            if otp and otp.is_valid():
                otp.is_used = True
                otp.save(update_fields=['is_used'])

                juror.last_login_at = timezone.now()
                juror.save(update_fields=['last_login_at'])

                request.session['juror_id'] = juror.id
                request.session['juror_verified'] = True
                del request.session['pending_juror_id']

                if not juror.nda_accepted:
                    return redirect('accounts:nda')
                return redirect('jury:dashboard')
            else:
                messages.error(request, 'That code is invalid or has expired. Please try again or resend a new code.')
    else:
        form = OTPVerifyForm()

    return render(request, 'accounts/verify_otp.html', {'form': form, 'juror': juror})


def resend_otp(request):
    pending_id = request.session.get('pending_juror_id')
    juror = Juror.objects.filter(id=pending_id).first() if pending_id else None
    if juror:
        otp = OTPCode.issue_for(juror)
        _send_otp_email(juror, otp)
        messages.success(request, f'A new code has been sent to {juror.email}.')
    return redirect('accounts:verify_otp')


def nda_view(request):
    juror_id = request.session.get('juror_id')
    if not juror_id or not request.session.get('juror_verified'):
        return redirect('accounts:login')

    juror = Juror.objects.filter(id=juror_id).first()
    if not juror:
        return redirect('accounts:login')

    if request.method == 'POST':
        if juror.nda_accepted:
            # Already accepted — nothing to do, just show the page again.
            return redirect('accounts:nda')
        if request.POST.get('agree') == 'on':
            juror.nda_accepted = True
            juror.nda_accepted_at = timezone.now()
            juror.save(update_fields=['nda_accepted', 'nda_accepted_at'])
            messages.success(request, 'Thank you. You now have access to the jury dashboard.')
            return redirect('jury:dashboard')
        else:
            messages.error(request, 'You must agree to the Non-Disclosure Agreement to continue.')

    return render(request, 'accounts/nda.html', {'juror': juror})


def logout_view(request):
    request.session.flush()
    messages.success(request, 'You have been logged out.')
    return redirect('accounts:login')