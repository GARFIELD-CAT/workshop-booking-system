"""Добавляет начальные данные для демонстрации учебного проекта."""

from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.utils import timezone


DEMO_USERNAMES = ('admin', 'user', 'user2')
DEMO_WORKSHOP_TITLES = (
    'Создание REST API на Django',
    'Основы публичных выступлений',
    'Мобильная фотография',
    'Эффективное управление временем',
)


def create_demo_data(apps, schema_editor):
    """Создаёт пользователей, мастер-классы и бронирования."""
    user_model = apps.get_model('workshops', 'User')
    workshop_model = apps.get_model('workshops', 'Workshop')
    booking_model = apps.get_model('workshops', 'Booking')

    admin = user_model.objects.create(
        username='admin',
        email='admin@example.com',
        password=make_password('admin'),
        role='admin',
    )
    user = user_model.objects.create(
        username='user',
        email='user@example.com',
        password=make_password('user'),
        role='user',
    )
    user2 = user_model.objects.create(
        username='user2',
        email='user2@example.com',
        password=make_password('user2'),
        role='user',
    )

    now = timezone.now()
    api_workshop = workshop_model.objects.create(
        title=DEMO_WORKSHOP_TITLES[0],
        description='Создание учебного API с Django REST Framework.',
        date=now + timedelta(days=30),
        capacity=10,
    )
    speaking = workshop_model.objects.create(
        title=DEMO_WORKSHOP_TITLES[1],
        description='Структура речи и работа с волнением.',
        date=now + timedelta(days=60),
        capacity=15,
    )
    photography = workshop_model.objects.create(
        title=DEMO_WORKSHOP_TITLES[2],
        description='Настройка камеры смартфона и основы композиции.',
        date=now + timedelta(days=90),
        capacity=10,
    )
    workshop_model.objects.create(
        title=DEMO_WORKSHOP_TITLES[3],
        description='Планирование задач и расстановка приоритетов.',
        date=now + timedelta(days=120),
        capacity=12,
    )

    booking_model.objects.bulk_create([
        booking_model(user=user, workshop=api_workshop),
        booking_model(user=user2, workshop=api_workshop),
        booking_model(user=user, workshop=speaking),
        booking_model(user=admin, workshop=photography),
    ])


def delete_demo_data(apps, schema_editor):
    """Удаляет записи, добавленные этой миграцией."""
    user_model = apps.get_model('workshops', 'User')
    workshop_model = apps.get_model('workshops', 'Workshop')

    user_model.objects.filter(username__in=DEMO_USERNAMES).delete()
    workshop_model.objects.filter(
        title__in=DEMO_WORKSHOP_TITLES,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('workshops', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_demo_data, delete_demo_data),
    ]
