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
