from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile
from allauth.account.signals import user_signed_up
from django.contrib import messages
from allauth.socialaccount.signals import pre_social_login
from allauth.account.models import EmailAddress

@receiver(pre_social_login)
def pre_social_login_verify(request, sociallogin, **kwargs):
    """
    Called before a social login is completed.
    Ensures that if the social provider confirms the email is verified,
    we sync that to both the allauth EmailAddress model and our UserProfile.
    """
    user = sociallogin.user
    if not user.email:
        return

    # Extract verification status from provider data
    is_provider_verified = (
        sociallogin.account.extra_data.get('email_verified') or 
        sociallogin.account.extra_data.get('verified') or
        False
    )

    if is_provider_verified:
        # 1. Sync allauth EmailAddress model
        email_obj, created = EmailAddress.objects.get_or_create(
            user=user, 
            email=user.email,
            defaults={'verified': True, 'primary': True}
        )
        if not email_obj.verified:
            email_obj.verified = True
            email_obj.save()

        # 2. Sync our local UserProfile if it exists
        try:
            profile = user.userprofile
            if not profile.is_email_verified:
                profile.is_email_verified = True
                profile.save(update_fields=['is_email_verified'])
        except Exception:
            pass # Profile might be created in student_dashboard or user_signed_up later

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
        
        # Auto-verify email if social provider says so
        is_provider_verified = data.get('email_verified') or data.get('verified') or False
        if is_provider_verified:
            profile.is_email_verified = True
            # Also ensure allauth record is verified
            EmailAddress.objects.update_or_create(
                user=user, email=user.email,
                defaults={'verified': True, 'primary': True}
            )
            
        profile.save()
            
        messages.success(request, f"Welcome to Advise-AI, {user.first_name or user.username}! Your student account is ready.")
    else:
        # Fallback for standard signups
        if created:
            profile.role = 'student'
            profile.save()
