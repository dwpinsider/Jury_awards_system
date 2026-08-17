import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'govhr_awards.settings')
django.setup()

from awards.models import Category, Nomination, NominationStat
from accounts.models import Juror

cat, _ = Category.objects.get_or_create(
    name='GOV HR Leader of the Year in Public & Government Sector',
    defaults=dict(level='individual', sector='public',
                  description='Individual Category — Public & Government Sector')
)

nom, created = Nomination.objects.get_or_create(
    organization_name='General Pensions and Social Security Authority',
    category=cat,
    defaults=dict(
        sector='Government Sector',
        city_country='Dubai, United Arab Emirates',
        contact_person='Manal Al Aswad',
        designation='Talent Development Senior Specialist',
        phone_number='+971971505219052',
        mobile_number='+971971505219052',
        email='manal.alaswad@gpssa.gov.ae',
        website='http://www.gpssa.gov.ae',
        nominee_full_name='Khalid Khadim, Chartered FCIPD',
        nominee_job_title='Director of Human Resources Dept.',
        nominee_address='United Arab Emirates, Dubai',
        employee_headcount=314,
        project_title='Building Future Ready Organizations Through People, Systems and Technology',
        project_highlights=(
            "My leadership philosophy is grounded in a simple principle: sustainable "
            "transformation requires the alignment of People, Systems, and Technology. "
            "Over more than 15 years in the UAE federal government, I have applied this "
            "approach to transform learning and capability development, talent management, "
            "recruitment, leadership development, workforce planning, organizational "
            "structures, and HR governance."
        ),
        key_achievements=(
            "Led comprehensive human capital initiatives that contributed to the organization "
            "achieving first place among UAE federal entities in Workplace Future Readiness "
            "in 2023. Transformed learning into a continuous digital ecosystem achieving "
            "approximately 97% continuous learning participation by 2022, reducing expenditure "
            "by more than 60% within two years. Led development of a digital careers platform "
            "transforming recruitment into an efficient, candidate-centric process."
        ),
        reason_for_nomination=(
            "Submitted in recognition of sustained leadership in driving human capital "
            "transformation through the strategic alignment of people, systems, and technology "
            "over more than 15 years in the UAE federal government."
        ),
        business_impact=(
            "The learning transformation demonstrated clear financial efficiency, reducing "
            "expenditure by more than 60% within two years while expanding learning "
            "participation and accessibility. The digital recruitment transformation generated "
            "additional efficiencies through reduced recruitment costs and faster vacancy "
            "fulfillment while improving candidate experience, responsiveness, and quality."
        ),
    )
)

if created:
    stats = [
        ('Learning Participation', 'approximately 97% continuous learning participation'),
        ('Candidate Satisfaction', '82% to 99%'),
        ('Recruitment Responsiveness', '70% to 97%'),
        ('Candidate Quality', '90% to 99%'),
        ('Emiratization', 'Approximately 86% to 88%'),
        ('Future Readiness', '1st place among UAE federal entities in Workplace Future Readiness in 2023'),
    ]
    for i, (area, value) in enumerate(stats):
        NominationStat.objects.create(nomination=nom, area=area, value=value, order=i)

juror, _ = Juror.objects.get_or_create(
    email='juror@example.com',
    defaults=dict(full_name='Sample Juror', organization='HR Excellence Council', title='Panel Member')
)

print('Seed complete.')
print('Category:', cat)
print('Nomination:', nom, '| stats:', nom.stats.count())
print('Juror:', juror)
