import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent


def _load_database_config() -> dict:
    config_path = PROJECT_ROOT / "db_config.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


_db_config = _load_database_config()

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me-before-production")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]
if DEBUG and "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")

INSTALLED_APPS = [
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "students",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "dorms_portal.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
                "students.context_processors.student_portal_context",
            ],
        },
    },
]

WSGI_APPLICATION = "dorms_portal.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE", _db_config.get("database", "GUDorms")),
        "USER": os.getenv("MYSQL_USER", _db_config.get("user", "root")),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", _db_config.get("password", "")),
        "HOST": os.getenv("MYSQL_HOST", _db_config.get("host", "localhost")),
        "PORT": os.getenv("MYSQL_PORT", str(_db_config.get("port", "3306"))),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Cairo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Signed-cookie sessions keep the portal inside the supplied schema instead of
# requiring Django-owned session/auth tables in the shared MySQL database.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = os.getenv("DJANGO_SESSION_COOKIE_SECURE", "0") == "1"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = os.getenv("DJANGO_CSRF_COOKIE_SECURE", "0") == "1"
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "0") == "1"
MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
