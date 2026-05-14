from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import viewsets, status, generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import Workshop, Booking, User
from .serializers import (
    RegisterSerializer,
    WorkshopSerializer,
    BookingSerializer,
    UserSerializer
)
from .permissions import IsAdminOrReadOnly

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Возвращаем данные созданного пользователя (без пароля)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

class WorkshopViewSet(viewsets.ModelViewSet):
    queryset = Workshop.objects.all().order_by('date')
    serializer_class = WorkshopSerializer
    permission_classes = (IsAdminOrReadOnly,)

@extend_schema_view(
    create=extend_schema(description='Забронировать место на мастер-класс'),
    list=extend_schema(description='Список бронирований текущего пользователя'),
)
class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = (IsAuthenticated,)
    queryset = Booking.objects.all()


    def get_queryset(self):
        # Пользователь видит только свои бронирования
        return Booking.objects.filter(user=self.request.user).select_related('workshop', 'user')

    def perform_create(self, serializer):
        # При создании автоматически подставляем текущего пользователя
        serializer.save(user=self.request.user)