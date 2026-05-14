from rest_framework import permissions

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    GET, HEAD, OPTIONS — доступны всем.
    POST, PUT, PATCH, DELETE — только администраторам (роль 'admin').
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.is_authenticated and request.user.role == 'admin'