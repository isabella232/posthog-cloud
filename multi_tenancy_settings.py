

MULTI_TENANCY = os.environ.get('MULTI_TENANCY', True)

ROOT_URLCONF = 'multi_tenancy.urls'

if INSTALLED_APPS and isinstance(INSTALLED_APPS, list):

	INSTALLED_APPS.append('multi_tenancy.apps.MultiTenancyConfig')

if TEMPLATES and TEMPLATES[0] and TEMPLATES[0]['DIRS'] and isinstance(TEMPLATES[0]['DIRS'], list):

	TEMPLATES[0]['DIRS'].append('multi_tenancy/templates')