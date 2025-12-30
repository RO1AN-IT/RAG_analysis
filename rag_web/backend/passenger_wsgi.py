"""
WSGI конфигурация для Beget (Passenger).
Этот файл используется, если Beget поддерживает Passenger WSGI.
"""

import sys
import os
from pathlib import Path

# Добавляем путь к проекту
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Активация виртуального окружения, если оно существует
venv_path = BASE_DIR / 'venv'
if venv_path.exists():
    # Добавляем site-packages из venv в sys.path
    site_packages = venv_path / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
    if site_packages.exists():
        sys.path.insert(0, str(site_packages))

# Установка переменных окружения Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Загрузка Django WSGI приложения
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

