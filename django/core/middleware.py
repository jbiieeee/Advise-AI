from django.utils import timezone
from .models import UserProfile

class LastActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # We update last_activity on every request if possible
            # To minimize DB writes, we could check if profile exists first
            profile = getattr(request.user, 'userprofile', None)
            if profile:
                # Update last_activity without triggering a full model save if possible
                # But auto_now=True handles it if we just call save()
                # Actually, simple update is faster: UserProfile.objects.filter(id=profile.id).update(last_activity=timezone.now())
                UserProfile.objects.filter(id=profile.id).update(last_activity=timezone.now())

        response = self.get_response(request)
        return response
