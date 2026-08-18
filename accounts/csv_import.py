"""CSV/Excel import for bulk juror invites."""

import csv
import io

import openpyxl

from .models import Juror

JUROR_CSV_COLUMNS = ['full_name', 'email', 'organization', 'title', 'is_active']


def _read_csv_rows(file_obj):
    data = file_obj.read()
    if isinstance(data, bytes):
        for encoding in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
            try:
                data = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
    return list(csv.DictReader(io.StringIO(data)))


def _read_xlsx_rows(file_obj):
    workbook = openpyxl.load_workbook(file_obj, data_only=True, read_only=True)
    sheet = workbook.worksheets[0]
    rows_iter = sheet.iter_rows(values_only=True)
    try:
        header = next(rows_iter)
    except StopIteration:
        return []
    headers = [str(h).strip() if h is not None else '' for h in header]
    rows = []
    for raw_row in rows_iter:
        if raw_row is None or all(cell is None for cell in raw_row):
            continue
        row = {}
        for i, header_name in enumerate(headers):
            if not header_name:
                continue
            value = raw_row[i] if i < len(raw_row) else None
            row[header_name] = '' if value is None else str(value)
        rows.append(row)
    return rows


def _read_rows(file_obj):
    name = getattr(file_obj, 'name', '') or ''
    if name.lower().endswith(('.xlsx', '.xlsm')):
        return _read_xlsx_rows(file_obj)
    return _read_csv_rows(file_obj)


def _truthy(value, default=True):
    if value is None or value == '':
        return default
    return str(value).strip().lower() not in ('false', '0', 'no')


def import_jurors_from_csv(file_obj, update_existing=True):
    """Expected columns: full_name, email, organization, title, is_active.
    Matching is by email (case-insensitive) — jurors already invited are
    updated in place if update_existing, otherwise skipped.
    Does NOT set a password or send an email — jurors log in by OTP, so a
    row here is simply "granting access" to that address."""
    reader = _read_rows(file_obj)
    created = updated = skipped = 0
    errors = []

    for i, row in enumerate(reader, start=2):
        email = (row.get('email') or '').strip().lower()
        full_name = (row.get('full_name') or '').strip()

        if not email or not full_name:
            errors.append(f'Row {i}: missing "email" or "full_name" — skipped.')
            skipped += 1
            continue

        defaults = dict(
            full_name=full_name,
            organization=(row.get('organization') or '').strip(),
            title=(row.get('title') or '').strip(),
            is_active=_truthy(row.get('is_active'), default=True),
        )

        existing = Juror.objects.filter(email__iexact=email).first()
        if existing:
            if update_existing:
                for field, value in defaults.items():
                    setattr(existing, field, value)
                existing.save()
                updated += 1
            else:
                skipped += 1
        else:
            Juror.objects.create(email=email, **defaults)
            created += 1

    return {'created': created, 'updated': updated, 'skipped': skipped, 'errors': errors}