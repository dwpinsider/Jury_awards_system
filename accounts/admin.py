from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect
from django.template.response import TemplateResponse

from .models import Juror, OTPCode
from .csv_import import import_jurors_from_csv, JUROR_CSV_COLUMNS

try:
    from awards.forms import CSVUploadForm
except ImportError:
    CSVUploadForm = None


@admin.register(Juror)
class JurorAdmin(admin.ModelAdmin):
    change_list_template = 'admin/accounts/juror_change_list.html'
    list_display = ('full_name', 'email', 'organization', 'is_active', 'nda_accepted', 'last_login_at')
    list_filter = ('is_active', 'nda_accepted')
    search_fields = ('full_name', 'email', 'organization')
    filter_horizontal = ('assigned_categories',)
    readonly_fields = ('nda_accepted_at', 'created_at', 'last_login_at')

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='accounts_juror_import_csv'),
        ]
        return custom + urls

    def import_csv(self, request):
        if request.method == 'POST':
            form = CSVUploadForm(request.POST, request.FILES)
            if form.is_valid():
                result = import_jurors_from_csv(
                    request.FILES['csv_file'],
                    update_existing=form.cleaned_data['update_existing'],
                )
                messages.success(
                    request,
                    f"Import finished — {result['created']} created, "
                    f"{result['updated']} updated, {result['skipped']} skipped."
                )
                for err in result['errors'][:25]:
                    messages.warning(request, err)
                return redirect('admin:accounts_juror_changelist')
        else:
            form = CSVUploadForm()

        context = dict(
            self.admin_site.each_context(request),
            title='Import Jurors from CSV',
            form=form, columns=JUROR_CSV_COLUMNS,
            opts=self.model._meta,
        )
        return TemplateResponse(request, 'admin/awards/import_csv.html', context)


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ('juror', 'code', 'created_at', 'expires_at', 'is_used')
    list_filter = ('is_used',)
    search_fields = ('juror__email', 'code')