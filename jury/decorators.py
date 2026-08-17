from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from accounts.models import Juror


def juror_required(view_func):
    """Requires a verified, active juror who has accepted the NDA."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        juror_id = request.session.get('juror_id')
        if not juror_id or not request.session.get('juror_verified'):
            return redirect('accounts:login')

        juror = Juror.objects.filter(id=juror_id, is_active=True).first()
        if not juror:
            request.session.flush()
            messages.error(request, 'Your session has expired or your account is inactive. Please log in again.')
            return redirect('accounts:login')

        if not juror.nda_accepted:
            return redirect('accounts:nda')

        request.juror = juror
        return view_func(request, *args, **kwargs)

    return _wrapped
