from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Booking, User, Workshop
from .permissions import IsAdminOrReadOnly
from .serializers import (
    BookingSerializer,
    RegisterSerializer,
    UserSerializer,
    WorkshopSerializer,
)
from .services import delete_workshop


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    @extend_schema(responses={201: UserSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            UserSerializer(user).data, status=status.HTTP_201_CREATED,
        )


class WorkshopViewSet(viewsets.ModelViewSet):
    queryset = Workshop.objects.all().order_by('date', 'id')
    serializer_class = WorkshopSerializer
    permission_classes = (IsAdminOrReadOnly,)

    def perform_destroy(self, instance):
        delete_workshop(instance.pk)


@extend_schema_view(
    create=extend_schema(description='Забронировать место на мастер-класс'),
    list=extend_schema(
        description='Список бронирований текущего пользователя',
    ),
)
class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = (IsAuthenticated,)
    queryset = Booking.objects.all()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Booking.objects.none()

        # Пользователь видит только свои бронирования
        return (
            Booking.objects.filter(user=self.request.user)
            .select_related('workshop', 'user')
            .order_by('-created_at', '-id')
        )

    def perform_create(self, serializer):
        # При создании автоматически подставляем текущего пользователя
        serializer.save(user=self.request.user)
