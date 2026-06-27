from rest_framework import permissions

class IsManager(permissions.BasePermission):

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and 
            request.user.groups.filter(name='Manager').exists()
        )

class IsStaff(permissions.BasePermission):

    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            request.user.groups.filter(name='Staff').exists()
        )