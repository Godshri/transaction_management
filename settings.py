import os

APP_SETTINGS = None

ADMINS = (
    ('img', 'img@it-solution.ru'),
)

BASE_DOMAIN = 'https://is_demo.it-solution.ru'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_PATH = os.path.dirname(__file__).replace('\\','/')

SECRET_KEY = 'UxWXNk8hFEJYUkstPtBdtNgvqKfOFbME'

DEBUG = False

ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    'b24-oyi9l4.bitrix24.ru',
    '.bitrix24.ru',
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'integration_utils.bitrix24',
    'deals',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'is_demo',
        'USER': 'is_demo',
        'PASSWORD': 'password',
        'HOST': 'localhost',
    },
}


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'ru-ru'

TIME_ZONE = 'Europe/Moscow'

USE_I18N = True

USE_L10N = True

USE_TZ = True

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
ENTRY_FILE_UPLOADING_FOLDER = os.path.join(MEDIA_ROOT, 'uploaded_entrie_files')

STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = '/static/'
ADMIN_MEDIA_PREFIX = '/static/admin/'
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)
STATICFILES_DIRS = [
     os.path.join(BASE_DIR, 'staticfiles'),
]


from integration_utils.its_utils.mute_logger import MuteLogger
ilogger = MuteLogger()



# local settings
try:
    from local_settings import *
except ImportError:
    from warnings import warn

    warn('create local_settings.py')

if not APP_SETTINGS:
    from integration_utils.bitrix24.local_settings_class import LocalSettingsClass
    APP_SETTINGS = LocalSettingsClass(
        # portal_domain='',
        app_domain='is_demo.it-solution.ru',
        app_name='post_currency',
        salt='df897hynj4b34u804b5n45bkl4b',
        secret_key='sfjbh40989034nk4j4389tfj',
        # application_bitrix_client_id='',
        # application_bitrix_client_secret='',
        application_index_path='/',
    )

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


CSRF_TRUSTED_ORIGINS = [
    'https://b24-oyi9l4.bitrix24.ru',
    'https://*.bitrix24.ru',
]

BASE_DOMAIN = 'http://localhost:8000'