from django.contrib import admin
from .models import Juror, OTPCode


@admin.register(Juror)
class JurorAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'organization', 'is_active', 'nda_accepted', 'last_login_at')
    list_filter = ('is_active', 'nda_accepted')
    search_fields = ('full_name', 'email', 'organization')
    filter_horizontal = ('assigned_categories',)
    readonly_fields = ('nda_accepted_at', 'created_at', 'last_login_at')


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ('juror', 'code', 'created_at', 'expires_at', 'is_used')
    list_filter = ('is_used',)
    search_fields = ('juror__email', 'code')
