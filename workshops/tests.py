from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from types import SimpleNamespace

from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient, APITestCase

from .models import Booking, User, Workshop
from .serializers import BookingSerializer


class BookingAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = 'studentPass'
        cls.user = User.objects.create_user(
            username='student', email='student@example.com',
            password=cls.password,
        )
        cls.other = User.objects.create_user(
            username='other', email='other@example.com',
            password=cls.password,
        )
        cls.admin = User.objects.create_superuser(
            username='admin', email='admin@example.com',
            password=cls.password,
        )
        cls.workshop = Workshop.objects.create(
            title='Гончарное дело', description='Знакомство с глиной',
            date=timezone.now() + timedelta(days=7), capacity=1,
        )
        cls.next_workshop = Workshop.objects.create(
            title='Рисование', description='Основы акварели',
            date=timezone.now() + timedelta(days=14), capacity=2,
        )

    def test_registration_does_not_expose_password_or_allow_admin_role(self):
        response = self.client.post('/api/register/', {
            'username': 'new', 'email': 'new@example.com',
            'password': self.password, 'role': 'admin', 'is_superuser': True,
        })
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('password', response.data)
        user = User.objects.get(username='new')
        self.assertEqual(user.role, 'user')
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password(self.password))

    def test_login_refresh_and_authenticated_request(self):
        response = self.client.post('/api/token/', {
            'email': self.user.email, 'password': self.password,
        })
        self.assertEqual(response.status_code, 200)
        refreshed = self.client.post('/api/token/refresh/', {
            'refresh': response.data['refresh'],
        })
        self.assertEqual(refreshed.status_code, 200)
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + refreshed.data['access'],
        )
        self.assertEqual(self.client.get('/api/bookings/').status_code, 200)

    def test_workshops_are_public_but_bookings_require_login(self):
        self.assertEqual(self.client.get('/api/workshops/').status_code, 200)
        detail = self.client.get(f'/api/workshops/{self.workshop.pk}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(self.client.get('/api/bookings/').status_code, 401)
        response = self.client.post('/api/bookings/', {
            'workshop_id': self.workshop.pk,
        })
        self.assertEqual(response.status_code, 401)

    def test_superuser_keeps_user_role_but_can_manage_workshops(self):
        self.assertEqual(self.admin.role, 'user')
        self.assertTrue(self.admin.is_staff)
        self.assertTrue(self.admin.is_superuser)
        self.client.force_authenticate(self.admin)
        data = {
            'title': 'Новый', 'description': 'Описание', 'capacity': 3,
            'date': (timezone.now() + timedelta(days=1)).isoformat(),
        }
        response = self.client.post('/api/workshops/', data)
        self.assertEqual(response.status_code, 201)
        url = f"/api/workshops/{response.data['id']}/"
        data['title'] = 'Обновлённый'
        self.assertEqual(self.client.put(url, data).status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_existing_superuser_with_user_role_keeps_admin_access(self):
        self.admin.role = 'user'
        self.admin.save()
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f'/api/workshops/{self.workshop.pk}/', {'title': 'Другое имя'},
        )
        self.assertEqual(response.status_code, 200)

    def test_regular_user_cannot_change_workshops(self):
        self.client.force_authenticate(self.user)
        url = f'/api/workshops/{self.workshop.pk}/'

        for method in ('put', 'patch', 'delete'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 403)

        self.assertEqual(
            self.client.post('/api/workshops/', {}).status_code, 403,
        )

    def test_create_booking_returns_workshop_and_current_user(self):
        self.client.force_authenticate(self.user)
        response = self.client.post('/api/bookings/', {
            'workshop_id': self.workshop.pk, 'user': self.other.pk,
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['user']['id'], self.user.pk)
        self.assertEqual(response.data['workshop']['title'], 'Гончарное дело')
        self.assertNotIn('password', response.data['user'])

    def test_duplicate_and_full_workshop_are_rejected(self):
        Booking.objects.create(user=self.user, workshop=self.workshop)

        for user in (self.user, self.other):
            with self.subTest(user=user.username):
                self.client.force_authenticate(user)
                response = self.client.post('/api/bookings/', {
                    'workshop_id': self.workshop.pk,
                })
                self.assertEqual(response.status_code, 400)

        self.assertEqual(self.workshop.bookings.count(), 1)

    def test_past_workshop_is_rejected(self):
        self.workshop.date = timezone.now() - timedelta(days=1)
        self.workshop.save()
        self.client.force_authenticate(self.user)
        response = self.client.post('/api/bookings/', {
            'workshop_id': self.workshop.pk,
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Booking.objects.exists())

    def test_user_cannot_read_or_change_foreign_bookings(self):
        booking = Booking.objects.create(
            user=self.other, workshop=self.workshop,
        )
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/bookings/').data['count'], 0)
        url = f'/api/bookings/{booking.pk}/'

        for method in ('get', 'put', 'patch', 'delete'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 404)

    def test_put_same_workshop_is_allowed_even_when_full(self):
        booking = Booking.objects.create(
            user=self.user, workshop=self.workshop,
        )
        self.client.force_authenticate(self.user)
        response = self.client.put(f'/api/bookings/{booking.pk}/', {
            'workshop_id': self.workshop.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.workshop.bookings.count(), 1)

    def test_empty_patch_keeps_booking(self):
        booking = Booking.objects.create(
            user=self.user, workshop=self.workshop,
        )
        self.client.force_authenticate(self.user)
        self.client.raise_request_exception = False
        response = self.client.patch(f'/api/bookings/{booking.pk}/', {})
        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.workshop_id, self.workshop.pk)

    def test_move_booking_frees_old_seat(self):
        booking = Booking.objects.create(
            user=self.user, workshop=self.workshop,
        )
        self.client.force_authenticate(self.user)
        response = self.client.patch(f'/api/bookings/{booking.pk}/', {
            'workshop_id': self.next_workshop.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.workshop.bookings.count(), 0)
        self.assertEqual(self.next_workshop.bookings.count(), 1)

    def test_failed_move_preserves_original_booking(self):
        booking = Booking.objects.create(
            user=self.user, workshop=self.next_workshop,
        )
        Booking.objects.create(user=self.other, workshop=self.workshop)
        self.client.force_authenticate(self.user)
        response = self.client.put(f'/api/bookings/{booking.pk}/', {
            'workshop_id': self.workshop.pk,
        })
        self.assertEqual(response.status_code, 400)
        booking.refresh_from_db()
        self.assertEqual(booking.workshop_id, self.next_workshop.pk)

    def test_cancellation_allows_another_user_to_book(self):
        booking = Booking.objects.create(
            user=self.user, workshop=self.workshop,
        )
        self.client.force_authenticate(self.user)
        response = self.client.delete(f'/api/bookings/{booking.pk}/')
        self.assertEqual(response.status_code, 204)
        self.client.force_authenticate(self.other)
        response = self.client.post('/api/bookings/', {
            'workshop_id': self.workshop.pk,
        })
        self.assertEqual(response.status_code, 201)

    def test_admin_cannot_reduce_capacity_below_existing_bookings(self):
        Booking.objects.create(user=self.user, workshop=self.next_workshop)
        Booking.objects.create(user=self.other, workshop=self.next_workshop)
        self.admin.role = 'admin'
        self.admin.save()
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f'/api/workshops/{self.next_workshop.pk}/', {'capacity': 1},
        )
        self.assertEqual(response.status_code, 400)
        self.next_workshop.refresh_from_db()
        self.assertEqual(self.next_workshop.capacity, 2)

    def test_capacity_is_checked_again_when_booking_is_saved(self):
        # Оба запроса получили данные до того, как первое место заняли.
        first = BookingSerializer(
            data={'workshop_id': self.workshop.pk},
            context={'request': SimpleNamespace(user=self.user)},
        )
        second = BookingSerializer(
            data={'workshop_id': self.workshop.pk},
            context={'request': SimpleNamespace(user=self.other)},
        )
        first.is_valid(raise_exception=True)
        second.is_valid(raise_exception=True)
        first.save(user=self.user)
        with self.assertRaises(ValidationError):
            second.save(user=self.other)
        self.assertEqual(self.workshop.bookings.count(), 1)

    def test_duplicate_is_checked_again_when_booking_is_saved(self):
        serializers = [
            BookingSerializer(
                data={'workshop_id': self.next_workshop.pk},
                context={'request': SimpleNamespace(user=self.user)},
            )
            for _ in range(2)
        ]

        for serializer in serializers:
            serializer.is_valid(raise_exception=True)

        serializers[0].save(user=self.user)
        with self.assertRaises(ValidationError):
            serializers[1].save(user=self.user)


class ConcurrentBookingTests(TransactionTestCase):
    """Проверяем настоящие одновременные запросы на PostgreSQL."""

    def setUp(self):
        self.workshop = Workshop.objects.create(
            title='Последнее место',
            description='Проверка одновременной записи',
            date=timezone.now() + timedelta(days=1), capacity=1,
        )
        self.users = [
            User.objects.create_user(
                username=f'user{i}', email=f'user{i}@example.com',
            )
            for i in range(2)
        ]

    def book_at_the_same_time(self, users):
        # Два потока используют разные соединения с БД и стартуют вместе.
        barrier = Barrier(2)

        def book(user):
            try:
                client = APIClient()
                client.force_authenticate(user)
                barrier.wait(timeout=10)

                return client.post('/api/bookings/', {
                    'workshop_id': self.workshop.pk,
                }).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return sorted(pool.map(book, users))

    def test_two_users_cannot_take_the_last_seat(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertEqual(self.book_at_the_same_time(self.users), [201, 400])
        self.assertEqual(self.workshop.bookings.count(), 1)

    def test_simultaneous_duplicate_returns_validation_error(self):
        self.workshop.capacity = 2
        self.workshop.save()
        responses = self.book_at_the_same_time([self.users[0], self.users[0]])
        self.assertEqual(responses, [201, 400])
        self.assertEqual(self.workshop.bookings.count(), 1)
