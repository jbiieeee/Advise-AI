from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile
from allauth.account.signals import user_signed_up

from django.contrib import messages

@receiver(user_signed_up)
def social_login_profile_sync(request, user, **kwargs):
    """
    Called after a user signs up via a social provider.
    Ensures a UserProfile exists, defaults role to 'student', and syncs metadata.
    """
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    # Check if this is a social signup
    sociallogin = kwargs.get('sociallogin')
    if sociallogin:
        data = sociallogin.account.extra_data
        
        # Google/Facebook/GitHub handle names differently
        first_name = data.get('first_name') or data.get('given_name') or ''
        last_name = data.get('last_name') or data.get('family_name') or ''
        
        # Fallback for name strings
        if not first_name and data.get('name'):
            parts = data.get('name').split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ''

        user_changed = False
        if not user.first_name and first_name:
            user.first_name = first_name[:150]
            user_changed = True
        if not user.last_name and last_name:
            user.last_name = last_name[:150]
            user_changed = True
        
        if user_changed:
            user.save()

        # All social signups are Students (Security enforcement)
        if created or not profile.role:
            profile.role = 'student'
            profile.save()
            
        messages.success(request, f"Welcome to Advise-AI, {user.first_name or user.username}! Your student account is ready.")
    else:
        # Fallback for standard signups
        if created:
            profile.role = 'student'
            profile.save()
