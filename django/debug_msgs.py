import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import Message, UserProfile
from django.contrib.auth.models import User

print("=== ALL MESSAGES ===")
msgs = Message.objects.all().order_by('-sent_at')
if not msgs:
    print("  (no messages in DB)")
for m in msgs:
    try:
        sr = m.sender.userprofile.role
    except:
        sr = "?"
    try:
        rr = m.receiver.userprofile.role
    except:
        rr = "?"
    print(f"  MSG id={m.id} from={m.sender.username}({sr}) -> to={m.receiver.username}({rr}) read={m.is_read} | {m.content[:60]}")

print()
print("=== ADVISERS ===")
for p in UserProfile.objects.filter(role='adviser'):
    print(f"  User.id={p.user.id} username={p.user.username} name={p.user.first_name} {p.user.last_name}")

print()
print("=== STUDENTS ===")
for p in UserProfile.objects.filter(role='student'):
    print(f"  User.id={p.user.id} username={p.user.username} name={p.user.first_name} {p.user.last_name}")
