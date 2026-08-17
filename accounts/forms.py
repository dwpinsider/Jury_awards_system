from django import forms


class EmailLoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'you@organization.gov.ae',
            'autofocus': True,
            'class': 'input',
        })
    )


class OTPVerifyForm(forms.Form):
    code = forms.CharField(
        max_length=8,
        widget=forms.TextInput(attrs={
            'placeholder': '6-digit code',
            'autofocus': True,
            'inputmode': 'numeric',
            'class': 'input otp-input',
        })
    )
