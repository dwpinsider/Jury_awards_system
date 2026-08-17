import random
import string
from django.db import models
from django.utils import timezone
from django.conf import settings


class Juror(models.Model):
    """A member of the judging panel. Created/managed from the Django admin."""

    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    organization = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=255, blank=True)
    photo = models.ImageField(upload_to='jurors/', blank=True, null=True)

    is_active = models.BooleanField(
        default=True,
        help_text='Inactive jurors cannot log in even with a valid code.',
    )

    # Categories this juror is allowed to judge. Leave empty to allow ALL categories.
    assigned_categories = models.ManyToManyField(
        'awards.Category', blank=True, related_name='assigned_jurors'
    )

    nda_accepted = models.BooleanField(default=False)
    nda_accepted_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'{self.full_name} <{self.email}>'

    def categories_queryset(self):
        from awards.models import Category
        if self.assigned_categories.exists():
            return self.assigned_categories.all()
        return Category.objects.all()


def generate_otp_code(length=None):
    length = length or getattr(settings, 'OTP_LENGTH', 6)
    return ''.join(random.choices(string.digits, k=length))


class OTPCode(models.Model):
    """One-time verification code emailed to a juror at login time."""

    juror = models.ForeignKey(Juror, on_delete=models.CASCADE, related_name='otp_codes')
    code = models.CharField(max_length=8)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.juror.email} - {self.code}'

    def is_valid(self):
        return (not self.is_used) and timezone.now() <= self.expires_at

    @classmethod
    def issue_for(cls, juror):
        validity = getattr(settings, 'OTP_VALIDITY_MINUTES', 10)
        code = generate_otp_code()
        return cls.objects.create(
            juror=juror,
            code=code,
            expires_at=timezone.now() + timezone.timedelta(minutes=validity),
        )
