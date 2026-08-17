from django import forms
from .models import JuryReview


class JuryReviewForm(forms.ModelForm):
    class Meta:
        model = JuryReview
        fields = ['achievement_score', 'methodology_score', 'creativity_score', 'execution_score', 'comments']
        widgets = {
            'achievement_score': forms.NumberInput(attrs={'min': 0, 'max': 35, 'class': 'input score-input'}),
            'methodology_score': forms.NumberInput(attrs={'min': 0, 'max': 20, 'class': 'input score-input'}),
            'creativity_score': forms.NumberInput(attrs={'min': 0, 'max': 10, 'class': 'input score-input'}),
            'execution_score': forms.NumberInput(attrs={'min': 0, 'max': 35, 'class': 'input score-input'}),
            'comments': forms.Textarea(attrs={'rows': 5, 'class': 'input', 'placeholder': 'Overall experience / remarks on this nomination...'}),
        }
        labels = {
            'achievement_score': 'Achievement and Outcome (0–35)',
            'methodology_score': 'Methodology of the Service / Project (0–20)',
            'creativity_score': 'Creativity and Innovation (0–10)',
            'execution_score': 'Execution of the Service / Project (0–35)',
            'comments': 'Overall Experience / Comments',
        }
