from rest_framework import serializers
from django.utils import timezone
from .models import User, Workshop, Booking


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'role')
        read_only_fields = ('id', 'role')  # роль нельзя изменить через API


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('email', 'username', 'password')

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password'],
            role='user'  # По умолчанию обычный пользователь
        )
        return user


class WorkshopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workshop
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class BookingSerializer(serializers.ModelSerializer):
    # Вложенное отображение мастер-класса (только для чтения)
    workshop = WorkshopSerializer(read_only=True)
    workshop_id = serializers.PrimaryKeyRelatedField(
        queryset=Workshop.objects.all(), write_only=True, source='workshop'
    )
    user = UserSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = ('id', 'user', 'workshop', 'workshop_id', 'created_at')
        read_only_fields = ('id', 'created_at', 'user')

    def validate(self, data):
        workshop = data['workshop']
        user = self.context['request'].user

        # 1. Проверка даты: нельзя записаться на прошедший мастер-класс
        if workshop.date < timezone.now():
            raise serializers.ValidationError("Нельзя забронировать прошедший мастер-класс.")

        # 2. Проверка дублирования
        if Booking.objects.filter(user=user, workshop=workshop).exists():
            raise serializers.ValidationError("Вы уже забронированы на этот мастер-класс.")

        # 3. Проверка вместимости
        current_bookings = Booking.objects.filter(workshop=workshop).count()
        if current_bookings >= workshop.capacity:
            raise serializers.ValidationError("Все места на мастер-класс заняты.")

        return data