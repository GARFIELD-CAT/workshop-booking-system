from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Booking, Workshop


def validate_booking(user, workshop, booking_id=None):
    """Проверяем дату, повторную запись и наличие свободного места."""
    if workshop.date <= timezone.now():
        raise ValidationError({
            'workshop_id': 'Нельзя забронировать прошедший мастер-класс.',
        })

    bookings = Booking.objects.filter(workshop=workshop)

    if booking_id is not None:
        bookings = bookings.exclude(pk=booking_id)

    if bookings.filter(user=user).exists():
        raise ValidationError({
            'workshop_id': 'Вы уже записаны на этот мастер-класс.',
        })

    if bookings.count() >= workshop.capacity:
        raise ValidationError({
            'workshop_id': 'Все места на мастер-класс заняты.',
        })


@transaction.atomic
def save_booking(user, workshop_id=None, booking_id=None):
    """Создаём бронь или переносим её на другой мастер-класс."""
    if booking_id is not None and workshop_id is None:
        # Пустой PATCH ничего не меняет, в том числе у старой брони.
        return get_object_or_404(Booking, pk=booking_id, user=user)

    # PostgreSQL блокирует строку до конца транзакции. Следующая запись
    # на этот мастер-класс дождётся сохранения и увидит актуальное число мест.
    workshop = get_object_or_404(
        Workshop.objects.select_for_update(), pk=workshop_id,
    )
    booking = None

    if booking_id is not None:
        # Сначала блокируем мастер-класс, затем бронь: порядок одинаковый
        # при переносе брони и удалении мастер-класса.
        booking = get_object_or_404(
            Booking.objects.select_for_update(), pk=booking_id, user=user,
        )

        if booking.workshop_id == workshop.pk:
            return booking

    validate_booking(user, workshop, booking_id)

    if booking is None:
        return Booking.objects.create(user=user, workshop=workshop)

    booking.workshop = workshop
    booking.save(update_fields=['workshop'])

    return booking


@transaction.atomic
def update_workshop(workshop_id, data):
    """Не даём уменьшить вместимость ниже числа действующих броней."""
    workshop = get_object_or_404(
        Workshop.objects.select_for_update(), pk=workshop_id,
    )
    capacity = data.get('capacity', workshop.capacity)

    if capacity < workshop.bookings.count():
        raise ValidationError({
            'capacity': 'Вместимость меньше количества существующих броней.',
        })

    for field, value in data.items():
        setattr(workshop, field, value)
    workshop.save()

    return workshop


@transaction.atomic
def delete_workshop(workshop_id):
    """Удаляем мастер-класс и брони после завершения текущих записей."""
    workshop = get_object_or_404(
        Workshop.objects.select_for_update(), pk=workshop_id,
    )
    workshop.delete()
