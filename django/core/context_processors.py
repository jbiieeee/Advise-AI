from core.models import Message, UserProfile
from django.contrib.auth.models import User

def notifications(request):
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
        
        count = Message.objects.filter(
            sender__userprofile__role='student',
            receiver__in=all_staff_ids,
            is_read=False
        ).count()
        
    return {'unread_notifications_count': count}
