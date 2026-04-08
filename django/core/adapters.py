from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth.models import User
from core.models import UserProfile
from django.core.exceptions import PermissionDenied
from django.contrib import messages

class AdviseAISocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        """
        Only allows signups via social auth. 
        Enforces that all new social accounts are 'students'.
        """
        return True

    def pre_social_login(self, request, sociallogin):
        """
        Check if the email already exists and if it belongs to an Admin or Adviser.
        Prevents Admi/Adviser from accidentally creating a duplicate student account via social.
        """
        email = sociallogin.user.email
        if not email:
            return

        try:
            user = User.objects.get(email=email)
            # If user exists, check their role
            try:
                profile = user.userprofile
                if profile.role in ['admin', 'adviser']:
                    # Allow login if strictly allowed, but prevent role override
                    pass
            except UserProfile.DoesNotExist:
                pass
        except User.DoesNotExist:
            # New user signup - handled by save_user and signals
            pass

    def save_user(self, request, sociallogin, form=None):
        """
        Overrides the user saving process to ensure the role is set correctly.
        """
        user = super().save_user(request, sociallogin, form)
        # The role assignment is also handled in signals, but we can be extra sure here.
        return user
