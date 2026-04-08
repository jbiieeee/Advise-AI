from core.models import Message, UserProfile
from django.contrib.auth.models import User

def notifications(request):
    # ... existing code ...
    if not request.user.is_authenticated:
        return {'unread_notifications_count': 0}

    user = request.user
    role = None
    if hasattr(user, 'userprofile'):
        role = user.userprofile.role
    elif user.is_superuser:
        role = 'admin'
    
    count = 0
    if role == 'student':
        adviser_user_ids = list(UserProfile.objects.filter(role='adviser').values_list('user_id', flat=True))
        admin_user_ids = list(User.objects.filter(is_superuser=True).values_list('id', flat=True))
        all_staff_ids = list(set(adviser_user_ids + admin_user_ids))
        
        count = Message.objects.filter(receiver=user, sender__in=all_staff_ids, is_read=False).count()
        
    elif role in ['adviser', 'admin']:
        adviser_user_ids = list(UserProfile.objects.filter(role='adviser').values_list('user_id', flat=True))
        admin_user_ids = list(User.objects.filter(is_superuser=True).values_list('id', flat=True))
        all_staff_ids = list(set(adviser_user_ids + admin_user_ids))
        
        msg_count = Message.objects.filter(
            sender__userprofile__role='student',
            receiver__in=all_staff_ids,
            is_read=False
        ).count()
        
        from core.models import Notification
        notif_count = Notification.objects.filter(user=user, is_read=False).count()
        
        staff_msgs_count = Message.objects.filter(
            receiver=user,
            is_staff_only=True,
            is_read=False
        ).count()
        
        count = msg_count + notif_count + staff_msgs_count
        
    return {'unread_notifications_count': count}

def social_apps(request):
    """Returns a set of provider IDs that have a SocialApp configured in the DB."""
    try:
        from allauth.socialaccount.models import SocialApp
        from django.conf import settings
        # Get apps linked to current SITE_ID
        active_apps = SocialApp.objects.filter(sites__id=settings.SITE_ID).values_list('provider', flat=True)
        return {'active_social_providers': set(active_apps)}
    except:
        return {'active_social_providers': set()}
