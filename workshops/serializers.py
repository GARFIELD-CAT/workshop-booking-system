from rest_framework import serializers

from .models import Booking, User, Workshop
from .services import save_booking, update_workshop


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
        fields = (
            'id', 'title', 'description', 'date', 'capacity',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def update(self, instance, validated_data):
        return update_workshop(instance.pk, validated_data)


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

    def create(self, validated_data):
        return save_booking(
            user=validated_data['user'],
            workshop_id=validated_data['workshop'].pk,
        )

    def update(self, instance, validated_data):
        workshop = validated_data.get('workshop')

        return save_booking(
            user=self.context['request'].user,
            workshop_id=workshop.pk if workshop is not None else None,
            booking_id=instance.pk,
        )
