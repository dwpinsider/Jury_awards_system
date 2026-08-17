from django import forms


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label='CSV or Excel file',
        help_text='.csv, .xlsx, or .xlsm. If CSV, must be comma-separated with a header row.',
    )
    update_existing = forms.BooleanField(
        required=False,
        initial=True,
        label='Update existing entries if a match is found',
        help_text='If unchecked, matching rows are skipped instead of overwritten.',
    )