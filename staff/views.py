from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Avg, F

from awards.models import Category, Nomination
from jury.models import JuryReview, RecentlyViewed
from .forms import ResultForm


def _staff_required(view_func):
    """Same gate as Django admin (must be logged in AND is_staff=True), but
    keeps people on this friendly portal instead of bouncing them into
    /admin/ if they're not authorized."""
    return staff_member_required(view_func, login_url='staff:login')


@_staff_required
def nominations(request):
    """Every nomination, across every category — the main landing page."""
    qs = Nomination.objects.filter(is_visible_to_jury=True).select_related('category').order_by(
        'category__name', 'organization_name'
    )

    query = request.GET.get('q', '').strip()
    if query:
        qs = qs.filter(
            Q(organization_name__icontains=query)
            | Q(nominee_full_name__icontains=query)
            | Q(category__name__icontains=query)
        )

    category_id = request.GET.get('category')
    if category_id:
        qs = qs.filter(category_id=category_id)

    rows = [{'nomination': n, 'avg_score': n.average_score(), 'review_count': n.review_count()} for n in qs]

    return render(request, 'staff/nominations.html', {
        'rows': rows,
        'categories': Category.objects.all().order_by('order', 'name'),
        'query': query,
        'selected_category': category_id,
    })


@_staff_required
def rankings(request):
    """Every nomination, grouped by category, ranked by average jury score."""
    category_id = request.GET.get('category')
    categories = Category.objects.all().order_by('order', 'name')

    if category_id:
        categories = categories.filter(pk=category_id)

    groups = []
    for cat in categories:
        noms = list(cat.nominations.filter(is_visible_to_jury=True))
        scored = [(n, n.average_score(), n.review_count()) for n in noms]
        scored.sort(key=lambda item: (item[1] is None, -(item[1] or 0)))
        if scored:
            groups.append({'category': cat, 'nominations': scored})

    return render(request, 'staff/rankings.html', {
        'groups': groups,
        'all_categories': Category.objects.all().order_by('order', 'name'),
        'selected_category': category_id,
    })


@_staff_required
def winners(request):
    """Only nominations that already have an award_tier set, grouped by category."""
    categories = Category.objects.all().order_by('order', 'name')
    tier_order = {tier: i for i, (tier, _label) in enumerate(Nomination.AWARD_TIER_CHOICES)}

    groups = []
    for cat in categories:
        winners_qs = list(
            cat.nominations.filter(is_visible_to_jury=True).exclude(award_tier='').exclude(award_tier__isnull=True)
        )
        winners_qs.sort(key=lambda n: tier_order.get(n.award_tier, 999))
        if winners_qs:
            groups.append({'category': cat, 'nominations': winners_qs})

    return render(request, 'staff/winners.html', {'groups': groups})


@_staff_required
def analytics(request):
    """High-level completion + workload dashboard."""
    from accounts.models import Juror

    categories = Category.objects.all().order_by('order', 'name')
    all_nominations = Nomination.objects.filter(is_visible_to_jury=True)
    active_jurors = Juror.objects.filter(is_active=True)
    submitted_reviews = JuryReview.objects.filter(is_submitted=True)

    total_categories = categories.count()
    total_nominations = all_nominations.count()
    total_jurors = active_jurors.count()
    total_reviews_submitted = submitted_reviews.count()

    possible_assignments = 0
    for juror in active_jurors:
        juror_categories = juror.categories_queryset().filter(is_open_for_judging=True)
        possible_assignments += Nomination.objects.filter(
            category__in=juror_categories, is_visible_to_jury=True
        ).count()
    overall_completion_pct = (
        round((total_reviews_submitted / possible_assignments) * 100) if possible_assignments else 0
    )

    category_rows = []
    for cat in categories:
        cat_noms = cat.nominations.filter(is_visible_to_jury=True)
        cat_nom_count = cat_noms.count()
        cat_reviews = submitted_reviews.filter(nomination__in=cat_noms).count()
        avg = submitted_reviews.filter(nomination__in=cat_noms).aggregate(
            avg=Avg(
                F('achievement_score') * 3.5 + F('methodology_score') * 2.0
                + F('creativity_score') * 1.0 + F('execution_score') * 3.5
            )
        )['avg']
        category_rows.append({
            'category': cat, 'nomination_count': cat_nom_count,
            'review_count': cat_reviews, 'avg_score': round(avg, 1) if avg is not None else None,
        })

    juror_rows = []
    for juror in active_jurors:
        juror_categories = juror.categories_queryset().filter(is_open_for_judging=True)
        assigned = Nomination.objects.filter(category__in=juror_categories, is_visible_to_jury=True).count()
        done = submitted_reviews.filter(juror=juror).count()
        juror_rows.append({
            'juror': juror, 'assigned': assigned, 'done': done,
            'pct': round((done / assigned) * 100) if assigned else 0,
        })
    juror_rows.sort(key=lambda r: r['pct'])

    top_nominations = sorted(
        [n for n in all_nominations if n.review_count() > 0],
        key=lambda n: n.average_score() or 0, reverse=True,
    )[:10]

    return render(request, 'staff/analytics.html', {
        'total_categories': total_categories, 'total_nominations': total_nominations,
        'total_jurors': total_jurors, 'total_reviews_submitted': total_reviews_submitted,
        'possible_assignments': possible_assignments, 'overall_completion_pct': overall_completion_pct,
        'category_rows': category_rows, 'juror_rows': juror_rows, 'top_nominations': top_nominations,
    })


@_staff_required
def scorecard(request, pk):
    """One nomination's full jury scorecard: overall gauge + every
    individual juror's score breakdown and comments."""
    nomination = get_object_or_404(Nomination, pk=pk)
    reviews = JuryReview.objects.filter(
        nomination=nomination, is_submitted=True
    ).select_related('juror').order_by('-submitted_at')
    reviews = sorted(reviews, key=lambda r: r.total_score(), reverse=True)
    for r in reviews:
        r.achievement_pct = (r.achievement_score or 0) * 10
        r.methodology_pct = (r.methodology_score or 0) * 10
        r.creativity_pct = (r.creativity_score or 0) * 10
        r.execution_pct = (r.execution_score or 0) * 10

    overall = nomination.average_score()
    overall_pct = round(overall) if overall is not None else 0

    return render(request, 'staff/scorecard.html', {
        'nomination': nomination, 'reviews': reviews,
        'overall': overall, 'overall_pct': overall_pct,
    })


@_staff_required
def jury_reviews(request):
    """Every submitted jury review, across every juror and nomination —
    a flat audit list, filterable by juror or category."""
    qs = JuryReview.objects.filter(is_submitted=True).select_related(
        'juror', 'nomination', 'nomination__category'
    ).order_by('-submitted_at')

    juror_id = request.GET.get('juror')
    if juror_id:
        qs = qs.filter(juror_id=juror_id)

    category_id = request.GET.get('category')
    if category_id:
        qs = qs.filter(nomination__category_id=category_id)

    from accounts.models import Juror
    return render(request, 'staff/jury_reviews.html', {
        'reviews': qs,
        'jurors': Juror.objects.filter(is_active=True).order_by('full_name'),
        'categories': Category.objects.all().order_by('order', 'name'),
        'selected_juror': juror_id,
        'selected_category': category_id,
    })


@_staff_required
def recently_viewed(request):
    """A live feed of which nominations jurors have been looking at
    recently, across the whole panel — not scoped to one juror."""
    recent = RecentlyViewed.objects.select_related(
        'juror', 'nomination', 'nomination__category'
    ).order_by('-viewed_at')[:60]

    return render(request, 'staff/recently_viewed.html', {'recent': recent})


@_staff_required
def edit_result(request, pk):
    """Focused edit screen for exactly one thing: this nomination's
    declared result (award_tier) + an optional internal note. Reachable
    from both the Rankings and Winners pages."""
    nomination = get_object_or_404(Nomination, pk=pk)

    if request.method == 'POST':
        form = ResultForm(request.POST, instance=nomination)
        if form.is_valid():
            form.save()
            messages.success(request, f'Result updated for "{nomination.organization_name}".')
            next_url = request.POST.get('next') or 'staff:rankings'
            return redirect(next_url)
    else:
        form = ResultForm(instance=nomination)

    return render(request, 'staff/edit_result.html', {
        'nomination': nomination,
        'form': form,
        'next': request.GET.get('next', ''),
    })


@_staff_required
def jurors(request):
    """Every active juror, with their assigned/completed workload — the
    actual people, not just their submitted reviews (that's Jury Reviews)."""
    from accounts.models import Juror

    query = request.GET.get('q', '').strip()
    jurors_qs = Juror.objects.filter(is_active=True).order_by('full_name')
    if query:
        jurors_qs = jurors_qs.filter(
            Q(full_name__icontains=query) | Q(email__icontains=query) | Q(organization__icontains=query)
        )

    rows = []
    for juror in jurors_qs:
        juror_categories = juror.categories_queryset().filter(is_open_for_judging=True)
        assigned = Nomination.objects.filter(category__in=juror_categories, is_visible_to_jury=True).count()
        done = JuryReview.objects.filter(juror=juror, is_submitted=True).count()
        rows.append({
            'juror': juror,
            'assigned': assigned,
            'done': done,
            'pct': round((done / assigned) * 100) if assigned else 0,
        })

    return render(request, 'staff/jurors.html', {'rows': rows, 'query': query})