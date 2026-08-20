from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django import forms

from awards.models import Nomination


class StaffLoginForm(AuthenticationForm):
    """Same as Django's default AuthenticationForm, styled with our .input
    CSS class. The field is internally still called "username" (hardcoded
    by Django's AuthenticationForm/LoginView), but is relabeled and
    validated as an email address — EmailBackend looks it up against
    User.email, not User.username, so staff log in with their email."""

    username = forms.CharField(
        label='Email address',
        widget=forms.EmailInput(attrs={'class': 'input', 'autofocus': True, 'autocomplete': 'email'}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'input', 'autocomplete': 'current-password'})
    )


class StaffPasswordResetForm(PasswordResetForm):
    """Same fix as StaffLoginForm, applied to the 'forgot password' email field."""
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'input', 'autofocus': True}))


class StaffSetPasswordForm(SetPasswordForm):
    """Same fix, applied to the 'choose a new password' step."""
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'input', 'autofocus': True})
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'input'})
    )


class ResultForm(forms.ModelForm):
    """The ONLY thing team members can change about a nomination — the
    declared result (award_tier) and an optional internal note. Deliberately
    exposes nothing else (organization name, nominee details, etc.) so this
    stays simple, unlike the full Django admin edit form."""

    class Meta:
        model = Nomination
        fields = ['award_tier', 'award_notes']
        widgets = {
            'award_tier': forms.Select(attrs={'class': 'input'}),
            'award_notes': forms.Textarea(attrs={'class': 'input', 'rows': 4, 'placeholder': 'Optional internal notes about this decision (not shown to jurors)...'}),
        }
        labels = {
            'award_tier': 'Result',
            'award_notes': 'Internal Notes',
        }