"""CSV import helpers for the admin panel.

Used by CategoryAdmin / NominationAdmin's "Import CSV" button so the
secretariat can bulk-load categories and nominations instead of typing
each one in by hand.
"""

import csv
import io

import openpyxl

from .models import Category, Nomination

CATEGORY_CSV_COLUMNS = [
    'name', 'level', 'sector', 'description', 'order', 'is_open_for_judging',
]

NOMINATION_CSV_COLUMNS = [
    'category', 'reference_code', 'organization_name', 'sector', 'city_country',
    'contact_person', 'designation', 'phone_number', 'mobile_number', 'email', 'website',
    'nominee_full_name', 'nominee_job_title', 'nominee_address', 'employee_headcount',
    'project_title', 'project_highlights', 'key_achievements', 'reason_for_nomination',
    'business_impact', 'is_visible_to_jury',
]


def _read_csv_rows(file_obj):
    data = file_obj.read()
    if isinstance(data, bytes):
        # Try the encodings CSV exports commonly show up in, in order of
        # likelihood. latin-1 never raises (it maps every byte 0-255 to a
        # character), so it's used as a guaranteed-not-to-crash last resort.
        for encoding in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
            try:
                data = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
    return list(csv.DictReader(io.StringIO(data)))


def _read_xlsx_rows(file_obj):
    """Reads the first sheet of an .xlsx file, treating row 1 as headers."""
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
            continue  # skip fully blank rows
        row = {}
        for i, header_name in enumerate(headers):
            if not header_name:
                continue
            value = raw_row[i] if i < len(raw_row) else None
            row[header_name] = '' if value is None else str(value)
        rows.append(row)
    return rows


def _read_rows(file_obj):
    """Dispatches to the CSV or XLSX reader based on the uploaded filename."""
    name = getattr(file_obj, 'name', '') or ''
    if name.lower().endswith(('.xlsx', '.xlsm')):
        return _read_xlsx_rows(file_obj)
    return _read_csv_rows(file_obj)


def _truthy(value, default=True):
    if value is None or value == '':
        return default
    return str(value).strip().lower() not in ('false', '0', 'no')


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# Human-friendly phrasings people naturally type/paste into a spreadsheet,
# mapped to the internal choice codes the Category model actually stores.
# Keys are matched after lowercasing + stripping whitespace.
LEVEL_ALIASES = {
    'individual': Category.LEVEL_INDIVIDUAL,
    'individual category': Category.LEVEL_INDIVIDUAL,
    'individual level category': Category.LEVEL_INDIVIDUAL,
    'organizational': Category.LEVEL_ORGANIZATIONAL,
    'organisational': Category.LEVEL_ORGANIZATIONAL,
    'organization': Category.LEVEL_ORGANIZATIONAL,
    'organisation': Category.LEVEL_ORGANIZATIONAL,
    'organizational category': Category.LEVEL_ORGANIZATIONAL,
    'organizational level category': Category.LEVEL_ORGANIZATIONAL,
    'org': Category.LEVEL_ORGANIZATIONAL,
}

SECTOR_ALIASES = {
    'public': Category.SECTOR_PUBLIC,
    'government': Category.SECTOR_PUBLIC,
    'public sector': Category.SECTOR_PUBLIC,
    'government sector': Category.SECTOR_PUBLIC,
    'public & government sector': Category.SECTOR_PUBLIC,
    'public and government sector': Category.SECTOR_PUBLIC,
    'public & government': Category.SECTOR_PUBLIC,
    'public and government': Category.SECTOR_PUBLIC,
    'gov': Category.SECTOR_PUBLIC,
    'private': Category.SECTOR_PRIVATE,
    'private sector': Category.SECTOR_PRIVATE,
    'na': Category.SECTOR_NA,
    'n/a': Category.SECTOR_NA,
    'not sector-specific': Category.SECTOR_NA,
    '': Category.SECTOR_NA,
}


def _normalize_choice(raw_value, aliases, valid_codes, default_code):
    """Maps a free-text CSV value to a valid model choice code.

    Tries an exact code match first (so 'public' still works even though
    it's also a dict key), then the alias table, then falls back to the
    default with a warning message for the caller to surface.
    """
    cleaned = (raw_value or '').strip()
    key = cleaned.lower()
    if key in valid_codes:
        return key, None
    if key in aliases:
        return aliases[key], None
    return default_code, cleaned


def import_categories_from_csv(file_obj, update_existing=True):
    """Expected columns: name, level, sector, description, order, is_open_for_judging

    - level: accepts 'individual'/'organizational' or common phrasings like
      'Individual Category', 'Organizational Level Category', etc.
    - sector: accepts 'public'/'private'/'na' or common phrasings like
      'Public & Government Sector', 'Private Sector', etc.
    - Matching is by category name (case-insensitive).
    """
    reader = _read_rows(file_obj)
    created = updated = skipped = 0
    errors = []

    valid_levels = {choice[0] for choice in Category.LEVEL_CHOICES}
    valid_sectors = {choice[0] for choice in Category.SECTOR_CHOICES}

    for i, row in enumerate(reader, start=2):  # row 1 is the header
        name = (row.get('name') or '').strip()
        if not name:
            errors.append(f'Row {i}: missing "name" — skipped.')
            skipped += 1
            continue

        level, bad_level = _normalize_choice(
            row.get('level'), LEVEL_ALIASES, valid_levels, Category.LEVEL_INDIVIDUAL
        )
        if bad_level:
            errors.append(f'Row {i}: unrecognized level "{bad_level}", defaulted to "individual".')

        sector, bad_sector = _normalize_choice(
            row.get('sector'), SECTOR_ALIASES, valid_sectors, Category.SECTOR_NA
        )
        if bad_sector:
            errors.append(f'Row {i}: unrecognized sector "{bad_sector}", defaulted to "na".')

        defaults = dict(
            level=level,
            sector=sector,
            description=row.get('description') or '',
            order=_int_or_none(row.get('order')) or 0,
            is_open_for_judging=_truthy(row.get('is_open_for_judging'), default=True),
        )

        existing = Category.objects.filter(name__iexact=name).first()
        if existing:
            if update_existing:
                for field, value in defaults.items():
                    setattr(existing, field, value)
                existing.save()
                updated += 1
            else:
                skipped += 1
        else:
            Category.objects.create(name=name, **defaults)
            created += 1

    return {'created': created, 'updated': updated, 'skipped': skipped, 'errors': errors}


def import_nominations_from_csv(file_obj, update_existing=True):
    """Expected columns: see NOMINATION_CSV_COLUMNS.

    - 'category' must match an existing Category name exactly (case-insensitive).
      Create the category first if it doesn't exist yet.
    - Matching an existing nomination is by (category, organization_name), case-insensitive.
    """
    reader = _read_rows(file_obj)
    created = updated = skipped = 0
    errors = []

    for i, row in enumerate(reader, start=2):
        org = (row.get('organization_name') or '').strip()
        cat_name = (row.get('category') or '').strip()

        if not org or not cat_name:
            errors.append(f'Row {i}: missing "organization_name" or "category" — skipped.')
            skipped += 1
            continue

        category = Category.objects.filter(name__iexact=cat_name).first()
        if not category:
            errors.append(
                f'Row {i}: category "{cat_name}" does not exist — skipped. '
                f'Create/import this category first.'
            )
            skipped += 1
            continue

        defaults = dict(
            reference_code=row.get('reference_code') or '',
            sector=row.get('sector') or '',
            city_country=row.get('city_country') or '',
            contact_person=row.get('contact_person') or '',
            designation=row.get('designation') or '',
            phone_number=row.get('phone_number') or '',
            mobile_number=row.get('mobile_number') or '',
            email=row.get('email') or '',
            website=row.get('website') or '',
            nominee_full_name=row.get('nominee_full_name') or '',
            nominee_job_title=row.get('nominee_job_title') or '',
            nominee_address=row.get('nominee_address') or '',
            employee_headcount=_int_or_none(row.get('employee_headcount')),
            project_title=row.get('project_title') or '',
            project_highlights=row.get('project_highlights') or '',
            key_achievements=row.get('key_achievements') or '',
            reason_for_nomination=row.get('reason_for_nomination') or '',
            business_impact=row.get('business_impact') or '',
            is_visible_to_jury=_truthy(row.get('is_visible_to_jury'), default=True),
        )

        existing = Nomination.objects.filter(category=category, organization_name__iexact=org).first()
        if existing:
            if update_existing:
                for field, value in defaults.items():
                    setattr(existing, field, value)
                existing.save()
                updated += 1
            else:
                skipped += 1
        else:
            Nomination.objects.create(category=category, organization_name=org, **defaults)
            created += 1

    return {'created': created, 'updated': updated, 'skipped': skipped, 'errors': errors}