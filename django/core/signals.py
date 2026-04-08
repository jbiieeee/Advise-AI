from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile
from allauth.account.signals import user_signed_up

@receiver(user_signed_up)
def social_login_profile_sync(request, user, **kwargs):
    """
    Ensure a UserProfile exists for users signing up via social accounts.
    Syncs basic data if available.
    """
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    # If the user has a social account, we can try to pull more info
    social_account = getattr(user, 'socialaccount_set', None)
    if social_account and social_account.exists():
        data = social_account.first().extra_data
        # Optionally sync name or other fields if User model doesn't have them
        if not user.first_name and 'first_name' in data:
            user.first_name = data['first_name']
        if not user.last_name and 'last_name' in data:
            user.last_name = data['last_name']
        user.save()

    if created:
        profile.role = 'student'
        profile.save()
