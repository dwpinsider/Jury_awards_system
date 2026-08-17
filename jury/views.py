from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Q

from awards.models import Category, Nomination
from .decorators import juror_required
from .forms import JuryReviewForm
from .models import JuryReview


@juror_required
def dashboard(request):
    juror = request.juror
    categories = juror.categories_queryset().filter(is_open_for_judging=True)

    total_nominations = Nomination.objects.filter(
        category__in=categories, is_visible_to_jury=True
    ).count()
    reviews = JuryReview.objects.filter(juror=juror)
    submitted_count = reviews.filter(is_submitted=True).count()

    context = {
        'juror': juror,
        'categories': categories,
        'category_count': categories.count(),
        'total_nominations': total_nominations,
        'submitted_count': submitted_count,
        'pending_count': max(total_nominations - submitted_count, 0),
    }
    return render(request, 'jury/dashboard.html', context)


@juror_required
def category_list(request):
    juror = request.juror
    categories = juror.categories_queryset().filter(is_open_for_judging=True).annotate(
        total=Count('nominations', filter=Q(nominations__is_visible_to_jury=True))
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
def nomination_detail(request, pk):
    juror = request.juror
    nomination = get_object_or_404(
        Nomination, pk=pk, category__in=juror.categories_queryset(), is_visible_to_jury=True
    )
    existing_review = JuryReview.objects.filter(juror=juror, nomination=nomination).first()

    all_documents = list(nomination.documents.all())
    video_documents = [d for d in all_documents if d.file_type() == 'video']
    image_documents = [d for d in all_documents if d.file_type() == 'image']
    other_documents = [d for d in all_documents if d.file_type() not in ('video', 'image')]

    return render(request, 'jury/nomination_detail.html', {
        'juror': juror,
        'nomination': nomination,
        'category': nomination.category,
        'stats': nomination.stats.all(),
        'video_documents': video_documents,
        'image_documents': image_documents,
        'other_documents': other_documents,
        'existing_review': existing_review,
    })


@juror_required
def submit_review(request, pk):
    juror = request.juror
    nomination = get_object_or_404(
        Nomination, pk=pk, category__in=juror.categories_queryset(), is_visible_to_jury=True
    )
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