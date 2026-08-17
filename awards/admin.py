from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.db.models import Q
import csv
from django.http import HttpResponse

from .models import Category, Nomination, NominationStat, NominationDocument
from .forms import CSVUploadForm
from .csv_import import (
    import_categories_from_csv, import_nominations_from_csv,
    CATEGORY_CSV_COLUMNS, NOMINATION_CSV_COLUMNS,
)


def export_categories_as_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="categories.csv"'
    writer = csv.writer(response)
    writer.writerow(['name', 'level', 'sector', 'description', 'order', 'is_open_for_judging', 'nomination_count'])
    for cat in queryset.order_by('order', 'name'):
        writer.writerow([
            cat.name, cat.level, cat.sector, cat.description,
            cat.order, cat.is_open_for_judging, cat.nomination_count(),
        ])
    return response


export_categories_as_csv.short_description = 'Export selected categories to CSV'


def export_nominations_as_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="nominations.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'category', 'reference_code', 'organization_name', 'sector', 'city_country',
        'contact_person', 'designation', 'phone_number', 'mobile_number', 'email', 'website',
        'nominee_full_name', 'nominee_job_title', 'nominee_address', 'employee_headcount',
        'project_title', 'project_highlights', 'key_achievements', 'reason_for_nomination',
        'business_impact', 'is_visible_to_jury', 'review_count', 'average_score',
    ])
    for nom in queryset.select_related('category').order_by('category__name', 'organization_name'):
        writer.writerow([
            nom.category.name, nom.reference_code, nom.organization_name, nom.sector, nom.city_country,
            nom.contact_person, nom.designation, nom.phone_number, nom.mobile_number, nom.email, nom.website,
            nom.nominee_full_name, nom.nominee_job_title, nom.nominee_address, nom.employee_headcount,
            nom.project_title, nom.project_highlights, nom.key_achievements, nom.reason_for_nomination,
            nom.business_impact, nom.is_visible_to_jury, nom.review_count(), nom.average_score(),
        ])
    return response


export_nominations_as_csv.short_description = 'Export selected nominations to CSV'


def _run_import(request, import_func, columns, title, done_url_name):
    """Shared logic for the 'Import CSV' admin page."""
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            result = import_func(
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
            if len(result['errors']) > 25:
                messages.warning(request, f"...and {len(result['errors']) - 25} more issues (not all shown).")
            return redirect(done_url_name)
    else:
        form = CSVUploadForm()

    return form, columns, title


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    change_list_template = 'admin/awards/category_change_list.html'
    list_display = ('name', 'level', 'sector', 'is_open_for_judging', 'nomination_count', 'order')
    list_filter = ('level', 'sector', 'is_open_for_judging')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    actions = [export_categories_as_csv]

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='awards_category_import_csv'),
        ]
        return custom + urls

    def import_csv(self, request):
        result = _run_import(
            request, import_categories_from_csv, CATEGORY_CSV_COLUMNS,
            'Import Categories from CSV', 'admin:awards_category_changelist',
        )
        if not isinstance(result, tuple):
            return result  # was a redirect
        form, columns, title = result
        context = dict(
            self.admin_site.each_context(request),
            title=title, form=form, columns=columns,
            opts=self.model._meta,
        )
        return TemplateResponse(request, 'admin/awards/import_csv.html', context)


class NominationStatInline(admin.TabularInline):
    model = NominationStat
    extra = 1


class NominationDocumentInline(admin.TabularInline):
    model = NominationDocument
    extra = 1
    fields = ('label', 'file', 'video_url')


@admin.register(Nomination)
class NominationAdmin(admin.ModelAdmin):
    change_list_template = 'admin/awards/nomination_change_list.html'
    list_display = (
        'organization_name', 'category', 'nominee_full_name', 'award_tier_badge',
        'is_visible_to_jury', 'review_count', 'average_score', 'created_at',
    )
    list_filter = ('category', 'award_tier', 'is_visible_to_jury')
    search_fields = ('organization_name', 'nominee_full_name', 'contact_person', 'email')
    inlines = [NominationStatInline, NominationDocumentInline]
    actions = [export_nominations_as_csv]
    fieldsets = (
        ('Category', {'fields': ('category', 'reference_code', 'is_visible_to_jury')}),
        ('Organization / Submitter', {'fields': (
            'organization_name', 'sector', 'city_country', 'website',
            'contact_person', 'designation', 'phone_number', 'mobile_number', 'email',
        )}),
        ('Nominee (individual awards)', {'fields': (
            'nominee_full_name', 'nominee_job_title', 'nominee_address', 'employee_headcount',
        )}),
        ('Submission Content (from PDF)', {'fields': (
            'project_title', 'project_highlights', 'key_achievements',
            'reason_for_nomination', 'business_impact',
        )}),
        ('Result (secretariat only — not shown to jury)', {'fields': ('award_tier', 'award_notes')}),
    )

    @admin.display(description='Result')
    def award_tier_badge(self, obj):
        return obj.get_award_tier_display() if obj.award_tier else '—'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='awards_nomination_import_csv'),
            path('rankings/', self.admin_site.admin_view(self.rankings_view), name='awards_nomination_rankings'),
            path('winners/', self.admin_site.admin_view(self.winners_view), name='awards_nomination_winners'),
        ]
        return custom + urls

    def import_csv(self, request):
        result = _run_import(
            request, import_nominations_from_csv, NOMINATION_CSV_COLUMNS,
            'Import Nominations from CSV', 'admin:awards_nomination_changelist',
        )
        if not isinstance(result, tuple):
            return result  # was a redirect
        form, columns, title = result
        context = dict(
            self.admin_site.each_context(request),
            title=title, form=form, columns=columns,
            opts=self.model._meta,
        )
        return TemplateResponse(request, 'admin/awards/import_csv.html', context)

    def rankings_view(self, request):
        """Every nomination, grouped by category, ranked by average jury score.
        Read-only — this is the tool the secretariat uses to *decide* winners.
        The category dropdown filter (?category=<id>) narrows the list.
        """
        category_id = request.GET.get('category')
        categories = Category.objects.all().order_by('order', 'name')
        selected_category = None
        if category_id:
            selected_category = categories.filter(pk=category_id).first()

        groups = []
        cats_to_show = [selected_category] if selected_category else categories
        for cat in cats_to_show:
            noms = list(cat.nominations.filter(is_visible_to_jury=True))
            ranked = sorted(
                noms,
                key=lambda n: (n.average_score() is None, -(n.average_score() or 0)),
            )
            if ranked:
                groups.append({'category': cat, 'nominations': ranked})

        context = dict(
            self.admin_site.each_context(request),
            title='Rankings — by Average Jury Score',
            groups=groups,
            categories=categories,
            selected_category=selected_category,
            opts=self.model._meta,
        )
        return TemplateResponse(request, 'admin/awards/rankings.html', context)

    def winners_view(self, request):
        """Only nominations that already have an award_tier set — the
        published-looking final results list, grouped by category."""
        categories = Category.objects.all().order_by('order', 'name')
        tier_order = {code: i for i, (code, _label) in enumerate(Nomination.AWARD_TIER_CHOICES)}

        groups = []
        for cat in categories:
            noms = list(
                cat.nominations.filter(is_visible_to_jury=True).exclude(award_tier='')
            )
            noms.sort(key=lambda n: tier_order.get(n.award_tier, 99))
            if noms:
                groups.append({'category': cat, 'nominations': noms})

        context = dict(
            self.admin_site.each_context(request),
            title='Winners List',
            groups=groups,
            opts=self.model._meta,
        )
        return TemplateResponse(request, 'admin/awards/winners.html', context)