"""
Django settings for nexhub project.

This file contains the basic configuration for development using SQLite.
"""

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "development-secret-key-change-me"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS: list[str] = []

# Agent shared API key for minimal push endpoint (internal use only)
# Change this to a strong random value and keep it secret
AGENT_API_KEY = "test-shared-key-1765595205"


# Application definition

INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "overwatch",
    "rest_framework",
    "rest_framework.authtoken",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "nexhub.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "nexhub.wsgi.application"
ASGI_APPLICATION = "nexhub.asgi.application"


# Database
# https://docs.djangoproject.com/en/stable/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Password validation
# https://docs.djangoproject.com/en/stable/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/stable/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/stable/howto/static-files/

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Default primary key field type
# https://docs.djangoproject.com/en/stable/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
}

# Jazzmin Admin Configuration
JAZZMIN_SETTINGS = {
    "site_title": "NexHub Admin",
    "site_header": "NexHub Infrastructure",
    "site_brand": "NexHub",
    "login_logo": None,
    "logo_title": None,
    "copyright": "NexHub Infrastructure Management",
    "search_model": ["overwatch.Server", "overwatch.Category"],
    "user_avatar": None,
    "topmenu_links": [
        {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "API", "url": "/api/", "permissions": ["auth.view_user"]},
        {"name": "Docs", "url": "/api/schema/", "permissions": ["auth.view_user"]},
    ],
    "usersettings_allow_user_preferences": True,
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": [
        "overwatch.Server",
        "overwatch.Category",
        "overwatch.Tag",
        "overwatch.DataDictionary",
    ],
    "icons": {
        "overwatch.Server": "fas fa-server",
        "overwatch.Category": "fas fa-folder",
        "overwatch.Tag": "fas fa-tag",
        "overwatch.DataDictionary": "fas fa-book",
        "overwatch.Subnet": "fas fa-network-wired",
        "overwatch.Note": "fas fa-sticky-note",
        "auth.User": "fas fa-user",
        "auth.Group": "fas fa-users",
    },
    "default_icon_parents": "fas fa-chevron-right",
    "default_icon_children": "fas fa-arrow-right",
    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "overwatch.server": "collapsible",
        "auth.user": "collapsible",
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small": False,
    "footer_small": False,
    "body_small": False,
    "brand_small": False,
    "brand_colour": "navbar-danger",
    "accent": "accent-primary",
    "tooltip_class": "tooltip-dark",
    "sidebar_nav_small_text": False,
    "dashboard_chart_device_support": True,
    "admin_paginate_change_list_view": 25,
}

