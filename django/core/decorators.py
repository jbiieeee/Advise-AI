"""
core/decorators.py — Centralized RBAC Decorators for Advise-AI

Usage:
    @student_required    — Only students (and admins for support) can access.
    @adviser_required    — Only advisers (and admins for support) can access.
    @admin_required      — Only admins / superusers can access.

Behavior:
    - Unauthenticated users are redirected to the login page.
    - Authenticated users accessing the wrong role's page are redirected to
      THEIR OWN dashboard with a clear error message.
    - Superusers (admins) bypass student and adviser checks for support access.
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def _get_role(user):
    """Helper: Returns the user's role string. Superusers are always 'admin'."""
    if user.is_superuser:
        return 'admin'
    profile = getattr(user, 'userprofile', None)
    if profile:
        return profile.role
    return None


def _redirect_to_home(request, role):
    """
    Redirects a user to their own dashboard with a permission-denied message.
    """
    messages.error(request, "You do not have permission to access that page.")
    if role == 'admin':
        return redirect('admin_dashboard')
    elif role == 'adviser':
        return redirect('adviser_dashboard')
    else:
        return redirect('student_dashboard')


def student_required(view_func):
    """
    Ensures the authenticated user is a student.
    Admins (superusers) are allowed through for support purposes.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        role = _get_role(request.user)

        # Admins bypass for support access
        if role == 'admin':
            return view_func(request, *args, **kwargs)

        if role != 'student':
            return _redirect_to_home(request, role)

        return view_func(request, *args, **kwargs)

    return wrapper


def adviser_required(view_func):
    """
    Ensures the authenticated user is an adviser.
    Admins (superusers) are allowed through for support purposes.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        role = _get_role(request.user)

        # Admins bypass for support access
        if role == 'admin':
            return view_func(request, *args, **kwargs)

        if role != 'adviser':
            return _redirect_to_home(request, role)

        return view_func(request, *args, **kwargs)

    return wrapper


def admin_required(view_func):
    """
    Ensures the authenticated user is an admin or superuser.
    No bypass — this is the top-level access guard.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        role = _get_role(request.user)

        if role != 'admin':
            return _redirect_to_home(request, role)

        return view_func(request, *args, **kwargs)

    return wrapper
