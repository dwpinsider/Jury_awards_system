import os

from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils.text import slugify


class Category(models.Model):
    LEVEL_INDIVIDUAL = 'individual'
    LEVEL_ORGANIZATIONAL = 'organizational'
    LEVEL_CHOICES = [
        (LEVEL_INDIVIDUAL, 'Individual Category'),
        (LEVEL_ORGANIZATIONAL, 'Organizational Level Category'),
    ]

    SECTOR_PUBLIC = 'public'
    SECTOR_PRIVATE = 'private'
    SECTOR_NA = 'na'
    SECTOR_CHOICES = [
        (SECTOR_PUBLIC, 'Public & Government Sector'),
        (SECTOR_PRIVATE, 'Private Sector'),
        (SECTOR_NA, 'Not sector-specific'),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default=LEVEL_INDIVIDUAL)
    sector = models.CharField(max_length=10, choices=SECTOR_CHOICES, default=SECTOR_NA)
    description = models.TextField(blank=True)
    is_open_for_judging = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:255]
        super().save(*args, **kwargs)

    def nomination_count(self):
        return self.nominations.count()


class Nomination(models.Model):
    """A submitted entry/company nomination within a category.

    This mirrors the fields captured on the public registration form / PDF
    that the admin imports for jury review.
    """

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='nominations')

    # Organization / submitter details
    organization_name = models.CharField(max_length=255)
    sector = models.CharField(max_length=255, blank=True, help_text="e.g. 'Government Sector'")
    city_country = models.CharField(max_length=255, blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    designation = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    mobile_number = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)

    # Nominee details (for individual awards)
    nominee_full_name = models.CharField(max_length=255, blank=True)
    nominee_job_title = models.CharField(max_length=255, blank=True)
    nominee_address = models.CharField(max_length=255, blank=True)
    employee_headcount = models.PositiveIntegerField(blank=True, null=True)

    # Narrative fields (from the PDF submission)
    project_title = models.CharField(max_length=255, blank=True)
    project_highlights = models.TextField(blank=True)
    key_achievements = models.TextField(blank=True)
    reason_for_nomination = models.TextField(blank=True)
    business_impact = models.TextField(blank=True)

    reference_code = models.CharField(max_length=50, blank=True, help_text='Internal tracking code, optional')
    is_visible_to_jury = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['organization_name']

    def __str__(self):
        return f'{self.organization_name} — {self.category.name}'

    def average_score(self):
        reviews = self.jury_reviews.all()
        if not reviews:
            return None
        return round(sum(r.total_score() for r in reviews) / len(reviews), 2)

    def review_count(self):
        return self.jury_reviews.count()


class NominationStat(models.Model):
    """Row of the 'Project Performance Results & Statistics' table, e.g.
    Area = 'Learning Participation', Value = 'approximately 97%'."""

    nomination = models.ForeignKey(Nomination, on_delete=models.CASCADE, related_name='stats')
    area = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.area}: {self.value}'


ALLOWED_DOCUMENT_EXTENSIONS = ['pdf', 'gif', 'jpg', 'jpeg', 'png', 'mov', 'mp4']

IMAGE_EXTENSIONS = {'gif', 'jpg', 'jpeg', 'png'}
VIDEO_EXTENSIONS = {'mov', 'mp4'}


class NominationDocument(models.Model):
    """Supporting file(s) uploaded for a nomination — shown to the jury as a
    clickable link (or thumbnail, for images). Accepts PDF, images
    (gif/jpg/jpeg/png), and video (mov/mp4)."""

    nomination = models.ForeignKey(Nomination, on_delete=models.CASCADE, related_name='documents')
    label = models.CharField(max_length=255, default='Supporting Document')
    file = models.FileField(
        upload_to='nominations/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS)],
        help_text='Accepted formats: PDF, GIF, JPEG, PNG, MOV, MP4.',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.label} — {self.nomination.organization_name}'

    def extension(self):
        return os.path.splitext(self.file.name)[1].lower().lstrip('.')

    def file_type(self):
        ext = self.extension()
        if ext in IMAGE_EXTENSIONS:
            return 'image'
        if ext in VIDEO_EXTENSIONS:
            return 'video'
        if ext == 'pdf':
            return 'pdf'
        return 'other'