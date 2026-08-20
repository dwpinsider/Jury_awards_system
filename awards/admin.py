from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.db.models import Q
from django.core.exceptions import PermissionDenied
import csv
from django.http import HttpResponse

from .models import Category, Nomination, NominationStat, NominationDocument
from .forms import CSVUploadForm
from .csv_import import (
    import_categories_from_csv, import_nominations_from_csv,
    CATEGORY_CSV_COLUMNS, NOMINATION_CSV_COLUMNS,
)


def _require_perm(request, perm):
    """Raises PermissionDenied (-> Django's standard 403 page) unless the
    logged-in user has this specific permission. Needed because our custom
    admin pages (Rankings, Winners, Analytics, Scorecard, CSV import) sit
    outside Django's normal per-model permission checks — admin_view() only
    confirms the user is staff, not that they hold any particular permission."""
    if not request.user.has_perm(perm):
        raise PermissionDenied


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
    list_display = ('name', 'level', 'sector', 'is_open_for_judging', 'judging_deadline', 'nomination_count', 'order')
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
        _require_perm(request, 'awards.add_category')
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
        'is_visible_to_jury', 'review_count', 'average_score', 'scorecard_link', 'created_at',
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

    @admin.display(description='Scorecard')
    def scorecard_link(self, obj):
        from django.utils.html import format_html
        from django.urls import reverse
        url = reverse('admin:awards_nomination_scorecard', args=[obj.pk])
        return format_html('<a href="{}">View Scorecard</a>', url)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='awards_nomination_import_csv'),
            path('rankings/', self.admin_site.admin_view(self.rankings_view), name='awards_nomination_rankings'),
            path('winners/', self.admin_site.admin_view(self.winners_view), name='awards_nomination_winners'),
            path('analytics/', self.admin_site.admin_view(self.analytics_view), name='awards_nomination_analytics'),
            path('<int:pk>/scorecard/', self.admin_site.admin_view(self.scorecard_view), name='awards_nomination_scorecard'),
        ]
        return custom + urls

    def scorecard_view(self, request, pk):
        """Admin-only visual scorecard for one nomination: overall gauge +
        every juror's individual review with per-criterion bars and
        comments. Jurors have no way to reach this — it lives entirely
        under /admin/, which they have no login for."""
        _require_perm(request, 'awards.view_nomination')
        from django.shortcuts import get_object_or_404
        from jury.models import JuryReview

        nomination = get_object_or_404(Nomination, pk=pk)
        reviews = JuryReview.objects.filter(
            nomination=nomination, is_submitted=True
        ).select_related('juror').order_by('-submitted_at')
        # total_score() is a computed Python property, not a DB field, so
        # sort in Python (highest score first) after fetching.
        reviews = sorted(reviews, key=lambda r: r.total_score(), reverse=True)
        # Precompute bar-width percentages (score is 0-10, bar wants 0-100)
        # rather than doing string-concatenation math in the template.
        for r in reviews:
            r.achievement_pct = (r.achievement_score or 0) * 10
            r.methodology_pct = (r.methodology_score or 0) * 10
            r.creativity_pct = (r.creativity_score or 0) * 10
            r.execution_pct = (r.execution_score or 0) * 10

        overall = nomination.average_score()
        overall_pct = round(overall) if overall is not None else 0

        context = dict(
            self.admin_site.each_context(request),
            title=f'Jury Scorecard — {nomination.organization_name}',
            nomination=nomination,
            reviews=reviews,
            overall=overall,
            overall_pct=overall_pct,
            opts=self.model._meta,
        )
        return TemplateResponse(request, 'admin/awards/nomination_scorecard.html', context)

    def import_csv(self, request):
        _require_perm(request, 'awards.add_nomination')
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
        _require_perm(request, 'awards.view_nomination')
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
        _require_perm(request, 'awards.view_nomination')
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

    def analytics_view(self, request):
        """High-level management dashboard: overall completion, per-category
        completion, per-juror workload, and a leaderboard of top-scoring
        nominations. Read-only."""
        _require_perm(request, 'awards.view_nomination')
        from django.db.models import Avg, Count as DCount, F, Q as DQ
        from accounts.models import Juror
        from jury.models import JuryReview

        categories = Category.objects.all().order_by('order', 'name')
        nominations = Nomination.objects.filter(is_visible_to_jury=True)
        jurors = Juror.objects.filter(is_active=True)
        submitted_reviews = JuryReview.objects.filter(is_submitted=True)

        total_categories = categories.count()
        total_nominations = nominations.count()
        total_jurors = jurors.count()
        total_reviews_submitted = submitted_reviews.count()

        # How many (juror, nomination) review assignments *could* exist, so we
        # can show overall % complete rather than just a raw count.
        possible_assignments = 0
        for juror in jurors:
            juror_categories = juror.categories_queryset().filter(is_open_for_judging=True)
            possible_assignments += Nomination.objects.filter(
                category__in=juror_categories, is_visible_to_jury=True
            ).count()
        overall_completion_pct = (
            round((total_reviews_submitted / possible_assignments) * 100) if possible_assignments else 0
        )

        # Per-category completion
        category_rows = []
        for cat in categories:
            cat_noms = cat.nominations.filter(is_visible_to_jury=True)
            cat_nom_count = cat_noms.count()
            cat_reviews = submitted_reviews.filter(nomination__in=cat_noms).count()
            # Weighted total, matching JuryReview.total_score() — NOT a plain
            # sum of the four raw 0-10 fields (that would only max out at 40).
            avg = submitted_reviews.filter(nomination__in=cat_noms).aggregate(
                avg=Avg(
                    F('achievement_score') * 3.5
                    + F('methodology_score') * 2.0
                    + F('creativity_score') * 1.0
                    + F('execution_score') * 3.5
                )
            )['avg']
            category_rows.append({
                'category': cat,
                'nomination_count': cat_nom_count,
                'review_count': cat_reviews,
                'avg_score': round(avg, 1) if avg is not None else None,
            })

        # Per-juror workload
        juror_rows = []
        for juror in jurors:
            juror_categories = juror.categories_queryset().filter(is_open_for_judging=True)
            assigned = Nomination.objects.filter(category__in=juror_categories, is_visible_to_jury=True).count()
            done = submitted_reviews.filter(juror=juror).count()
            juror_rows.append({
                'juror': juror,
                'assigned': assigned,
                'done': done,
                'pct': round((done / assigned) * 100) if assigned else 0,
            })
        juror_rows.sort(key=lambda r: r['pct'])  # least-complete first, easiest to spot who needs a nudge

        # Top 10 highest-scoring nominations overall (submitted reviews only)
        top_nominations = sorted(
            [n for n in nominations if n.review_count() > 0],
            key=lambda n: n.average_score() or 0,
            reverse=True,
        )[:10]

        context = dict(
            self.admin_site.each_context(request),
            title='Analytics',
            total_categories=total_categories,
            total_nominations=total_nominations,
            total_jurors=total_jurors,
            total_reviews_submitted=total_reviews_submitted,
            possible_assignments=possible_assignments,
            overall_completion_pct=overall_completion_pct,
            category_rows=category_rows,
            juror_rows=juror_rows,
            top_nominations=top_nominations,
            opts=self.model._meta,
        )
        return TemplateResponse(request, 'admin/awards/analytics.html', context)