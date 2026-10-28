"""
Custom permissions for Tasonaliz.
Ensures users can only edit or delete their own comments (Section 3.6 & 10).
"""

from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Read permissions are allowed to any request.
    Write/Edit/Delete permissions are strictly restricted to the author of the comment.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and obj.user_id == request.user.id)
