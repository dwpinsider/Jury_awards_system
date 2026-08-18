import os
import re

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
    judging_deadline = models.DateTimeField(
        blank=True, null=True,
        help_text='Optional. After this date/time, jurors can no longer submit or update scores for this category — enforced automatically, not just advisory.',
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def is_judging_open(self):
        """True if the category is marked open AND (no deadline, or deadline hasn't passed)."""
        if not self.is_open_for_judging:
            return False
        if self.judging_deadline:
            from django.utils import timezone
            if timezone.now() >= self.judging_deadline:
                return False
        return True

    def tag_level_label(self):
        """Short version of get_level_display() — for compact card badges only.
        The full phrase ('Organizational Level Category') is too wide to fit
        as a single-line pill in a normal-width card."""
        return 'Organizational' if self.level == self.LEVEL_ORGANIZATIONAL else 'Individual'

    def tag_sector_label(self):
        """Short version of get_sector_display() — for compact card badges only."""
        if self.sector == self.SECTOR_PUBLIC:
            return 'Public & Government'
        if self.sector == self.SECTOR_PRIVATE:
            return 'Private Sector'
        return None

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

    AWARD_TIER_CHOICES = [
        ('', 'Not decided yet'),
        ('winner', 'Winner'),
        ('gold', 'Gold'),
        ('silver', 'Silver'),
        ('bronze', 'Bronze'),
        ('finalist', 'Finalist'),
        ('shortlisted', 'Shortlisted'),
    ]
    award_tier = models.CharField(
        max_length=20, choices=AWARD_TIER_CHOICES, blank=True, default='',
        help_text='Set once the secretariat has decided the result for this nomination.',
    )
    award_notes = models.TextField(
        blank=True,
        help_text='Optional internal notes about the final decision (not shown to jurors).',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['organization_name']

    def __str__(self):
        return f'{self.organization_name} — {self.category.name}'

    def average_score(self):
        reviews = self.jury_reviews.filter(is_submitted=True)
        if not reviews:
            return None
        return round(sum(r.total_score() for r in reviews) / len(reviews), 2)

    def review_count(self):
        return self.jury_reviews.filter(is_submitted=True).count()


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


ALLOWED_DOCUMENT_EXTENSIONS = ['pdf', 'gif', 'jpg', 'jpeg', 'png', 'mov', 'mp4', 'docx', 'pptx']

IMAGE_EXTENSIONS = {'gif', 'jpg', 'jpeg', 'png'}
VIDEO_EXTENSIONS = {'mov', 'mp4'}
WORD_EXTENSIONS = {'docx'}
SLIDES_EXTENSIONS = {'pptx'}


class NominationDocument(models.Model):
    """Supporting file(s) uploaded for a nomination — shown to the jury as a
    clickable link (or thumbnail/player, for images/video). Accepts either an
    uploaded PDF, image (gif/jpg/jpeg/png), or video (mov/mp4) — OR a link to
    an externally-hosted video (YouTube, Vimeo, etc.) instead of an upload."""

    nomination = models.ForeignKey(Nomination, on_delete=models.CASCADE, related_name='documents')
    label = models.CharField(max_length=255, default='Supporting Document')
    file = models.FileField(
        upload_to='nominations/%Y/%m/',
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS)],
        help_text='Accepted formats: PDF, GIF, JPEG, PNG, MOV, MP4, DOCX, PPTX. Leave blank if using a Video URL instead.',
    )
    video_url = models.URLField(
        blank=True,
        help_text='YouTube (or Vimeo) link, if not uploading a video file directly. Leave blank if using File instead.',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.label} — {self.nomination.organization_name}'

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.file and not self.video_url:
            raise ValidationError('Provide either a file upload or a video URL.')
        if self.file and self.video_url:
            raise ValidationError('Provide only one: either a file upload or a video URL, not both.')

    def extension(self):
        if not self.file:
            return ''
        return os.path.splitext(self.file.name)[1].lower().lstrip('.')

    def youtube_embed_url(self):
        """Returns an embeddable https://www.youtube.com/embed/<id> URL if
        video_url is a recognizable YouTube link, else None."""
        if not self.video_url:
            return None
        match = re.search(
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([\w-]{11})',
            self.video_url,
        )
        return f'https://www.youtube.com/embed/{match.group(1)}' if match else None

    def vimeo_embed_url(self):
        if not self.video_url:
            return None
        match = re.search(r'vimeo\.com/(\d+)', self.video_url)
        return f'https://player.vimeo.com/video/{match.group(1)}' if match else None

    def file_type(self):
        if self.video_url:
            return 'external_video'
        ext = self.extension()
        if ext in IMAGE_EXTENSIONS:
            return 'image'
        if ext in VIDEO_EXTENSIONS:
            return 'video'
        if ext == 'pdf':
            return 'pdf'
        if ext in WORD_EXTENSIONS:
            return 'word'
        if ext in SLIDES_EXTENSIONS:
            return 'slides'
        return 'other'