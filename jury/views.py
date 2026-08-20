from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone

from awards.models import Category, Nomination
from .decorators import juror_required
from .forms import JuryReviewForm
from .models import JuryReview, RecentlyViewed

def _score_distribution(scores):
    """Buckets a list of total_score() values (0-100) into 4 ranges for the
    dashboard's mini bar chart. Returns a list of dicts with a pre-computed
    bar height percentage so the template stays simple."""
    buckets = [
        {'label': '0–40', 'min': 0, 'max': 40, 'count': 0},
        {'label': '40–60', 'min': 40, 'max': 60, 'count': 0},
        {'label': '60–80', 'min': 60, 'max': 80, 'count': 0},
        {'label': '80–100', 'min': 80, 'max': 101, 'count': 0},
    ]
    for score in scores:
        for bucket in buckets:
            if bucket['min'] <= score < bucket['max']:
                bucket['count'] += 1
                break
    highest = max((b['count'] for b in buckets), default=0)
    for bucket in buckets:
        bucket['height_pct'] = round((bucket['count'] / highest) * 100) if highest else 0
    return buckets


@juror_required
def dashboard(request):
    juror = request.juror
    categories = juror.categories_queryset().filter(is_open_for_judging=True).annotate(
        total=Count('nominations', filter=Q(nominations__is_visible_to_jury=True), distinct=True),
        reviewed=Count(
            'nominations__jury_reviews',
            filter=Q(
                nominations__is_visible_to_jury=True,
                nominations__jury_reviews__juror=juror,
                nominations__jury_reviews__is_submitted=True,
            ),
            distinct=True,
        ),
    )
    for cat in categories:
        cat.pending = max(cat.total - cat.reviewed, 0)

    # Scope BOTH total_nominations and submitted_count to the exact same
    # nomination set — only nominations in categories currently assigned to
    # and open for this juror. Previously submitted_count counted every
    # review the juror had ever submitted, with no such scoping, so a
    # review left over from a category that's since closed (or been
    # unassigned from them) would silently deflate "Pending" below its
    # true value.
    visible_nominations = Nomination.objects.filter(category__in=categories, is_visible_to_jury=True)
    total_nominations = visible_nominations.count()
    submitted_reviews = JuryReview.objects.filter(
        juror=juror, is_submitted=True, nomination__in=visible_nominations
    )
    submitted_count = submitted_reviews.count()
    pending_count = max(total_nominations - submitted_count, 0)
    progress_pct = round((submitted_count / total_nominations) * 100) if total_nominations else 0

    score_distribution = _score_distribution([r.total_score() for r in submitted_reviews])

    recent = RecentlyViewed.objects.filter(juror=juror).select_related(
        'nomination', 'nomination__category'
    )[:RecentlyViewed.MAX_PER_JUROR]

    # Earliest upcoming deadline among this juror's open categories
    upcoming_deadline = None
    deadline_category = None
    now = timezone.now()
    for cat in categories.exclude(judging_deadline__isnull=True).order_by('judging_deadline'):
        if cat.judging_deadline and cat.judging_deadline > now:
            upcoming_deadline = cat.judging_deadline
            deadline_category = cat
            break
    days_left = (upcoming_deadline - now).days if upcoming_deadline else None

    context = {
        'juror': juror,
        'categories': categories,
        'category_count': categories.count(),
        'total_nominations': total_nominations,
        'submitted_count': submitted_count,
        'pending_count': pending_count,
        'progress_pct': progress_pct,
        'score_distribution': score_distribution,
        'has_submitted_reviews': submitted_count > 0,
        'recent_views': recent,
        'upcoming_deadline': upcoming_deadline,
        'deadline_category': deadline_category,
        'days_left': days_left,
    }
    return render(request, 'jury/dashboard.html', context)


@juror_required
def category_list(request):
    juror = request.juror
    categories = juror.categories_queryset().filter(is_open_for_judging=True).annotate(
        total=Count('nominations', filter=Q(nominations__is_visible_to_jury=True), distinct=True),
        reviewed=Count(
            'nominations__jury_reviews',
            filter=Q(
                nominations__is_visible_to_jury=True,
                nominations__jury_reviews__juror=juror,
                nominations__jury_reviews__is_submitted=True,
            ),
            distinct=True,
        ),
    )

    level = request.GET.get('level', 'all')
    if level in (Category.LEVEL_INDIVIDUAL, Category.LEVEL_ORGANIZATIONAL):
        categories = categories.filter(level=level)
    else:
        level = 'all'

    sector = request.GET.get('sector', 'all')
    if sector in (Category.SECTOR_PUBLIC, Category.SECTOR_PRIVATE):
        categories = categories.filter(sector=sector)
    else:
        sector = 'all'

    categories = categories.order_by('order', 'name')
    # pending isn't something the DB can annotate directly (it's total -
    # reviewed), so compute it in Python after the query runs.
    for cat in categories:
        cat.pending = max(cat.total - cat.reviewed, 0)

    return render(request, 'jury/category_list.html', {
        'juror': juror,
        'categories': categories,
        'active_level': level,
        'active_sector': sector,
    })


@juror_required
def nomination_list(request, slug):
    juror = request.juror
    category = get_object_or_404(juror.categories_queryset(), slug=slug, is_open_for_judging=True)
    nominations = category.nominations.filter(is_visible_to_jury=True).order_by('organization_name')

    reviewed_ids = set(
        JuryReview.objects.filter(juror=juror, nomination__in=nominations, is_submitted=True)
        .values_list('nomination_id', flat=True)
    )

    return render(request, 'jury/nomination_list.html', {
        'juror': juror,
        'category': category,
        'nominations': nominations,
        'reviewed_ids': reviewed_ids,
    })


@juror_required
def search_nominations(request):
    """Search by organization name, nominee name, or category name — across
    every category this juror has access to (not just one at a time)."""
    juror = request.juror
    query = request.GET.get('q', '').strip()
    results = []

    if query:
        nominations = Nomination.objects.filter(
            category__in=juror.categories_queryset(),
            is_visible_to_jury=True,
        ).filter(
            Q(organization_name__icontains=query)
            | Q(nominee_full_name__icontains=query)
            | Q(category__name__icontains=query)
        ).select_related('category').order_by('category__name', 'organization_name')

        reviewed_ids = set(
            JuryReview.objects.filter(juror=juror, nomination__in=nominations, is_submitted=True)
            .values_list('nomination_id', flat=True)
        )
        results = [{'nomination': n, 'reviewed': n.id in reviewed_ids} for n in nominations]

    return render(request, 'jury/search_results.html', {
        'juror': juror,
        'query': query,
        'results': results,
    })


@juror_required
def nomination_detail(request, pk):
    juror = request.juror
    nomination = get_object_or_404(
        Nomination, pk=pk, category__in=juror.categories_queryset(), is_visible_to_jury=True
    )
    existing_review = JuryReview.objects.filter(juror=juror, nomination=nomination).first()

    RecentlyViewed.record(juror, nomination)

    all_documents = list(nomination.documents.all())
    video_documents = [d for d in all_documents if d.file_type() in ('video', 'external_video')]
    image_documents = [d for d in all_documents if d.file_type() == 'image']
    other_documents = [d for d in all_documents if d.file_type() not in ('video', 'external_video', 'image')]

    return render(request, 'jury/nomination_detail.html', {
        'juror': juror,
        'nomination': nomination,
        'category': nomination.category,
        'stats': nomination.stats.all(),
        'video_documents': video_documents,
        'image_documents': image_documents,
        'other_documents': other_documents,
        'media_count': len(video_documents) + len(image_documents) + len(other_documents),
        'existing_review': existing_review,
        'judging_closed': not nomination.category.is_judging_open(),
        'form': JuryReviewForm(instance=existing_review),
    })


@juror_required
def submit_review(request, pk):
    juror = request.juror
    nomination = get_object_or_404(
        Nomination, pk=pk, category__in=juror.categories_queryset(), is_visible_to_jury=True
    )

    if not nomination.category.is_judging_open():
        messages.error(
            request,
            f'Judging for "{nomination.category.name}" has closed'
            + (f' (deadline was {nomination.category.judging_deadline:%d %b %Y, %H:%M}).' if nomination.category.judging_deadline else '.')
            + ' Scores can no longer be submitted or changed for this category.',
        )
        return redirect('jury:nomination_detail', pk=nomination.pk)

    instance = JuryReview.objects.filter(juror=juror, nomination=nomination).first()

    if request.method == 'POST':
        form = JuryReviewForm(request.POST, instance=instance)
        if form.is_valid():
            review = form.save(commit=False)
            review.juror = juror
            review.nomination = nomination

            action = request.POST.get('action', 'save')
            if action == 'submit':
                review.save()
                review.mark_submitted()
                messages.success(
                    request,
                    f'Your review for "{nomination.organization_name}" has been submitted. '
                    f'Total score: {review.total_score()}/100.',
                )
                return redirect('jury:nomination_list', slug=nomination.category.slug)
            else:
                review.save()
                messages.success(request, 'Your scores have been saved as a draft.')
                return redirect('jury:submit_review', pk=nomination.pk)
    else:
        form = JuryReviewForm(instance=instance)

    return render(request, 'jury/review_form.html', {
        'juror': juror,
        'nomination': nomination,
        'category': nomination.category,
        'form': form,
        'existing_review': instance,
    })


@juror_required
def my_reviews(request):
    juror = request.juror
    reviews = JuryReview.objects.filter(juror=juror, is_submitted=True).select_related(
        'nomination', 'nomination__category'
    ).order_by('nomination__category__name', 'nomination__organization_name')

    scored = [r.total_score() for r in reviews]
    overall_average = round(sum(scored) / len(scored), 2) if scored else None

    return render(request, 'jury/my_reviews.html', {
        'juror': juror,
        'reviews': reviews,
        'overall_average': overall_average,
        'submitted_count': len(scored),
    })