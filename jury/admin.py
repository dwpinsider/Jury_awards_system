import csv

from django.contrib import admin
from django.http import HttpResponse

from .models import JuryReview, RecentlyViewed


def export_reviews_as_csv(modeladmin, request, queryset):
    """Admin action: exports the selected JuryReview rows to a CSV file."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="jury_reviews.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Juror Name', 'Juror Email', 'Category', 'Nomination (Organization)',
        'Achievement (/35)', 'Methodology (/20)', 'Creativity (/10)', 'Execution (/35)',
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
    list_display = ('juror', 'nomination', 'total_score', 'is_submitted', 'submitted_at')
    list_filter = ('is_submitted', 'nomination__category')
    search_fields = ('juror__full_name', 'juror__email', 'nomination__organization_name')
    readonly_fields = ('submitted_at', 'created_at', 'updated_at')
    actions = [export_reviews_as_csv]


@admin.register(RecentlyViewed)
class RecentlyViewedAdmin(admin.ModelAdmin):
    list_display = ('juror', 'nomination', 'viewed_at')
    list_filter = ('juror',)