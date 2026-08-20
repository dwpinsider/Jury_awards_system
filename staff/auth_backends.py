from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class EmailBackend(ModelBackend):
    """Lets a user log in with their email address instead of their
    Django username. The login form field is still internally called
    "username" (that's hardcoded into Django's AuthenticationForm), but
    whatever the person types into it is looked up against User.email here,
    not User.username — so the actual username value on the account
    becomes irrelevant for login purposes."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        try:
            user = User.objects.get(email__iexact=username)
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # Two accounts somehow share an email — refuse rather than
            # guessing which one the person meant.
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None