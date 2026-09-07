from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='user',
    )

    # Используем email для входа
    email = models.EmailField(unique=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # username нужен для AbstractUser

    def __str__(self):
        return f"{self.email} - {self.role}"


class Workshop(models.Model):
    title = models.CharField(max_length=200, unique=True)
    description = models.TextField()
    date = models.DateTimeField()
    capacity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.date} - {self.capacity}"


class Booking(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='bookings',
    )
    workshop = models.ForeignKey(
        Workshop, on_delete=models.CASCADE, related_name='bookings',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ограничение БД запрещает повторную запись одного пользователя.
        unique_together = ('user', 'workshop')

    def __str__(self):
        return f"{self.user.email} -> {self.workshop.title}"
