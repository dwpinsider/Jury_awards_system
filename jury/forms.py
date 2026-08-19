from django import forms
from .models import JuryReview


class RangeInput(forms.NumberInput):
    """A <input type="range"> that still submits/validates as a plain number."""
    input_type = 'range'


SCORE_MIN = JuryReview.SCORE_MIN   # 6 — mandatory floor, jurors can raise but never lower
SCORE_MAX = JuryReview.SCORE_MAX   # 10


class JuryReviewForm(forms.ModelForm):
    class Meta:
        model = JuryReview
        fields = ['achievement_score', 'methodology_score', 'creativity_score', 'execution_score', 'comments']
        widgets = {
            'achievement_score': RangeInput(attrs={'min': SCORE_MIN, 'max': SCORE_MAX, 'step': 1, 'class': 'score-slider'}),
            'methodology_score': RangeInput(attrs={'min': SCORE_MIN, 'max': SCORE_MAX, 'step': 1, 'class': 'score-slider'}),
            'creativity_score': RangeInput(attrs={'min': SCORE_MIN, 'max': SCORE_MAX, 'step': 1, 'class': 'score-slider'}),
            'execution_score': RangeInput(attrs={'min': SCORE_MIN, 'max': SCORE_MAX, 'step': 1, 'class': 'score-slider'}),
            'comments': forms.Textarea(attrs={'rows': 5, 'class': 'input', 'placeholder': 'Overall experience / remarks on this nomination...'}),
        }
        # Note: weight percentages are intentionally NOT in these labels —
        # jurors only see a plain 0-10 scale. Weights live in the admin-only
        # "Scoring Guide" page instead.
        labels = {
            'achievement_score': 'Achievement and Outcome',
            'methodology_score': 'Methodology of the Service / Project',
            'creativity_score': 'Creativity and Innovation',
            'execution_score': 'Execution of the Service / Project',
            'comments': 'Overall Experience / Comments',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('achievement_score', 'methodology_score', 'creativity_score', 'execution_score'):
            field = self.fields[name]
            # Django's PositiveSmallIntegerField.formfield() hardcodes
            # min_value=0 into the widget's attrs dict at form-class
            # construction time, regardless of our model's custom
            # MinValueValidator(6) — so setting field.min_value alone isn't
            # enough, since it doesn't touch the widget's own attrs dict that
            # actually gets rendered. Overwriting widget.attrs directly here
            # is what actually fixes the rendered HTML min="0" bug.
            field.min_value = SCORE_MIN
            field.max_value = SCORE_MAX
            field.widget.attrs['min'] = SCORE_MIN
            field.widget.attrs['max'] = SCORE_MAX
            # Every criterion starts at the mandatory floor (6) for a brand-new
            # (unscored) review — jurors can only move it up from there, never
            # below. Without this, an empty range input would default to its
            # midpoint, which could sit below the floor.
            if self.initial.get(name) is None and not (self.instance and self.instance.pk):
                field.initial = SCORE_MIN