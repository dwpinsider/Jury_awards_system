from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone


class JuryReview(models.Model):
    """A single juror's score + comments for a single nomination.

    Weighting matches the official judging rubric:
      Achievement & Outcome        -> out of 35
      Methodology of service/project -> out of 20
      Creativity & Innovation      -> out of 10
      Execution of service/project -> out of 35
      (Total out of 100)
    """

    juror = models.ForeignKey('accounts.Juror', on_delete=models.CASCADE, related_name='reviews')
    nomination = models.ForeignKey('awards.Nomination', on_delete=models.CASCADE, related_name='jury_reviews')

    achievement_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(35)],
        help_text='Achievement and outcome (out of 35)',
    )
    methodology_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(20)],
        help_text='Methodology of the service / project (out of 20)',
    )
    creativity_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text='Creativity and innovation (out of 10)',
    )
    execution_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(35)],
        help_text='Execution of the service / project (out of 35)',
    )

    comments = models.TextField(blank=True, help_text="Juror's overall experience / remarks on this entry")

    is_submitted = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('juror', 'nomination')
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.juror} -> {self.nomination} ({self.total_score()}/100)'

    def total_score(self):
        return (
            (self.achievement_score or 0)
            + (self.methodology_score or 0)
            + (self.creativity_score or 0)
            + (self.execution_score or 0)
        )

    def mark_submitted(self):
        self.is_submitted = True
        self.submitted_at = timezone.now()
        self.save(update_fields=['is_submitted', 'submitted_at'])


class RecentlyViewed(models.Model):
    """Tracks the last nominations a juror opened, for the dashboard's
    'Recently Viewed' quick-jump list. Capped at 4 per juror (oldest trimmed)."""

    MAX_PER_JUROR = 4

    juror = models.ForeignKey('accounts.Juror', on_delete=models.CASCADE, related_name='recently_viewed')
    nomination = models.ForeignKey('awards.Nomination', on_delete=models.CASCADE, related_name='+')
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('juror', 'nomination')
        ordering = ['-viewed_at']

    def __str__(self):
        return f'{self.juror} viewed {self.nomination} at {self.viewed_at}'

    @classmethod
    def record(cls, juror, nomination):
        obj, _created = cls.objects.update_or_create(juror=juror, nomination=nomination)
        # Trim anything beyond the most recent MAX_PER_JUROR entries
        stale_ids = list(
            cls.objects.filter(juror=juror).order_by('-viewed_at').values_list('id', flat=True)[cls.MAX_PER_JUROR:]
        )
        if stale_ids:
            cls.objects.filter(id__in=stale_ids).delete()
        return obj