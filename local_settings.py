DEBUG = True
ALLOWED_HOSTS = ['*']

from integration_utils.bitrix24.local_settings_class import LocalSettingsClass

TINKOFF_API_KEY = 'your-api-key'
ENDPOINT_TINKOFF = 'your-secret-key'
API_KEY_TINKOFF = 'your-api-key'
SECRET_KEY_TINKOFF = 'your-secret-key'

OPEN_AI_API_KEY = 'your-api-key'


APP_SETTINGS = LocalSettingsClass(
    portal_domain='b24-oyi9l4.bitrix24.ru',
    app_domain='127.0.0.1:8000',
    app_name='is-demo',
    salt='wefiewofioiI(IF(Eufrew8fju8ewfjhwkefjlewfjlJFKjewubhybfwybgybHBGYBGF',
    secret_key='wefewfkji4834gudrj.kjh237tgofhfjekewf.kjewkfjeiwfjeiwjfijewf',
    application_bitrix_client_id='local.68c3cfa704b199.28351672',
    application_bitrix_client_secret='0jttxdjVz7hbP0osPOtybDnAlmqfXexbrcampcgDA0oH7hMK3D',
    application_index_path='/',
)

DOMAIN = "56218ef983f3-8301993767665431593.ngrok-free.app"


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'transaction_management',  # Or path to database file if using sqlite3.
        'USER': 'demo',  # Not used with sqlite3.
        'PASSWORD': 'P@ssw0rd',  # Not used with sqlite3.
        'HOST': 'localhost',
    },
}