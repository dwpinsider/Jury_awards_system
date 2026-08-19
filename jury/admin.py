import csv

from django.contrib import admin
from django.http import HttpResponse
from django.urls import path
from django.template.response import TemplateResponse

from .models import JuryReview, RecentlyViewed


def export_reviews_as_csv(modeladmin, request, queryset):
    """Admin action: exports the selected JuryReview rows to a CSV file."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="jury_reviews.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Juror Name', 'Juror Email', 'Category', 'Nomination (Organization)',
        'Achievement (/10, 35% weight)', 'Methodology (/10, 20% weight)',
        'Creativity (/10, 10% weight)', 'Execution (/10, 35% weight)',
        'Total (/100)', 'Submitted', 'Submitted At', 'Comments',
    ])

    reviews = queryset.select_related('juror', 'nomination', 'nomination__category').order_by(
        'nomination__category__name', 'nomination__organization_name', 'juror__full_name'
    )
    for review in reviews:
        writer.writerow([
            review.juror.full_name,
            review.juror.email,
            review.nomination.category.name,
            review.nomination.organization_name,
            review.achievement_score,
            review.methodology_score,
            review.creativity_score,
            review.execution_score,
            review.total_score(),
            'Yes' if review.is_submitted else 'No',
            review.submitted_at.strftime('%Y-%m-%d %H:%M') if review.submitted_at else '',
            review.comments,
        ])

    return response


export_reviews_as_csv.short_description = 'Export selected reviews to CSV'


@admin.register(JuryReview)
class JuryReviewAdmin(admin.ModelAdmin):
    change_list_template = 'admin/jury/juryreview_change_list.html'
    list_display = (
        'juror', 'nomination', 'achievement_score', 'methodology_score',
        'creativity_score', 'execution_score', 'total_score', 'is_submitted', 'submitted_at',
    )
    list_filter = ('is_submitted', 'nomination__category')
    search_fields = ('juror__full_name', 'juror__email', 'nomination__organization_name')
    readonly_fields = ('submitted_at', 'created_at', 'updated_at')
    actions = [export_reviews_as_csv]

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('scoring-guide/', self.admin_site.admin_view(self.scoring_guide_view), name='jury_juryreview_scoring_guide'),
        ]
        return custom + urls

    def scoring_guide_view(self, request):
        """Admin-only reference page explaining the scoring rubric and
        weights — this is intentionally NOT shown to jurors."""
        rows = [
            {'label': 'Achievement and Outcome', 'weight': 35, 'multiplier': JuryReview.WEIGHT_ACHIEVEMENT},
            {'label': 'Methodology of the Service / Project', 'weight': 20, 'multiplier': JuryReview.WEIGHT_METHODOLOGY},
            {'label': 'Creativity and Innovation', 'weight': 10, 'multiplier': JuryReview.WEIGHT_CREATIVITY},
            {'label': 'Execution of the Service / Project', 'weight': 35, 'multiplier': JuryReview.WEIGHT_EXECUTION},
        ]
        context = dict(
            self.admin_site.each_context(request),
            title='Scoring Guide',
            rows=rows,
            score_min=JuryReview.SCORE_MIN,
            score_max=JuryReview.SCORE_MAX,
            opts=self.model._meta,
        )
        return TemplateResponse(request, 'admin/jury/scoring_guide.html', context)


@admin.register(RecentlyViewed)
class RecentlyViewedAdmin(admin.ModelAdmin):
    list_display = ('juror', 'nomination', 'viewed_at')
    list_filter = ('juror',)