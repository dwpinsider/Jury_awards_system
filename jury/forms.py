from django import forms
from .models import JuryReview


class RangeInput(forms.NumberInput):
    """A <input type="range"> that still submits/validates as a plain number."""
    input_type = 'range'


class JuryReviewForm(forms.ModelForm):
    class Meta:
        model = JuryReview
        fields = ['achievement_score', 'methodology_score', 'creativity_score', 'execution_score', 'comments']
        widgets = {
            'achievement_score': RangeInput(attrs={'min': 0, 'max': 35, 'step': 1, 'class': 'score-slider'}),
            'methodology_score': RangeInput(attrs={'min': 0, 'max': 20, 'step': 1, 'class': 'score-slider'}),
            'creativity_score': RangeInput(attrs={'min': 0, 'max': 10, 'step': 1, 'class': 'score-slider'}),
            'execution_score': RangeInput(attrs={'min': 0, 'max': 35, 'step': 1, 'class': 'score-slider'}),
            'comments': forms.Textarea(attrs={'rows': 5, 'class': 'input', 'placeholder': 'Overall experience / remarks on this nomination...'}),
        }
        labels = {
            'achievement_score': 'Achievement and Outcome (0–35)',
            'methodology_score': 'Methodology of the Service / Project (0–20)',
            'creativity_score': 'Creativity and Innovation (0–10)',
            'execution_score': 'Execution of the Service / Project (0–35)',
            'comments': 'Overall Experience / Comments',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Sliders need a starting value even for a brand-new (unscored) review,
        # otherwise the browser defaults an empty range input to its midpoint,
        # which would silently pre-select a non-zero score.
        for name in ('achievement_score', 'methodology_score', 'creativity_score', 'execution_score'):
            if self.initial.get(name) is None and not (self.instance and self.instance.pk):
                self.fields[name].initial = 0