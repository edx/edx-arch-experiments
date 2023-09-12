"""
These settings are here to use during manufacture_data tests

In a real-world use case, apps in this project are installed into other
Django applications, so these settings will not be used.
"""
import os

INSTALLED_APPS = [
    'edx_arch_experiments',
    'edx_arch_experiments.tests.test_management',
]

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': os.environ.get('DB_NAME', 'default.db'),
        'USER': os.environ.get('DB_USER', ''),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', ''),
        'PORT': os.environ.get('DB_PORT', ''),
    },
}
