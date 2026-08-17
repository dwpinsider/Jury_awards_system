# GOV HR & Youth Awards — Jury Portal

A Django app implementing the jury workflow for `govhr-summit.com/awards`:

1. **Email login** — juror enters their email → gets a 6-digit one-time code by email.
2. **OTP verification** — code expires after 10 minutes (configurable).
3. **NDA gate** — juror must accept the NDA once before seeing any nomination content.
4. **My Dashboard** — stats + category shortcuts.
5. **Categories** — mirrors your category structure (Individual / Organizational, Public & Government / Private Sector).
6. **Nomination list per category** — all submitted companies/nominees in that category, with Reviewed/Pending status.
7. **Nomination detail** — all fields from the submission PDF (organization info, nominee info, project highlights, key achievements, reason for nomination, performance stats table, business impact) plus a link to the supporting PDF document(s).
8. **Scoring form** — matches your published rubric:
   - Achievement and Outcome — 35%
   - Methodology of the service/project — 20%
   - Creativity and Innovation — 10%
   - Execution of the service/project — 35%
   - Free-text "overall experience" comments
   - Save as draft or Submit final score
9. **My Reviews** — a juror's own submission history with total scores and an overall average, so they can see their overall judging experience.

Everything a juror sees (categories, nominations, PDFs, jury accounts, NDA copy) is managed from the **Django admin** at `/admin/`, exactly as you described ("I will let you know what data to show the jury" → you control it entirely from there).

## Project layout

```
accounts/   Juror model, OTP model, email-login views/templates
awards/     Category, Nomination, NominationStat, NominationDocument (imported by admin)
jury/       JuryReview model, dashboard/category/nomination/scoring views
templates/  All HTML (gold/charcoal theme matching your awards branding)
static/     CSS
```

## Local setup

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser  # create your admin login
python manage.py runserver
```

Visit:
- `http://127.0.0.1:8000/admin/` — add Categories, Nominations (with stats + PDF uploads), and Jurors here.
- `http://127.0.0.1:8000/accounts/login/` — jury login.

By default OTP codes print to the **console** (terminal) instead of sending real email, so you can test immediately without SMTP setup. To send real emails, copy `.env.example` to `.env`, fill in your SMTP provider (Gmail, SendGrid, SES, etc.), and export those variables before running the server (or wire them into your deployment platform's environment settings).

## Loading a sample nomination

`seed_sample_data.py` creates one sample category, one sample nomination (using the GPSSA / Khalid Khadim data from your PDF), and one sample juror (`juror@example.com`) so you can click through the whole flow immediately:

```bash
python seed_sample_data.py
python manage.py runserver
# then go to /accounts/login/, enter juror@example.com, and read the code from your terminal
```

## How to add real jurors and nominations

**Add a juror** — Admin → Accounts → Jurors → Add Juror. Set full name, email, and (optionally) which categories they're assigned to judge — leave "Assigned categories" empty to let them judge every open category.

**Add a category** — Admin → Awards → Categories → Add Category. Set name, level (Individual/Organizational), and sector (Public & Government / Private / N/A) to match your public registration form's category tree.

**Add a nomination (from a submitted PDF)** — Admin → Awards → Nominations → Add Nomination. Fill in the organization/nominee fields and paste the narrative sections (Project Highlights, Key Achievements, Reason for Nomination, Business Impact). Use the inline **Stats** rows for the "Project Performance Results & Statistics" table (Area / Value pairs), and the inline **Documents** section to upload the actual submission PDF — the jury will see it as a clickable link ("View" → opens PDF in a new tab) on the nomination detail page.

## Scoring model

Each `JuryReview` stores one juror's score for one nomination:

| Field | Max | Weight |
|---|---|---|
| achievement_score | 35 | 35% |
| methodology_score | 20 | 20% |
| creativity_score | 10 | 10% |
| execution_score | 35 | 35% |

`total_score()` sums these to a score out of 100. A juror can save a draft (not counted as submitted) and submit later; submitting locks in `submitted_at` and shows on their "My Reviews" page and in the admin's JuryReview list (where you can compute averages across jurors per nomination for finalist selection).

## Notes for production

- Set `DJANGO_DEBUG=False`, a real `DJANGO_SECRET_KEY`, and your real domain in `DJANGO_ALLOWED_HOSTS`.
- Configure real SMTP credentials so OTP emails actually send.
- Configure a real database (Postgres recommended) by changing `DATABASES` in `govhr_awards/settings.py`, or wire in `dj-database-url` if your host provides a `DATABASE_URL`.
- Serve `/media/` (uploaded PDFs) via your web server or cloud storage (e.g. S3) in production — Django's built-in static serving is for development only.
