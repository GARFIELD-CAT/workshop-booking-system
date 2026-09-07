from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Booking, User, Workshop


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('email', 'username', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser')
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Роль в системе', {'fields': ('role',)}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ('Дополнительные данные', {'fields': ('email', 'role')}),
    )


class ReadOnlyAdmin(admin.ModelAdmin):
    # Изменения мастер-классов и броней выполняются через API,
    # чтобы нельзя было обойти валидацию наличия мест и даты через админку.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Workshop)
class WorkshopAdmin(ReadOnlyAdmin):
    list_display = ('title', 'date', 'capacity')
    search_fields = ('title',)


@admin.register(Booking)
class BookingAdmin(ReadOnlyAdmin):
    list_display = ('user', 'workshop', 'created_at')
    list_select_related = ('user', 'workshop')
