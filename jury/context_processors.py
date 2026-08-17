from accounts.models import Juror


def juror_context(request):
    """Makes the logged-in juror available in every template as `current_juror`."""
    juror_id = request.session.get('juror_id')
    if juror_id and request.session.get('juror_verified'):
        juror = Juror.objects.filter(id=juror_id).first()
        return {'current_juror': juror}
    return {'current_juror': None}
