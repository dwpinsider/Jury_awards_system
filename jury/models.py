from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone


class JuryReview(models.Model):
    """A single juror's score + comments for a single nomination.

    Each criterion is scored on a 0-10 scale, with a MANDATORY FLOOR of 6 —
    a juror can raise a score above 6 but never drop below it. Scores are
    then weighted into a 0-100 total using the official rubric:
      Achievement & Outcome          -> 35% weight (score/10 * 35)
      Methodology of service/project -> 20% weight (score/10 * 20)
      Creativity & Innovation        -> 10% weight (score/10 * 10)
      Execution of service/project   -> 35% weight (score/10 * 35)
    The weights themselves are NOT shown to jurors in the scoring UI —
    they only see a plain 0-10 scale per criterion. Weights are visible to
    the secretariat via the "Scoring Guide" admin page.
    """

    SCORE_MIN = 6
    SCORE_MAX = 10

    WEIGHT_ACHIEVEMENT = 3.5   # 35% of 100, expressed as a multiplier of a /10 score
    WEIGHT_METHODOLOGY = 2.0   # 20%
    WEIGHT_CREATIVITY = 1.0    # 10%
    WEIGHT_EXECUTION = 3.5     # 35%

    juror = models.ForeignKey('accounts.Juror', on_delete=models.CASCADE, related_name='reviews')
    nomination = models.ForeignKey('awards.Nomination', on_delete=models.CASCADE, related_name='jury_reviews')

    achievement_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(SCORE_MIN), MaxValueValidator(SCORE_MAX)],
        help_text='Achievement and outcome (6–10, minimum 6 mandatory)',
    )
    methodology_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(SCORE_MIN), MaxValueValidator(SCORE_MAX)],
        help_text='Methodology of the service / project (6–10, minimum 6 mandatory)',
    )
    creativity_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(SCORE_MIN), MaxValueValidator(SCORE_MAX)],
        help_text='Creativity and innovation (6–10, minimum 6 mandatory)',
    )
    execution_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(SCORE_MIN), MaxValueValidator(SCORE_MAX)],
        help_text='Execution of the service / project (6–10, minimum 6 mandatory)',
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
        """Weighted total out of 100, computed from the four 0-10 scores."""
        return round(
            (self.achievement_score or 0) * self.WEIGHT_ACHIEVEMENT
            + (self.methodology_score or 0) * self.WEIGHT_METHODOLOGY
            + (self.creativity_score or 0) * self.WEIGHT_CREATIVITY
            + (self.execution_score or 0) * self.WEIGHT_EXECUTION
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