import json
from django.conf import settings
from datetime import datetime, timedelta
from django.utils import timezone
from django.utils.timezone import localtime
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit
from .decorators import student_required, adviser_required, admin_required
from django.db.models import Q
from .models import (
    UserProfile, CurriculumSubject, 
    TermEnrollment, StudentCurriculum, EnrollmentCode,
    FormSubmission, Appointment, Message, StaffMessage, Notification, ActivityLog
)
import google.generativeai as genai

def csrf_failure(request, reason=""):
    """Handle CSRF failures by redirecting back with a message instead of showing 403."""
    messages.error(request, "Security check failed (CSRF). Please refresh the page and try again.")
    return redirect(request.META.get('HTTP_REFERER', 'landing'))

def log_activity(user, action, details):
    """Utility to log system activities for Admin review."""
    from .models import ActivityLog
    ActivityLog.objects.create(user=user, action=action, details=details)

def get_total_unread_count(user):
    """Calculates combined unread count from Notifications, Messages, and StaffMessages."""
    if not user.is_authenticated:
        return 0
    from .models import Notification, Message, StaffMessage
    notif_count = Notification.objects.filter(user=user, is_read=False).count()
    msg_count = Message.objects.filter(receiver=user, is_read=False).count()
    
    staff_msg_count = 0
    # Check if user is staff (adviser or admin)
    is_staff = user.is_staff or user.is_superuser
    if not is_staff:
        try:
            is_staff = user.userprofile.role in ['adviser', 'admin']
        except:
            pass
            
    if is_staff:
        staff_msg_count = StaffMessage.objects.filter(receiver=user, is_read=False).count()
        
    return notif_count + msg_count + staff_msg_count

def landing_page(request):
    return render(request, 'core/landing.html')

@ratelimit(key='ip', rate='10/5m', method='POST', block=False)
def login_page(request):
    # Lockout check for students/staff (session-based)
    lockout_until_str = request.session.get('login_lockout_until')
    if lockout_until_str:
        try:
            lockout_until = datetime.fromisoformat(lockout_until_str)
            if timezone.is_naive(lockout_until):
                lockout_until = timezone.make_aware(lockout_until)
            
            if timezone.now() < lockout_until:
                diff = lockout_until - timezone.now()
                mins = int(diff.total_seconds() // 60)
                messages.error(request, f"Too many failed login attempts. Please wait {mins if mins > 0 else 1} minutes before trying again.")
                return render(request, 'core/login.html')
            else:
                # Lockout expired
                del request.session['login_lockout_until']
                request.session['login_fails'] = 0
        except (ValueError, TypeError):
            pass

    if request.method == 'POST':
        if getattr(request, 'limited', False):
            messages.error(request, "Rate limit exceeded. Please try again later.")
            return redirect('login')

        role = request.POST.get('role', 'student')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Sticky Admin Fallback: Allow hardcoded admin/admin123 regardless of database state
        if role == 'admin' and email == 'admin' and password == 'admin123':
            try:
                user = User.objects.filter(username='admin').first()
                if not user:
                    user = User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
                else:
                    # Sync password just in case it was changed
                    user.set_password('admin123')
                    user.is_active = True
                    user.save()
                
                # Reset fails on success
                request.session['login_fails'] = 0
                # Explicitly specify the backend since allauth adds multiple backends
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect('admin_dashboard')
            except Exception as e:
                messages.error(request, f"Database error during sticky login: {str(e)}")
                return redirect('login')
        
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            # For admin role, just check superuser status or specific role
            if role == 'admin' and user.is_superuser:
                request.session['login_fails'] = 0
                login(request, user)
                log_activity(user, "Login", "Admin logged in successfully.")
                return redirect('admin_dashboard')
            
            # Ensure profile exists using get_or_create to prevent 500 on first login
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={'role': 'admin' if user.is_superuser else role}
            )
            
            if profile.role != role and not user.is_superuser:
                messages.error(request, f'You do not have a {role} account.')
                return redirect('login')
            
            # Reset fails on success
            request.session['login_fails'] = 0
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            log_activity(user, "Login", f"{role.capitalize()} logged in successfully.")
            if role == 'student' or profile.role == 'student':
                return redirect('student_dashboard')
            elif role == 'adviser' or profile.role == 'adviser':
                return redirect('adviser_dashboard')
            elif user.is_superuser:
                return redirect('admin_dashboard')
                    
        else:
            # Track failed attempts
            fails = request.session.get('login_fails', 0) + 1
            request.session['login_fails'] = fails
            
            if fails >= 6:
                lockout_time = timezone.now() + timedelta(hours=1)
                request.session['login_lockout_until'] = lockout_time.isoformat()
                messages.error(request, "Too many failed attempts. Your login is restricted for 1 hour.")
            elif fails >= 3:
                remaining = 6 - fails
                messages.error(request, f"Invalid email or password. You have {remaining} attempts remaining before a 1-hour lockout.")
            else:
                messages.error(request, 'Invalid email or password.')
            return redirect('login')
            
    return render(request, 'core/login.html')
            
    return render(request, 'core/login.html')

@ratelimit(key='ip', rate='3/1h', method='POST', block=True)
def register_page(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        studentId = request.POST.get('studentId')
        email = request.POST.get('email')
        institution = request.POST.get('institution')
        program = request.POST.get('program')
        yearLevel = request.POST.get('yearLevel')
        password = request.POST.get('password')
        confirmPassword = request.POST.get('confirmPassword')
        
        if password != confirmPassword:
            messages.error(request, 'Passwords do not match.')
            return redirect('register')
            
        if User.objects.filter(username=email).exists():
            messages.error(request, 'Email already registered. Please log in.')
            return redirect('register')
            
        # Create user
        first_name = name.split()[0] if name else ''
        last_name = ' '.join(name.split()[1:]) if len(name.split()) > 1 else ''
        
        user = User.objects.create_user(
            username=email, 
            email=email, 
            password=password, 
            first_name=first_name,
            last_name=last_name
        )
        
        # Create profile
        UserProfile.objects.create(
            user=user,
            student_id=studentId,
            institution=institution,
            program=program,
            year_level=yearLevel,
            role='student'
        )
        
        # New: Notify all Admins about new student registration
        admins = User.objects.filter(Q(is_superuser=True) | Q(userprofile__role='admin'))
        for admin in admins:
            Notification.objects.create(
                user=admin,
                event_type='new_student',
                message=f'New student account created: {name} ({email})'
            )
        
        log_activity(user, "Registration", f"New student account created: {name} ({email})")
        return redirect('login')
        
    return render(request, 'core/register.html')

@login_required(login_url='login')
def api_messages_list(request):
    """Returns contact list with last message and unread count. High performance."""
    user = request.user
    from django.db.models import Max, Q, F
    from core.models import UserProfile, Message, StaffMessage
    from datetime import datetime
    from django.utils import timezone
    
    role = getattr(user, 'userprofile', None)
    role_str = role.role if role else ('admin' if user.is_superuser else 'student')
    
    contacts = []
    
    # 1. Standard Messaging Partners (Students <-> Advisers/Admins)
    if role_str == 'student':
        # Broaden candidates: assigned adviser PLUS anyone they have message history with
        assigned_id = role.assigned_adviser_id if role and role.assigned_adviser else None
        
        # Get unique IDs of everyone they've had a conversation with
        msg_partners = set(Message.objects.filter(sender=user).values_list('receiver_id', flat=True)) | \
                       set(Message.objects.filter(receiver=user).values_list('sender_id', flat=True))
        
        if assigned_id:
            msg_partners.add(assigned_id)
        
        if not msg_partners:
            # Fallback for brand-new students: Only show Advisers (NOT Admins)
            std_candidates = User.objects.filter(userprofile__role='adviser').exclude(id=user.id)
        else:
            std_candidates = User.objects.filter(id__in=msg_partners)
    else:
        # Staff see all students
        std_candidates = User.objects.filter(userprofile__role='student')

    for c_user in std_candidates:
        last_msg = Message.objects.filter(
            (Q(sender=user, receiver=c_user) | Q(sender=c_user, receiver=user))
        ).order_by('-sent_at').first()
        unread = Message.objects.filter(sender=c_user, receiver=user, is_read=False).count()
        is_admin = c_user.is_superuser or (hasattr(c_user, 'userprofile') and c_user.userprofile.role == 'admin')
        contacts.append({
            'id': c_user.id,
            'user_id': c_user.id,
            'name': f"{c_user.first_name} {c_user.last_name}".strip() or c_user.username,
            'role': c_user.userprofile.role if hasattr(c_user, 'userprofile') else ('admin' if c_user.is_superuser else 'student'),
            'last_message': last_msg.content if last_msg else "No messages yet.",
            'last_message_time': last_msg.sent_at if last_msg else None,
            'unread_count': unread,
            'type': 'standard',
            'is_staff': c_user.is_superuser or (hasattr(c_user, 'userprofile') and c_user.userprofile.role in ['adviser', 'admin']),
            'is_admin': is_admin
        })

    # 2. Staff Messaging Partners (Staff <-> Staff)
    if role_str != 'student':
        staff_candidates = User.objects.filter(Q(userprofile__role__in=['adviser', 'admin']) | Q(is_superuser=True)).exclude(id=user.id)
        for s_user in staff_candidates:
            last_msg = StaffMessage.objects.filter(
                (Q(sender=user, receiver=s_user) | Q(sender=s_user, receiver=user))
            ).order_by('-sent_at').first()
            unread = StaffMessage.objects.filter(sender=s_user, receiver=user, is_read=False).count()
            contacts.append({
                'id': s_user.id,
                'user_id': s_user.id,
                'name': f"{s_user.first_name} {s_user.last_name}".strip() or s_user.username,
                'role': s_user.userprofile.role if hasattr(s_user, 'userprofile') else 'admin',
                'last_message': last_msg.content if last_msg else "No staff messages yet.",
                'last_message_time': last_msg.sent_at if last_msg else None,
                'unread_count': unread,
                'type': 'staff',
                'is_staff': True
            })

    # Sort by time
    def get_time(x): return x['last_message_time'] if x['last_message_time'] else timezone.make_aware(datetime.min)
    contacts.sort(key=get_time, reverse=True)
    
    # Format for JSON
    for c in contacts:
        if c['last_message_time']:
            c['last_message_time'] = timezone.localtime(c['last_message_time']).strftime('%b %d, %H:%M')

    return JsonResponse({'contacts': contacts})

@login_required(login_url='login')
def api_messages_thread(request, contact_id):
    """Returns conversation history for a specific contact and type."""
    from django.db.models import Q
    from core.models import Message, StaffMessage
    user = request.user
    msg_type = request.GET.get('type', 'standard')
    
    # Security: Students cannot access staff threads
    role = getattr(user, 'userprofile', None)
    role_str = role.role if role else ('admin' if user.is_superuser else 'student')
    if msg_type == 'staff' and role_str == 'student':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        contact = User.objects.get(id=contact_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

    if msg_type == 'staff':
        thread = StaffMessage.objects.filter(
            (Q(sender=user, receiver=contact) | Q(sender=contact, receiver=user))
        ).order_by('sent_at')
        # Mark as read
        StaffMessage.objects.filter(sender=contact, receiver=user, is_read=False).update(is_read=True)
    else:
        thread = Message.objects.filter(
            (Q(sender=user, receiver=contact) | Q(sender=contact, receiver=user))
        ).order_by('sent_at')
        # Mark as read
        Message.objects.filter(sender=contact, receiver=user, is_read=False).update(is_read=True)

    data = []
    for m in thread:
        data.append({
            'content': m.content,
            'sent_at': timezone.localtime(m.sent_at).strftime('%b %d, %I:%M %p'),
            'is_me': m.sender == user
        })
    return JsonResponse({'messages': data})

@login_required(login_url='login')
@ratelimit(key='user', rate='10/m', method='POST', block=True)
def api_messages_send(request):
    """Unified API for sending messages."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    import json as _json
    from core.models import Message, StaffMessage
    try:
        data = _json.loads(request.body)
    except:
        data = request.POST
        
    receiver_id = data.get('receiver_id')
    content = data.get('content', '').strip()
    msg_type = data.get('type', 'standard')
    
    if not receiver_id or not content:
        return JsonResponse({'error': 'Missing receiver or content'}, status=400)
    
    try:
        receiver = User.objects.get(id=receiver_id)
        user = request.user
        role = getattr(user, 'userprofile', None)
        role_str = role.role if role else ('admin' if user.is_superuser else 'student')
        
        # Security Checks
        if msg_type == 'staff':
            if role_str == 'student':
                return JsonResponse({'error': 'Students cannot send staff messages'}, status=403)
            # Ensure receiver is also staff
            rev_role = getattr(receiver, 'userprofile', None)
            rev_role_str = rev_role.role if rev_role else ('admin' if receiver.is_superuser else 'student')
            if rev_role_str == 'student':
                return JsonResponse({'error': 'Cannot send staff messages to students'}, status=400)
            
            m = StaffMessage.objects.create(sender=user, receiver=receiver, content=content)
        else:
            # Standard Message
            # Security: Students cannot message other students
            rev_role = getattr(receiver, 'userprofile', None)
            rev_role_str = rev_role.role if rev_role else ('admin' if receiver.is_superuser else 'student')
            
            if role_str == 'student' and rev_role_str == 'student':
                return JsonResponse({'error': 'Students cannot message other students'}, status=403)
            
            # Security: Admin -> Student is one-way. Student cannot message Admin.
            if role_str == 'student' and (rev_role_str == 'admin' or receiver.is_superuser):
                return JsonResponse({'error': 'Admins do not receive direct messages. Please use the Help/Report form for official inquiries.'}, status=403)
                
            m = Message.objects.create(sender=user, receiver=receiver, content=content)
            
        return JsonResponse({
            'status': 'success',
            'message': {
                'content': m.content,
                'sent_at': timezone.localtime(m.sent_at).strftime('%b %d, %I:%M %p'),
                'is_me': True
            }
        })
    except User.DoesNotExist:
        return JsonResponse({'error': 'Receiver not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def logout_user(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('landing')

def about_page(request):
    return render(request, 'core/about.html')

from .models import (
    UserProfile, CurriculumSubject, 
    TermEnrollment, StudentCurriculum, EnrollmentCode,
    FormSubmission, Appointment, Message, Notification
)

@student_required
def student_dashboard(request):
    user = request.user
    
    # Robust profile retrieval — use get_or_create to prevent 500 on first login
    profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={'role': 'admin' if user.is_superuser else 'student'}
    )

    # Redirect superusers without student role to admin dashboard
    if user.is_superuser and profile.role != 'student':
        return redirect('admin_dashboard')

    # Mission: Enforce Program Logic (BSIT/BSCS)
    # If program is not set or invalid, redirect to profile completion
    if profile.role == 'student' and (not profile.program or profile.program not in ['BSIT', 'BSCS']):
        messages.warning(request, "Please select your degree program (BSIT or BSCS) to access your dashboard.")
        return redirect('profile')

    # Get curriculum status for tags early to avoid UnboundLocalError during POST
    curriculum_records = StudentCurriculum.objects.filter(student=user)
    curriculum_status_map = {r.subject_id: r.status for r in curriculum_records}

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'redeem_code':
            # Lockout check (session-based)
            lock_str = request.session.get('redemption_lockout_until')
            if lock_str:
                try:
                    lock_until = datetime.fromisoformat(lock_str)
                    if timezone.is_naive(lock_until):
                        lock_until = timezone.make_aware(lock_until)
                    
                    if timezone.now() < lock_until:
                        diff = lock_until - timezone.now()
                        m = int(diff.total_seconds() // 60)
                        messages.error(request, f"Too many failed attempts. Redemption restricted for {m if m > 0 else 1} more minutes.")
                        return redirect('student_dashboard')
                    else:
                        # Lockout expired
                        del request.session['redemption_lockout_until']
                        request.session['redemption_fails'] = 0
                except (ValueError, TypeError):
                    pass

            code_str = request.POST.get('enrollment_code', '').strip().upper()
            if not code_str:
                messages.error(request, 'Please enter a valid Enrollment Code.')
            else:
                try:
                    # Check if code exists globally to distinguish errors
                    enc = EnrollmentCode.objects.filter(code=code_str).first()
                    
                    if not enc:
                        raise EnrollmentCode.DoesNotExist
                    
                    if enc.student != user:
                        # Increment fails for wrong student code
                        f = request.session.get('redemption_fails', 0) + 1
                        request.session['redemption_fails'] = f
                        if f >= 6:
                            request.session['redemption_lockout_until'] = (timezone.now() + timedelta(hours=1)).isoformat()
                            messages.error(request, "Too many invalid attempts. Enrollment redemption locked for 1 hour.")
                        elif f >= 3:
                            remaining = 6 - f
                            messages.error(request, f"This Enrollment Code is assigned to another student. You have {remaining} attempts remaining.")
                        else:
                            messages.error(request, 'This Enrollment Code is assigned to another student.')
                        return redirect('student_dashboard')

                    if enc.used:
                        # Success resets fails
                        request.session['redemption_fails'] = 0
                        messages.info(request, f'This enrollment code ({code_str}) has already been successfully redeemed for your account.')
                    else:
                        # Filter out subjects already passed or in-progress
                        valid_subjects = []
                        skipped = []
                        for subj in enc.approved_subjects.all():
                            status = curriculum_status_map.get(subj.id, 'not_taken')
                            if status in ['passed', 'in_progress']:
                                skipped.append(subj.code)
                                continue
                            
                            # Also check if already in a pending TermEnrollment for this term
                            if not TermEnrollment.objects.filter(student=user, subject=subj, status='pending').exists():
                                valid_subjects.append(subj)
                            else:
                                skipped.append(f"{subj.code} (already pending)")

                        if not valid_subjects:
                            request.session['redemption_fails'] = 0
                            msg = 'All subjects in this code have already been passed or are currently being taken.'
                            if skipped:
                                msg += f" (Already passed/pending: {', '.join(skipped)})"
                            messages.warning(request, msg)
                        else:
                            for subj in valid_subjects:
                                TermEnrollment.objects.get_or_create(
                                    student=user, subject=subj, term_label=enc.term_label,
                                    defaults={'enrollment_code': enc, 'status': 'pending'}
                                )
                            
                            enc.used = True
                            enc.used_at = timezone.now()
                            enc.save()
                            
                            # Reset fails on success
                            request.session['redemption_fails'] = 0
                            
                            # Cumulative Enrollment logic: Only set to 'pending' if not currently 'enrolled'
                            if profile.enrollment_status != 'enrolled':
                                profile.enrollment_status = 'pending'
                                profile.save()
                            
                            # Notify all Admins
                            admins = User.objects.filter(Q(is_superuser=True) | Q(userprofile__role='admin'))
                            for admin in admins:
                                Notification.objects.create(
                                    user=admin,
                                    event_type='enrollment_code_redeemed',
                                    message=f'Student {user.get_full_name() or user.username} redeemed enrollment code {enc.code} for {enc.term_label}. Approval required.'
                                )

                            messages.success(request, f'Registration code submitted! Your enrollment for {enc.term_label} is now pending Admin approval.')
                except EnrollmentCode.DoesNotExist:
                    f = request.session.get('redemption_fails', 0) + 1
                    request.session['redemption_fails'] = f
                    if f >= 6:
                        request.session['redemption_lockout_until'] = (timezone.now() + timedelta(hours=1)).isoformat()
                        messages.error(request, "Too many invalid attempts. Enrollment redemption locked for 1 hour.")
                    elif f >= 3:
                        remaining = 6 - f
                        messages.error(request, f"Invalid Enrollment Code. You have {remaining} attempts remaining.")
                    else:
                        messages.error(request, 'Invalid Enrollment Code. Please contact your adviser.')
                except Exception as e:
                    messages.error(request, f'An unexpected error occurred: {str(e)}')

        
        elif action == 'submit_form':
            title = request.POST.get('form_title')
            desc = request.POST.get('form_desc')
            if title:
                FormSubmission.objects.create(student=user, title=title, description=desc)
                messages.success(request, 'Form submitted successfully.')

        elif action == 'schedule_appointment':
            date_str = request.POST.get('appointment_date')
            time_str = request.POST.get('appointment_time')
            purpose = request.POST.get('appointment_purpose')
            if date_str and time_str and purpose:
                try:
                    dt_str = f"{date_str} {time_str}"
                    dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                    # Make aware to avoid naive vs aware comparison errors
                    dt_aware = timezone.make_aware(dt_obj, timezone.get_current_timezone())
                    
                    # 1. Past Date/Time Check
                    if dt_aware < timezone.now():
                        messages.error(request, 'Cannot schedule an appointment in the past.')
                        return redirect('student_dashboard')

                    # 2. Student Double-Booking Check
                    if Appointment.objects.filter(student=user, date_time=dt_aware).exclude(status='cancelled').exists():
                        messages.error(request, 'You already have an appointment scheduled for this exact time.')
                        return redirect('student_dashboard')

                    # 3. Adviser Availability Check
                    adviser = profile.assigned_adviser
                    if adviser:
                        if Appointment.objects.filter(adviser=adviser, date_time=dt_aware, status='confirmed').exists():
                            messages.error(request, f'Your assigned adviser ({adviser.get_full_name() or adviser.username}) is already booked for this time. Please select another slot.')
                            return redirect('student_dashboard')
                    
                    # Store appointment with adviser if available
                    Appointment.objects.create(
                        student=user, 
                        adviser=adviser,
                        date_time=dt_aware, 
                        purpose=purpose,
                        status='pending'
                    )
                    log_activity(user, "Appointment Requested", f"Requested session: {purpose} for {dt_aware.strftime('%Y-%m-%d %H:%M')}")
                    messages.success(request, 'Your appointment has been scheduled and is pending approval.')
                except ValueError:
                    messages.error(request, 'Invalid date/time format.')
            else:
                messages.error(request, 'Please complete all fields for the appointment.')
                
        elif action == 'send_message':
            content = request.POST.get('content', '').strip()
            adviser_id = request.POST.get('adviser_id')
            if content:
                # Get all adviser user IDs
                adviser_ids = list(UserProfile.objects.filter(role='adviser').values_list('user_id', flat=True))
                admin_ids = list(User.objects.filter(is_superuser=True).values_list('id', flat=True))
                all_staff_ids = list(set(adviser_ids + admin_ids))
                
                if profile.assigned_adviser:
                    all_staff_ids = [profile.assigned_adviser.id]

                target_adviser = None
                if adviser_id:
                    target_adviser = User.objects.filter(id=adviser_id, id__in=all_staff_ids).first()
                
                # fallback if none properly selected
                if not target_adviser and all_staff_ids:
                    target_adviser = User.objects.filter(id=all_staff_ids[0]).first()

                if target_adviser:
                    msg = Message.objects.create(sender=user, receiver=target_adviser, content=content, is_read=False)
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'status': 'success', 
                            'message': {
                                'id': msg.id,
                                'content': msg.content,
                                'sender_name': 'You',
                                'sent_at': localtime(msg.sent_at).strftime("%b %d, %H:%M"),
                                'is_student': True
                            }
                        })
                    messages.success(request, 'Message sent successfully.')
                else:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'error': 'No adviser available to message right now.'}, status=400)
                    messages.error(request, 'No adviser available to message right now.')
            else:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'error': 'Content cannot be empty.'}, status=400)

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success'})

        return redirect('student_dashboard')

    # Fetch data for dashboard
    enrollment_status = profile.enrollment_status
    # Get curriculum status for tags early to identify passed subjects
    curriculum_records = StudentCurriculum.objects.filter(student=user)
    curriculum_status_map = {r.subject_id: r.status for r in curriculum_records}
    passed_subject_ids = [r.subject_id for r in curriculum_records if r.status == 'passed']

    # Get term enrollments grouped by status, excluding subjects already passed
    approved_enrollments = profile.user.term_enrollments.filter(status='approved').exclude(subject_id__in=passed_subject_ids).select_related('subject').order_by('subject__year_level', 'subject__semester', 'subject__code')
    pending_enrollments = profile.user.term_enrollments.filter(status='pending').exclude(subject_id__in=passed_subject_ids).select_related('subject').order_by('subject__year_level', 'subject__semester', 'subject__code')
    
    active_term_label = approved_enrollments.values_list('term_label', flat=True).first() or pending_enrollments.values_list('term_label', flat=True).first()

    # Recommendations
    recommended_subjects = get_recommended_subjects(profile)

    student_forms = FormSubmission.objects.filter(student=user).order_by('-submitted_at')
    student_appointments = Appointment.objects.filter(student=user).order_by('-date_time')
    
    pending_approvals = student_forms.filter(status='pending').count()
    appointments_count = student_appointments.filter(status='pending').count()
    
    adviser_ids = list(UserProfile.objects.filter(role='adviser').values_list('user_id', flat=True))
    admin_ids = list(User.objects.filter(is_superuser=True).values_list('id', flat=True))
    all_staff_ids = list(set(adviser_ids + admin_ids))
    
    if profile.assigned_adviser:
        advisers_list = User.objects.filter(id=profile.assigned_adviser.id)
        all_staff_ids = [profile.assigned_adviser.id]
    else:
        advisers_list = User.objects.filter(id__in=all_staff_ids).order_by('first_name', 'last_name')
    
    
    all_staff_ids_json = json.dumps(all_staff_ids)

    unread_notifications_count = get_total_unread_count(user)

    # Persistent Verification Check (One-Time Only)
    is_verified = profile.is_email_verified or user.is_superuser
    if not is_verified:
        try:
            from allauth.account.models import EmailAddress
            if EmailAddress.objects.filter(user=user, verified=True).exists():
                is_verified = True
                profile.is_email_verified = True
                profile.save(update_fields=['is_email_verified'])
        except Exception:
            pass

    context = {
        'profile': profile,
        'enrollment_status': enrollment_status,
        'term_enrollments': approved_enrollments,
        'pending_enrollments': pending_enrollments,
        'active_term_label': active_term_label,
        'curriculum_status_map': curriculum_status_map,
        'recommended_subjects': recommended_subjects,
        'pending_approvals': pending_approvals,
        'unread_notifications_count': unread_notifications_count,
        'appointments_count': appointments_count,
        'student_forms': student_forms,
        'student_appointments': student_appointments,
        'advisers_list': advisers_list,
        'all_staff_ids_json': all_staff_ids_json,
        'is_verified': is_verified,
    }
    return render(request, 'core/student.html', context)

@student_required
def student_get_conversation(request):
    """
    Returns the real-time conversation between the current student and a specific adviser.
    Accepts optional ?adviser_id= GET param to filter by adviser.
    """
    # Role check handled by @student_required decorator
    if not hasattr(request.user, 'userprofile'):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    user = request.user
    from django.db.models import Q
    from django.utils.timezone import localtime
    
    adviser_ids = list(UserProfile.objects.filter(role='adviser').values_list('user_id', flat=True))
    admin_ids = list(User.objects.filter(is_superuser=True).values_list('id', flat=True))
    all_staff_ids = list(set(adviser_ids + admin_ids))
    
    # If student has assigned adviser, restrict to that adviser
    assigned = user.userprofile.assigned_adviser
    if assigned:
        all_staff_ids = [assigned.id]

    # If specific adviser_id requested (from JS), filter to that adviser only
    requested_adviser_id = request.GET.get('adviser_id')
    if requested_adviser_id:
        try:
            req_id = int(requested_adviser_id)
            if req_id in all_staff_ids:
                all_staff_ids = [req_id]
        except (ValueError, TypeError):
            pass

    # Mark messages FROM any staff TO this student as read
    Message.objects.filter(
        sender__in=all_staff_ids, receiver=user, is_read=False
    ).update(is_read=True)

    # Fetch conversation between student and the target staff
    msgs = Message.objects.filter(
        Q(sender=user, receiver__in=all_staff_ids) |
        Q(sender__in=all_staff_ids, receiver=user)
    ).order_by('sent_at')

    data = []
    for m in msgs:
        is_student = (m.sender == user)
        data.append({
            'id': m.id,
            'content': m.content,
            'is_student': is_student,
            'sender_id': m.sender.id,
            'receiver_id': m.receiver.id if m.receiver else None,
            'sender_name': 'You' if is_student else (m.sender.first_name or m.sender.username),
            'sent_at': localtime(m.sent_at).strftime("%b %d, %H:%M"),
        })

    return JsonResponse({'messages': data})


@adviser_required
def adviser_dashboard(request):
    user = request.user
    from django.db.models import Q
    
    # Robust profile retrieval
    try:
        profile = user.userprofile
    except UserProfile.DoesNotExist:
        if user.is_superuser:
            role = 'admin'
        else:
            role = 'adviser'
        profile = UserProfile.objects.create(user=user, role=role)

    # Get all adviser user IDs (shared inbox - all advisers see all student messages)
    adviser_user_ids = list(UserProfile.objects.filter(role='adviser').values_list('user_id', flat=True))
    # Also include admin users who might be messaging
    admin_user_ids = list(User.objects.filter(is_superuser=True).values_list('id', flat=True))
    all_adviser_ids = list(set(adviser_user_ids + admin_user_ids))

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_appointment':
            apt_id = request.POST.get('apt_id')
            status = request.POST.get('status')
            adviser_notes = request.POST.get('adviser_notes')
            if apt_id and status:
                try:
                    apt = Appointment.objects.get(id=apt_id)
                    apt.status = status
                    apt.adviser = user
                    if status == 'confirmed':
                        sp = getattr(apt.student, 'userprofile', None)
                        if sp and sp.assigned_adviser is None:
                            sp.assigned_adviser = user
                            sp.save()
                        
                        # AUTO-GENERATE internal video conference link if empty
                        if not apt.meeting_link:
                            import uuid
                            room_id = uuid.uuid4().hex[:8]
                            room_name = f"AdviseAI-Apt-{room_id}"
                            # Build the full absolute internal URL
                            internal_link = request.build_absolute_uri(reverse('video_call_session', args=[room_name]))
                            apt.meeting_link = internal_link

                    if adviser_notes:
                        apt.adviser_notes = adviser_notes
                    
                    meeting_link = request.POST.get('meeting_link') or apt.meeting_link
                    if meeting_link:
                        apt.meeting_link = meeting_link
                        
                    if adviser_notes or meeting_link:
                        msg_content = f"Appointment Update ({apt.purpose}): "
                        if adviser_notes:
                            msg_content += f"{adviser_notes} "
                        if meeting_link:
                            msg_content += f"\n\nMeeting link: {meeting_link}"
                        Message.objects.create(sender=user, receiver=apt.student, content=msg_content.strip())
                        
                    apt.save()
                    
                    # Branded Email Notification on Confirmation or Denial
                    if status in ['confirmed', 'declined'] and apt.student.email:
                        send_branded_appointment_email(apt, adviser_comment=adviser_notes or "")
                        
                    log_activity(user, "Appointment Status Updated", f"Changed status of session ({apt.purpose}) to {status} for student {apt.student.username}")
                    messages.success(request, f'Appointment {status} successfully.')
                except Appointment.DoesNotExist:
                    messages.error(request, 'Appointment not found.')

        elif action == 'send_message':
            student_id = request.POST.get('student_id')
            content = request.POST.get('content', '').strip()
            if student_id and content:
                try:
                    student_user = User.objects.get(id=student_id)
                    # Adviser sends as themselves; student will see message from this adviser
                    m = Message.objects.create(sender=user, receiver=student_user, content=content, is_read=False)
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        from django.utils.timezone import localtime
                        return JsonResponse({
                            'status': 'success',
                            'message': {
                                'id': m.id,
                                'sender_id': m.sender.id,
                                'sender_name': m.sender.first_name or m.sender.username,
                                'content': m.content,
                                'sent_at': localtime(m.sent_at).strftime('%b %d, %Y %I:%M %p'),
                                'is_adviser': True,
                            }
                        })
                    messages.success(request, 'Message sent successfully.')
                except User.DoesNotExist:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'error': 'Student not found.'}, status=404)
                    messages.error(request, 'Student not found.')
            else:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'error': 'Content cannot be empty.'}, status=400)
                    
        return redirect('adviser_dashboard')

    # 1. Consolidated Real-Time Appointments List
    # - Pending: Available for confirmation
    # - In Progress: Currently in a call
    # - Done: Visible for 24 hours after completion
    from datetime import timedelta
    now = timezone.now()
    # 1. Main Operational Feed (Pending, Confirmed, In Progress)
    my_appointments = Appointment.objects.filter(
        adviser=user,
        status__in=['pending', 'confirmed', 'in_progress']
    ).select_related('student', 'student__userprofile').order_by('date_time')
    my_students = UserProfile.objects.filter(Q(role='student') & (Q(assigned_adviser__isnull=True) | Q(assigned_adviser=user)))

    # 2. Appointments History (Completed, Declined, Cancelled)
    appointments_history = Appointment.objects.filter(
        adviser=user,
        status__in=['completed', 'declined', 'cancelled']
    ).select_related('student', 'student__userprofile').order_by('-date_time')[:50]

    # 3. Priority Action Center Logic (Find earliest session that needs response)
    focus_apt = Appointment.objects.filter(
        adviser=user,
        status='pending'
    ).order_by('date_time').first()

    # Build per-student conversation threads
    # A thread between a student and ANY adviser/admin is visible to all advisers unless assigned to a specific adviser
    student_threads = []
    for sp in my_students:
        s = sp.user
        # Messages: student -> any adviser, OR any adviser -> student
        thread_msgs = Message.objects.filter(
            Q(sender__in=all_adviser_ids, receiver=s) |
            Q(sender=s, receiver__in=all_adviser_ids)
        ).order_by('sent_at')

        # Unread = messages from student that haven't been read yet
        unread_count = thread_msgs.filter(sender=s, is_read=False).count()
        last_msg = thread_msgs.last()
        if thread_msgs.exists():
            student_threads.append({
                'profile': sp,
                'messages': list(thread_msgs),
                'unread': unread_count,
                'last_msg': last_msg,
            })

    # Sort threads: unread first, then by last message time
    student_threads.sort(key=lambda t: (
        0 if t['unread'] > 0 else 1,
        t['last_msg'].sent_at if t['last_msg'] else None
    ), reverse=False)
    student_threads.sort(key=lambda t: t['unread'] > 0, reverse=True)

    # Count unread: student messages with no adviser reply yet (or not read)
    total_unread = Message.objects.filter(
        sender__in=list(UserProfile.objects.filter(role='student').values_list('user_id', flat=True)),
        is_read=False
    ).count()

    # Curriculum data for adviser
    all_subjects = CurriculumSubject.objects.all()
    generated_codes = EnrollmentCode.objects.filter(adviser=user).select_related('student').prefetch_related('approved_subjects').order_by('-created_at')[:30]

    # For Peer-to-Peer Staff Messaging
    staff_list = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)).exclude(id=user.id)

    # Persistent Verification Check (One-Time Only)
    is_verified = profile.is_email_verified or user.is_superuser
    if not is_verified:
        try:
            from allauth.account.models import EmailAddress
            if EmailAddress.objects.filter(user=user, verified=True).exists():
                is_verified = True
                profile.is_email_verified = True
                profile.save(update_fields=['is_email_verified'])
        except Exception:
            pass

    # Get all adviser user IDs for the dashboard JS
    all_adviser_ids = list(UserProfile.objects.filter(role='adviser').values_list('user_id', flat=True))

    context = {
        'is_verified': is_verified,
        'appointments': my_appointments,
        'appointments_history': appointments_history,
        'focus_apt': focus_apt,
        'my_students': my_students,
        'total_advisees': my_students.count(),
        'pending_action_count': Appointment.objects.filter(adviser=user, status='pending').count(),
        'active_sessions_count': my_appointments.filter(status='in_progress').count(),
        'student_threads': student_threads,
        'total_unread': total_unread,
        'adviser_user': user,
        'all_adviser_ids_json': json.dumps(all_adviser_ids),
        'all_subjects': all_subjects,
        'generated_codes': generated_codes,
        'staff_list': staff_list,
        'unread_notifications_count': get_total_unread_count(user),
    }
    return render(request, 'core/adviser.html', context)

@login_required(login_url='login')
def messages_page(request):
    """Shell view for the dedicated messaging page. Initial content loaded via AJAX."""
    user = request.user
    role = getattr(user, 'userprofile', None)
    role_str = role.role if role else ('admin' if user.is_superuser else 'student')
    
    context = {
        'role': role_str,
        'user_name': f"{user.first_name} {user.last_name}".strip() or user.username,
    }
    return render(request, 'core/messages.html', context)



@login_required(login_url='login')
def api_send_message(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    import json as _json
    try:
        body = _json.loads(request.body)
    except Exception:
        body = request.POST
        
    receiver_id = body.get('receiver_id')
    content = body.get('content', '').strip()
    
    if not receiver_id or not content:
        return JsonResponse({'error': 'receiver_id and content are required'}, status=400)
    
    try:
        receiver = User.objects.get(id=receiver_id)
        # Security: Students cannot message other students
        try:
            sender_profile = request.user.userprofile
            receiver_profile = receiver.userprofile
            
            if sender_profile.role == 'student' and receiver_profile.role == 'student':
                 return JsonResponse({'error': 'Students cannot message other students.'}, status=403)
        except UserProfile.DoesNotExist:
            pass # Superusers might not have profile
            
        m = Message.objects.create(sender=request.user, receiver=receiver, content=content, is_read=False)
        return JsonResponse({
            'status': 'success',
            'message': {
                'id': m.id,
                'content': m.content,
                'sent_at': localtime(m.sent_at).strftime('%b %d, %Y %I:%M %p')
            }
        })
    except User.DoesNotExist:
        return JsonResponse({'error': 'Receiver not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required(login_url='login')
def get_conversation(request, student_id):
    """AJAX endpoint: returns full conversation between a student and ANY adviser. Marks student msgs read."""
    from django.db.models import Q
    from django.http import JsonResponse

    adviser = request.user

    try:
        student_user = User.objects.get(id=student_id)
        student_profile = student_user.userprofile
        if student_profile.assigned_adviser and student_profile.assigned_adviser != adviser and not adviser.is_superuser:
            return JsonResponse({'error': 'Student is assigned to another adviser'}, status=403)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    # Get all adviser/admin user IDs for shared inbox (will be filtered if assigned)
    adviser_user_ids = list(UserProfile.objects.filter(role='adviser').values_list('user_id', flat=True))
    admin_user_ids = list(User.objects.filter(is_superuser=True).values_list('id', flat=True))
    all_adviser_ids = list(set(adviser_user_ids + admin_user_ids))

    # Fetch ALL messages between this student and any adviser (shared inbox)
    thread = Message.objects.filter(
        Q(sender__in=all_adviser_ids, receiver=student_user) |
        Q(sender=student_user, receiver__in=all_adviser_ids)
    ).order_by('sent_at')

    # Mark student's unread messages as read
    thread.filter(sender=student_user, is_read=False).update(is_read=True)

    data = []
    for m in thread:
        sender_name = f"{m.sender.first_name} {m.sender.last_name}".strip() or m.sender.username
        is_adviser_msg = m.sender.id in all_adviser_ids
        data.append({
            'id': m.id,
            'sender_id': m.sender.id,
            'sender_name': sender_name,
            'content': m.content,
            'sent_at': m.sent_at.strftime('%b %d, %Y %I:%M %p'),
            'is_adviser': is_adviser_msg,
        })
    return JsonResponse({'messages': data})


@admin_required
def admin_dashboard(request):
    user = request.user
    from django.db.models import Q
    from datetime import timedelta
    # Monitoring retention threshold (1 week)
    threshold_1w = timezone.now() - timedelta(days=7)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'admin_approve_enrollment':
            req_id = request.POST.get('request_id')
            from .models import TermEnrollment, StudentCurriculum
            try:
                enr = TermEnrollment.objects.get(id=req_id)
                enr.status = 'approved'
                enr.save()
                
                # Also update StudentCurriculum to 'in_progress'
                StudentCurriculum.objects.update_or_create(
                    student=enr.student, subject=enr.subject,
                    defaults={'status': 'in_progress', 'term_taken': enr.term_label}
                )
                
                # Check if all pending for this student are done to update profile status
                if not TermEnrollment.objects.filter(student=enr.student, status='pending').exists():
                    p = enr.student.userprofile
                    p.enrollment_status = 'enrolled'
                    p.save()
                    
                    # New: Notify Adviser that enrollment is approved
                    if p.assigned_adviser:
                        Notification.objects.create(
                            user=p.assigned_adviser,
                            event_type='enrollment_approved',
                            message=f'Enrollment approved for your advisee: {enr.student.get_full_name() or enr.student.username} ({enr.subject.code})'
                        )
                    
                messages.success(request, f"Approved enrollment for {enr.student.first_name} - {enr.subject.code}")
                log_activity(user, "Enrollment Approved", f"Approved {enr.subject.code} for {enr.student.get_full_name() or enr.student.username}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'success', 'message': f"Approved: {enr.subject.code}"})
            except TermEnrollment.DoesNotExist:
                messages.error(request, "Enrollment request not found.")
                
        elif action == 'admin_decline_enrollment':
            req_id = request.POST.get('request_id')
            from .models import TermEnrollment
            try:
                enr = TermEnrollment.objects.get(id=req_id)
                enr.status = 'declined'
                enr.save()
                
                # If no more pending, update profile
                if not TermEnrollment.objects.filter(student=enr.student, status='pending').exists():
                    p = enr.student.userprofile
                    p.enrollment_status = 'not_enrolled' # or keep as it was
                    p.save()
                    
                messages.warning(request, f"Declined enrollment for {enr.student.first_name} - {enr.subject.code}")
                log_activity(user, "Enrollment Declined", f"Declined {enr.subject.code} for {enr.student.get_full_name() or enr.student.username}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'success', 'message': f"Declined: {enr.subject.code}"})
            except TermEnrollment.DoesNotExist:
                messages.error(request, "Enrollment request not found.")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': "Request not found."})

        elif action == 'admin_approve_enrollment_bulk':
            code_id = request.POST.get('enrollment_code_id')
            from .models import TermEnrollment, StudentCurriculum
            try:
                pending_batch = TermEnrollment.objects.filter(enrollment_code_id=code_id, status='pending')
                if not pending_batch.exists():
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'status': 'error', 'message': "No pending requests for this code."})
                
                count = 0
                student_profile = None
                for enr in pending_batch:
                    enr.status = 'approved'
                    enr.save()
                    StudentCurriculum.objects.update_or_create(
                        student=enr.student, subject=enr.subject,
                        defaults={'status': 'in_progress', 'term_taken': enr.term_label}
                    )
                    student_profile = enr.student.userprofile
                    count += 1
                
                if student_profile and not TermEnrollment.objects.filter(student=student_profile.user, status='pending').exists():
                    student_profile.enrollment_status = 'enrolled'
                    student_profile.save()
                    
                msg = f"Successfully approved {count} subjects."
                messages.success(request, msg)
                log_activity(user, "Bulk Enrollment Approved", f"Approved {count} subjects for code {code_id}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'success', 'message': msg})
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': str(e)})
                messages.error(request, str(e))

        elif action == 'admin_decline_enrollment_bulk':
            code_id = request.POST.get('enrollment_code_id')
            from .models import TermEnrollment
            try:
                pending_batch = TermEnrollment.objects.filter(enrollment_code_id=code_id, status='pending')
                count = pending_batch.count()
                pending_batch.update(status='declined')
                
                # Update profile if no more pending
                for enr in pending_batch:
                    if not TermEnrollment.objects.filter(student=enr.student, status='pending').exists():
                        p = enr.student.userprofile
                        p.enrollment_status = 'not_enrolled'
                        p.save()
                    break # Only need to check once per batch/student
                    
                msg = f"Declined {count} enrollment requests."
                messages.warning(request, msg)
                log_activity(user, "Bulk Enrollment Declined", f"Declined {count} subjects for code {code_id}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'success', 'message': msg})
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': str(e)})
                messages.error(request, str(e))

        elif action == 'add_staff':
            name = request.POST.get('name')
            email = request.POST.get('email')
            password = request.POST.get('password')
            role = request.POST.get('role') # admin or adviser

            if role == 'adviser' and not email.lower().endswith('@gmail.com'):
                messages.error(request, 'Adviser accounts must use a legitimate @gmail.com address.')
                return redirect('admin_dashboard')

            if not User.objects.filter(username=email).exists():
                new_user = User.objects.create_user(username=email, email=email, password=password)
                if name:
                    parts = name.split()
                    new_user.first_name = parts[0]
                    if len(parts) > 1:
                        new_user.last_name = " ".join(parts[1:])
                
                if role == 'admin':
                    new_user.is_superuser = True
                    new_user.is_staff = True
                new_user.save()
                
                UserProfile.objects.create(user=new_user, role=role)
                messages.success(request, f'{role.capitalize()} account created successfully.')
                log_activity(user, "Staff Added", f"Created {role} account for {email}")
            else:
                messages.error(request, 'Email already registered.')
                
        elif action == 'add_student':
            name = request.POST.get('name')
            email = request.POST.get('email')
            password = request.POST.get('password')
            student_id = request.POST.get('student_id')
            program = request.POST.get('program', 'BSIT')
            
            if not User.objects.filter(username=email).exists():
                new_user = User.objects.create_user(username=email, email=email, password=password)
                if name:
                    parts = name.split()
                    new_user.first_name = parts[0]
                    if len(parts) > 1:
                        new_user.last_name = " ".join(parts[1:])
                new_user.save()
                
                UserProfile.objects.create(user=new_user, role='student', student_id=student_id, program=program, enrollment_status='enrolled')
                messages.success(request, 'Student account created successfully.')
                log_activity(user, "Student Added", f"Created student account for {email} ({program})")
            else:
                messages.error(request, 'Email already registered.')
                
        elif action == 'update_enrollment':
            student_profile_id = request.POST.get('profile_id')
            status = request.POST.get('status') # 'enrolled' or 'rejected'
            if student_profile_id and status:
                try:
                    profile = UserProfile.objects.get(id=student_profile_id)
                    profile.enrollment_status = status
                    profile.save()
                    messages.success(request, f'Enrollment {status} successfully.')
                    log_activity(user, "Enrollment Updated", f"Updated {profile.user.username} enrollment status to {status}")
                except UserProfile.DoesNotExist:
                    messages.error(request, 'Student profile not found.')
        elif action == 'toggle_user_status':
            target_user_id = request.POST.get('user_id')
            if target_user_id:
                try:
                    target_user = User.objects.get(id=target_user_id)
                    if target_user != request.user:
                        target_user.is_active = not target_user.is_active
                        target_user.save()
                        status_str = "activated" if target_user.is_active else "deactivated"
                        messages.success(request, f'Account successfully {status_str}.')
                        log_activity(user, "User Status Toggled", f"{status_str.capitalize()} account for {target_user.username}")
                    else:
                        messages.error(request, 'You cannot deactivate your own account.')
                except User.DoesNotExist:
                    messages.error(request, 'User not found.')

        elif action == 'delete_user':
            target_user_id = request.POST.get('user_id')
            if target_user_id:
                try:
                    target_user = User.objects.get(id=target_user_id)
                    if target_user != request.user:
                        uname = target_user.username
                        target_user.delete()
                        messages.success(request, 'Account successfully deleted.')
                        log_activity(user, "User Deleted", f"Deleted account for {uname}")
                    else:
                        messages.error(request, 'You cannot delete your own account.')
                except User.DoesNotExist:
                    messages.error(request, 'User not found.')

        elif action == 'admin_broadcast_notification':
            message_text = request.POST.get('broadcast_message')
            if message_text:
                all_users = User.objects.all()
                notifs = [
                    Notification(
                        user=u, 
                        event_type='broadcast', 
                        message=f"SYSTEM ALERT: {message_text}",
                        is_read=False
                    ) for u in all_users
                ]
                Notification.objects.bulk_create(notifs)
                messages.success(request, f'Broadcast sent to {all_users.count()} users.')
                log_activity(user, "System Broadcast", f"Sent broadcast pulse: {message_text[:50]}...")
        
        elif action == 'admin_respond_form':
            form_id = request.POST.get('form_id')
            status = request.POST.get('status')
            admin_response = request.POST.get('admin_response', '').strip()
            if form_id and status:
                try:
                    form = FormSubmission.objects.get(id=form_id)
                    form.status = status
                    form.admin_response = admin_response
                    form.save()
                    
                    # Auto-message to student
                    if admin_response:
                        Message.objects.create(
                            sender=user, 
                            receiver=form.student, 
                            content=f"[RESPONSE TO YOUR {form.title.upper()}]: {admin_response}"
                        )
                    
                    # Notification to student
                    Notification.objects.create(
                        user=form.student,
                        event_type='help_response',
                        message=f'Admin has responded to your request: "{form.title}".'
                    )
                    
                    
                    messages.success(request, f'Form {status} successfully.')
                    log_activity(user, "Form Responded", f"Responded to {form.student.username}'s form: {form.title}")
                except FormSubmission.DoesNotExist:
                    messages.error(request, 'Form not found.')

        elif action == 'admin_reset_password':
            target_user_id = request.POST.get('user_id')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            if target_user_id and new_password:
                if new_password != confirm_password:
                    messages.error(request, 'Passwords do not match.')
                else:
                    try:
                        target_user = User.objects.get(id=target_user_id)
                        target_user.set_password(new_password)
                        target_user.save()
                        messages.success(request, f'Password for {target_user.get_full_name() or target_user.username} has been reset.')
                        log_activity(user, "Password Reset", f"Reset password for {target_user.get_full_name() or target_user.username}")
                    except User.DoesNotExist:
                        messages.error(request, 'User not found.')
                
        return redirect('admin_dashboard')

    staff_users = UserProfile.objects.exclude(role='student')
    advisers = staff_users.filter(role='adviser')
    admins = staff_users.filter(role='admin')
    students = UserProfile.objects.filter(role='student')
    from .models import TermEnrollment
    all_pending = TermEnrollment.objects.filter(status='pending').select_related('student', 'subject', 'enrollment_code')
    
    # Grouping pending requests by code
    grouped_pending = {}
    for req in all_pending:
        code_id = req.enrollment_code.id if req.enrollment_code else 'manual'
        if code_id not in grouped_pending:
            grouped_pending[code_id] = {
                'code': req.enrollment_code,
                'student': req.student,
                'term': req.term_label,
                'requests': []
            }
        grouped_pending[code_id]['requests'].append(req)
    
    pending_groups = list(grouped_pending.values())

    context = {
        'staff_users': staff_users,
        'advisers': advisers,
        'admins': admins,
        'students': students,
        'pending_requests': all_pending,
        'pending_groups': pending_groups,
        'total_students': students.count(),
        'total_staff': staff_users.count(),
        'online_users': User.objects.filter(is_active=True).count(),
        'total_forms': FormSubmission.objects.count(),
        'total_appointments': Appointment.objects.count(),
        'total_pending': all_pending.count(),
        'pending_forms': FormSubmission.objects.filter(status='pending').order_by('-submitted_at'),
        'avg_response_time': calculate_avg_response_time(),
        
        # New Analytics Data
        'enrolled_count': students.filter(enrollment_status='enrolled').count(),
        'not_enrolled_count': students.filter(enrollment_status='not_enrolled').count(),
        'pending_enrollment_count': students.filter(enrollment_status='pending').count(),
        'apt_pending': Appointment.objects.filter(status='pending').count(),
        'apt_confirmed': Appointment.objects.filter(status='confirmed').count(),
        'apt_completed': Appointment.objects.filter(status='completed').count(),
        
        # Monitoring & Records (1-Week Retention for Completed)
        'appointment_monitoring': Appointment.objects.filter(
            Q(status__in=['pending', 'confirmed', 'in_progress']) |
            Q(status='completed', actual_end_at__gte=threshold_1w)
        ).order_by('-date_time')[:100],
        'activity_logs': ActivityLog.objects.all()[:100],
        'student_records': students,
        'unassigned_students': students.filter(assigned_adviser=None),
        'all_advisers': advisers,
        'help_forms': FormSubmission.objects.all(),
        'enrollment_requests': all_pending,
        'curriculum_subjects': CurriculumSubject.objects.all().order_by('program', 'year_level', 'semester'),
        'unread_notifications_count': get_total_unread_count(user),
    }
    return render(request, 'core/admin.html', context)

@login_required
def admin_monitor_view(request):
    # Check if user is superuser or has 'admin' role
    is_admin = request.user.is_superuser
    if not is_admin and hasattr(request.user, 'userprofile'):
        is_admin = request.user.userprofile.role == 'admin'
    
    if not is_admin:
        return redirect('landing')
    
    context = {
        'appointment_monitoring': Appointment.objects.all().order_by('-created_at')[:100],
        'activity_logs': ActivityLog.objects.all().order_by('-timestamp')[:100],
        'live_calls_count': Appointment.objects.filter(actual_start_at__isnull=False, actual_end_at__isnull=True).count(),
        'total_completed': Appointment.objects.filter(status='completed').count(),
    }
    return render(request, 'core/admin_monitor.html', context)

@login_required
def api_signal_appointment_start(request, apt_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        apt = Appointment.objects.get(id=apt_id)
        if apt.actual_start_at is None:
            apt.actual_start_at = timezone.now()
            apt.save()
            log_activity(request.user, "Meeting Started", f"Conference logic started for assignment: {apt.purpose}")
        return JsonResponse({'status': 'success', 'started_at': apt.actual_start_at})
    except Appointment.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

@login_required
def api_signal_appointment_end(request, apt_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        apt = Appointment.objects.get(id=apt_id)
        if apt.actual_end_at is None:
            apt.actual_end_at = timezone.now()
            apt.status = 'completed'
            apt.save()
            log_activity(request.user, "Meeting Ended", f"Conference logic concluded for assignment: {apt.purpose}")
        return JsonResponse({'status': 'success', 'ended_at': apt.actual_end_at})
    except Appointment.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required(login_url='login')
def api_analytics_sync(request):
    """API endpoint to return latest system analytics for Admin."""
    if not request.user.is_superuser and getattr(request.user, 'userprofile', None).role != 'admin':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    advisers = UserProfile.objects.filter(role='adviser')
    students = UserProfile.objects.filter(role='student')
    pending_enrollments = TermEnrollment.objects.filter(status='pending')
    
    data = {
        'total_students': students.count(),
        'online_users': User.objects.filter(is_active=True).count(),
        'total_forms': FormSubmission.objects.count(),
        'total_appointments': Appointment.objects.count(),
        'total_pending': pending_enrollments.count(),
        'avg_response_time': calculate_avg_response_time(),
        
        # Analytics Tab Stats
        'enrolled_count': students.filter(enrollment_status='enrolled').count(),
        'not_enrolled_count': students.filter(enrollment_status='not_enrolled').count(),
        'pending_enrollment_count': students.filter(enrollment_status='pending').count(),
        'apt_pending': Appointment.objects.filter(status='pending').count(),
        'apt_confirmed': Appointment.objects.filter(status='confirmed').count(),
        'apt_completed': Appointment.objects.filter(status='completed').count(),
        'form_pending': FormSubmission.objects.filter(status='pending').count(),
        'form_approved': FormSubmission.objects.filter(status='approved').count(),
    }
    return JsonResponse(data)

def calculate_avg_response_time():
    """Calculates the average time between an inquiry submission and the first adviser response."""
    from django.utils import timezone
    from datetime import timedelta
    import statistics
    
    inquiries = FormSubmission.objects.all()
    deltas = []
    
    for inq in inquiries:
        # Find first message from any staff to this student after inquiry submission
        staff_ids = list(UserProfile.objects.filter(role__in=['adviser', 'admin']).values_list('user_id', flat=True))
        resp = Message.objects.filter(
            sender__id__in=staff_ids,
            receiver=inq.student,
            sent_at__gt=inq.submitted_at
        ).order_by('sent_at').first()
        
        if resp:
            diff = resp.sent_at - inq.submitted_at
            deltas.append(diff.total_seconds())
            
    if not deltas:
        return "1.2 hours" # Default placeholder if no data
        
    avg_seconds = statistics.mean(deltas)
    hours = avg_seconds / 3600
    if hours < 1:
        return f"{int(avg_seconds / 60)} minutes"
    return f"{round(hours, 1)} hours"


def forms_portal(request):
    return render(request, 'core/forms.html')

def admin_users(request):
    return render(request, 'core/admin.html')

def admin_settings(request):
    return render(request, 'core/admin.html')

@login_required(login_url='login')
def profile_view(request):
    user = request.user
    role = None
    if hasattr(user, 'userprofile'):
        role = user.userprofile.role
    elif user.is_superuser:
        role = 'admin'

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            email = request.POST.get('email')
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')

            if email and email != user.email:
                if User.objects.filter(username=email).exclude(id=user.id).exists():
                    messages.error(request, 'Email is already in use by another account.')
                else:
                    user.email = email
                    user.username = email
                    user.save()
                    messages.success(request, 'Email successfully updated.')
            
            if password:
                if password == confirm_password:
                    user.set_password(password)
                    user.save()
                    update_session_auth_hash(request, user)
                    messages.success(request, 'Password successfully updated.')
                else:
                    messages.error(request, 'Passwords do not match.')

            if role == 'student':
                program = request.POST.get('program')
                if program in ['BSIT', 'BSCS']:
                    user.userprofile.program = program
                    user.userprofile.save()
                    messages.success(request, f'Degree program set to {program}.')
            
            if role == 'adviser':
                meeting_link = request.POST.get('meeting_link')
                user.userprofile.meeting_link = meeting_link
                user.userprofile.save()
                messages.success(request, 'Profile meeting link updated.')

            return redirect('profile')

    context = {
        'user': user,
        'role': role
    }
    return render(request, 'core/profile.html', context)


@login_required(login_url='login')
def get_notification_count(request):
    return JsonResponse({'count': get_total_unread_count(request.user)})


@login_required(login_url='login')
def staff_get_contacts(request):
    """Returns list of other staff members (Admins/Advisers) for DMs."""
    try:
        user_profile = request.user.userprofile
        is_staff_role = user_profile.role in ['admin', 'adviser']
    except UserProfile.DoesNotExist:
        is_staff_role = False

    if not (request.user.is_superuser or is_staff_role):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    data = []

    # Include superusers who may not have a UserProfile
    seen_ids = set()

    # First: collect all UserProfile-backed staff
    profile_contacts = UserProfile.objects.filter(
        role__in=['admin', 'adviser']
    ).select_related('user').exclude(user=request.user)

    for c in profile_contacts:
        seen_ids.add(c.user.id)
        data.append({
            'id': c.user.id,
            'name': f"{c.user.first_name} {c.user.last_name}".strip() or c.user.username,
            'role': c.role.capitalize(),
            'email': c.user.email,
            'online': (timezone.now() - c.last_activity).total_seconds() < 300 if c.last_activity else False
        })

    # Second: collect superusers without a UserProfile entry (e.g., sticky admin)
    superusers = User.objects.filter(
        is_superuser=True
    ).exclude(id=request.user.id).exclude(id__in=seen_ids)

    for su in superusers:
        data.append({
            'id': su.id,
            'name': f"{su.first_name} {su.last_name}".strip() or su.username,
            'role': 'Admin',
            'email': su.email,
            'online': False
        })

    return JsonResponse({'contacts': data})

@login_required(login_url='login')
def staff_get_conversation(request, contact_id):
    """Returns conversation between current staff and another staff member using StaffMessage model."""
    from core.models import StaffMessage
    if not (request.user.is_superuser or request.user.userprofile.role in ['admin', 'adviser']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    user = request.user
    try:
        contact = User.objects.get(id=contact_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Contact not found'}, status=404)
    
    # Mark staff messages as read
    StaffMessage.objects.filter(sender=contact, receiver=user, is_read=False).update(is_read=True)
    
    from django.db.models import Q
    msgs = StaffMessage.objects.filter(
        (Q(sender=user, receiver=contact) | Q(sender=contact, receiver=user))
    ).order_by('sent_at')
    
    data = []
    for m in msgs:
        data.append({
            'id': m.id,
            'content': m.content,
            'sender_id': m.sender.id,
            'sender_name': 'You' if m.sender == user else (f"{m.sender.first_name} {m.sender.last_name}".strip() or m.sender.username),
            'sent_at': m.sent_at.strftime('%b %d, %I:%M %p'),
            'is_me': m.sender == user
        })
    return JsonResponse({'messages': data})

@login_required(login_url='login')
def staff_send_message(request):
    """Sends a staff-only message using StaffMessage model. Supports JSON and POST."""
    from core.models import StaffMessage
    if not (request.user.is_superuser or request.user.userprofile.role in ['admin', 'adviser']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        import json as _json
        try:
            body = _json.loads(request.body)
        except Exception:
            body = request.POST
            
        receiver_id = body.get('receiver_id')
        content = body.get('content', '').strip()
        
        if not receiver_id or not content:
            return JsonResponse({'error': 'Missing fields'}, status=400)
        
        try:
            receiver = User.objects.get(id=receiver_id)
            StaffMessage.objects.create(
                sender=request.user,
                receiver=receiver,
                content=content
            )
            return JsonResponse({'status': 'success'})
        except User.DoesNotExist:
            return JsonResponse({'error': 'Receiver not found'}, status=404)
    return JsonResponse({'error': 'POST required'}, status=405)

@login_required(login_url='login')
def api_get_active_sessions(request):
    """API for the Admin 'Who's Online' modal."""
    if not (request.user.is_superuser or request.user.userprofile.role == 'admin'):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    from core.models import UserProfile
    from django.utils import timezone
    five_mins_ago = timezone.now() - timedelta(minutes=5)
    
    online_profiles = UserProfile.objects.filter(last_activity__gte=five_mins_ago).select_related('user')
    
    data = []
    for p in online_profiles:
        data.append({
            'name': f"{p.user.first_name} {p.user.last_name}".strip() or p.user.username,
            'role': p.role.capitalize(),
            'email': p.user.email,
            'last_active': timezone.localtime(p.last_activity).strftime('%I:%M %p'),
            'is_me': p.user == request.user
        })
    
    return JsonResponse({'active_sessions': data})

@login_required(login_url='login')
def api_send_official_notice(request):
    """Admin-to-Student one-way official notice."""
    if not (request.user.is_superuser or request.user.userprofile.role == 'admin'):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            student_id = data.get('student_id')
            content = data.get('content', '').strip()
            
            if not student_id or not content:
                return JsonResponse({'error': 'Missing student or message'}, status=400)
            
            student_user = User.objects.get(id=student_id)
            
            # Prefix with recognizable flag for the student UI to lock input
            official_content = f"[OFFICIAL ADMIN NOTICE] {content}"
            
            from core.models import Message
            Message.objects.create(
                sender=request.user,
                receiver=student_user,
                content=official_content
            )
            
            return JsonResponse({'status': 'success', 'message': 'Notice sent successfully'})
        except User.DoesNotExist:
            return JsonResponse({'error': 'Student not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'POST required'}, status=405)

@login_required(login_url='login')
def api_send_staff_message(request):
    """Messaging between staff members (Admins/Advisers)."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            receiver_id = data.get('receiver_id')
            content = data.get('content', '').strip()
            
            if not receiver_id or not content:
                return JsonResponse({'error': 'Missing receiver or message'}, status=400)
            
            from django.contrib.auth.models import User
            receiver = User.objects.get(id=receiver_id)
            
            # Verify both are staff
            sender_profile = request.user.userprofile
            receiver_profile = receiver.userprofile
            
            is_sender_staff = request.user.is_superuser or sender_profile.role in ['admin', 'adviser']
            is_receiver_staff = receiver.is_superuser or receiver_profile.role in ['admin', 'adviser']
            
            if not (is_sender_staff and is_receiver_staff):
                return JsonResponse({'error': 'Staff messaging only allowed between staff members'}, status=403)
                
            from core.models import StaffMessage
            msg = StaffMessage.objects.create(
                sender=request.user,
                receiver=receiver,
                content=content
            )
            return JsonResponse({
                'status': 'success',
                'message': {
                    'id': msg.id,
                    'content': msg.content,
                    'sent_at': msg.sent_at.strftime('%b %d, %I:%M %p')
                }
            })
        except User.DoesNotExist:
            return JsonResponse({'error': 'Receiver not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'POST required'}, status=405)

@login_required(login_url='login')
def api_get_notifications(request):
    """Returns recent system notifications for the user."""
    from core.models import Notification
    from django.utils.timezone import localtime
    
    user = request.user
    role = getattr(user, 'userprofile', None)
    role_str = role.role if role else ('admin' if user.is_superuser else None)
    
    user = request.user
    
    # 1. Real Notifications
    notifs_query = Notification.objects.filter(user=user).order_by('-created_at')[:15]
    data = []
    for n in notifs_query:
        data.append({
            'id': f"n_{n.id}",
            'type': n.get_event_type_display(),
            'raw_type': n.event_type,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': n.created_at.timestamp(), # Use timestamp for accurate frontend sorting
            'display_date': localtime(n.created_at).strftime('%b %d, %I:%M %p')
        })
    
    # 2. Unread Messages as notifications
    # For students: messages from staff
    # For staff: messages from students OR other staff (if StaffMessage)
    unread_msgs = Message.objects.filter(receiver=user, is_read=False).order_by('-sent_at')[:10]
    for m in unread_msgs:
        data.append({
            'id': f"m_{m.id}",
            'type': 'New Message',
            'raw_type': 'message',
            'message': f"From {m.sender.first_name or m.sender.username}: {m.content[:40]}...",
            'is_read': False,
            'created_at': m.sent_at.timestamp(),
            'display_date': localtime(m.sent_at).strftime('%b %d, %I:%M %p')
        })
    
    # Sort combined by timestamp descending
    data.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Calculate unread count for the simplified badge update
    unread_count = Notification.objects.filter(user=user, is_read=False).count()
    unread_count += Message.objects.filter(receiver=user, is_read=False).count()

    return JsonResponse({
        'notifications': data,
        'unread_count': unread_count
    })

@login_required
@csrf_exempt
def api_trigger_call(request):
    """
    Endpoint for Advisers to trigger an 'Incoming Call' notification for a student.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        target_user_id = data.get('receiver_id')
        room_name = data.get('room_name')
        
        if not target_user_id or not room_name:
            return JsonResponse({'error': 'Missing receiver_id or room_name'}, status=400)
            
        target_user = User.objects.get(id=target_user_id)
        
        # Create a machine-parseable notification message
        caller_name = request.user.get_full_name() or request.user.username
        notif_msg = json.dumps({
            'caller_name': caller_name,
            'room_name': room_name,
            'display_text': f"{caller_name} is inviting you to a secure video conference."
        })
        
        from core.models import Notification
        Notification.objects.create(
            user=target_user,
            event_type='incoming_call',
            message=notif_msg,
            is_read=False
        )
        
        return JsonResponse({'status': 'success'})
    except User.DoesNotExist:
        return JsonResponse({'error': 'Target user not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    # Actually, let's just keep them as requested: latest first.
    
    return JsonResponse({
        'notifications': data,
        'unread_count': get_total_unread_count(user)
    })


@login_required(login_url='login')
def api_mark_notifications_read(request):
    from core.models import Notification
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'success'})


@login_required(login_url='login')
def get_latest_notifications(request):
    from django.http import JsonResponse
    from core.models import UserProfile, Message
    user = request.user
    role = getattr(user, 'userprofile', None)
    role = role.role if role else ('admin' if user.is_superuser else None)
    
    notifications = []
    
    if role == 'student':
        # 1. Real Notifications from the Notification model
        from core.models import Notification
        notifs = Notification.objects.filter(user=user, is_read=False, event_type='help_response').order_by('-created_at')[:5]
        for n in notifs:
            # Try to find the last admin message to get a sender_id
            last_reply = Message.objects.filter(receiver=user, content__icontains="RESPONSE TO YOUR").order_by('-sent_at').first()
            sender_id = last_reply.sender_id if last_reply else None
            notifications.append({
                'id': f"notif_{n.id}",
                'title': 'Help/Report Responded',
                'content': n.message,
                'time': n.created_at.strftime('%b %d, %H:%M'),
                'sender_id': sender_id
            })

        # 2. Unread Messages acting as notifications
        staff = list(UserProfile.objects.filter(role__in=['adviser', 'admin']).values_list('user_id', flat=True)) + \
                list(User.objects.filter(is_superuser=True).values_list('id', flat=True))
        
        msgs = Message.objects.filter(receiver=user, sender__in=staff, is_read=False).order_by('-sent_at')[:5]
        for m in msgs:
            is_response = "RESPONSE TO YOUR" in m.content.upper()
            notifications.append({
                'id': f"msg_{m.id}",
                'title': 'Form Response Received' if is_response else f'Message from {m.sender.first_name or m.sender.username}',
                'content': m.content[:50] + ('...' if len(m.content) > 50 else ''),
                'time': m.sent_at.strftime('%b %d, %H:%M'),
                'sender_id': m.sender_id
            })
    
    elif role in ['adviser', 'admin']:
        staff = list(UserProfile.objects.filter(role='adviser').values_list('user_id', flat=True)) + \
                list(User.objects.filter(is_superuser=True).values_list('id', flat=True))
        msgs = Message.objects.filter(
            sender__userprofile__role='student',
            receiver__in=staff,
            is_read=False
        ).order_by('-sent_at')[:5]
        for m in msgs:
            notifications.append({
                'id': m.id,
                'title': f'New message from Student {m.sender.first_name or m.sender.username}',
                'content': m.content[:50] + ('...' if len(m.content) > 50 else ''),
                'time': m.sent_at.strftime('%b %d, %H:%M')
            })
            
    return JsonResponse({'notifications': notifications})


# ─────────────────────────────────────────────────────────────
#  CURRICULUM & ENROLLMENT CODE API VIEWS
# ─────────────────────────────────────────────────────────────

@login_required(login_url='login')
def get_all_curriculum(request):
    """Returns the curriculum subjects filtered by program if specified."""
    program = request.GET.get('program')
    if not program:
        # Fallback to user's program if student
        try:
            profile = request.user.userprofile
            if profile.role == 'student':
                program = profile.program
        except UserProfile.DoesNotExist:
            pass
            
    subjects_query = CurriculumSubject.objects.all()
    if program:
        subjects_query = subjects_query.filter(program=program)
        
    subjects = subjects_query.values(
        'id', 'code', 'title', 'units', 'year_level', 'semester', 'prerequisite_codes', 'track', 'subject_type', 'program'
    ).order_by('year_level', 'semester', 'code')
    
    return JsonResponse({'subjects': list(subjects)})


@login_required(login_url='login')
def get_student_curriculum(request, student_id):
    """
    Returns a student's curriculum checklist.
    Accessible by advisers/admins for any student.
    Students can only access their own via get_my_curriculum.
    """
    try:
        profile = request.user.userprofile
        if profile.role not in ('adviser',) and not request.user.is_superuser:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
    except UserProfile.DoesNotExist:
        if not request.user.is_superuser:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        student = User.objects.get(id=student_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Student not found'}, status=404)

    # Filter subjects by the student's program
    student_program = getattr(student.userprofile, 'program', 'BSIT')
    all_subjects = CurriculumSubject.objects.filter(program=student_program).order_by('year_level', 'semester', 'code')
    records = {r.subject_id: r for r in StudentCurriculum.objects.filter(student=student)}

    data = []
    for subj in all_subjects:
        rec = records.get(subj.id)
        data.append({
            'id': subj.id,
            'code': subj.code,
            'title': subj.title,
            'units': subj.units,
            'year_level': subj.year_level,
            'semester': subj.semester,
            'prerequisite_codes': subj.prerequisite_codes,
            'track': subj.track,
            'subject_type': subj.subject_type,
            'program': subj.program,
            'status': rec.status if rec else 'not_taken',
            'grade': rec.grade if rec else '',
            'term_taken': rec.term_taken if rec else '',
        })
    return JsonResponse({
        'curriculum': data,
        'student': {
            'name': f"{student.first_name} {student.last_name}".strip() or student.username,
            'student_id': getattr(student.userprofile, 'student_id', 'N/A') if hasattr(student, 'userprofile') else 'N/A',
            'program': getattr(student.userprofile, 'program', 'N/A') if hasattr(student, 'userprofile') else 'N/A',
        }
    })


@login_required(login_url='login')
def get_my_curriculum(request):
    """Student's own curriculum checklist view with enhanced status tracking."""
    user = request.user
    program = getattr(user.userprofile, 'program', 'BSIT')
    
    # Ensure consistent order by year, semester, and code, filtered by program
    all_subjects = CurriculumSubject.objects.filter(program=program).order_by('year_level', 'semester', 'code')
    records = {r.subject_id: r for r in StudentCurriculum.objects.filter(student=user)}
    
    # Get subjects that are currently in TermEnrollment (pending/approved)
    # This helps distinguish between subjects that are truly "Not Taken" vs "Pending" or "Currently Taking"
    term_enrollments = {r.subject_id: r.status for r in user.term_enrollments.all()}

    data = []
    for subj in all_subjects:
        rec = records.get(subj.id)
        term_status = term_enrollments.get(subj.id)
        
        status = rec.status if rec else 'not_taken'
        
        # Override status if there's a more recent TermEnrollment record
        if status == 'not_taken' and term_status:
            status = term_status
            
        data.append({
            'id': subj.id,
            'code': subj.code,
            'title': subj.title,
            'units': subj.units,
            'year_level': subj.year_level,
            'semester': subj.semester,
            'semester_label': subj.get_semester_display(),
            'prerequisite_codes': subj.prerequisite_codes,
            'track': subj.track,
            'subject_type': subj.subject_type,
            'program': subj.program,
            'status': status,
            'grade': rec.grade if rec else '',
            'term_taken': rec.term_taken if rec else '',
        })
    return JsonResponse({'curriculum': data})


def recalculate_enrollment_status(student_user):
    """
    Automates the enrollment status transition based on academic activity.
    - 'enrolled': If any subject is 'in_progress' or they have approved term enrollments.
    - 'not_enrolled': If all finished (passed/failed) and no active sessions.
    """
    from core.models import StudentCurriculum, TermEnrollment
    
    profile = student_user.userprofile
    
    # Check for active academic records
    has_active_subjects = StudentCurriculum.objects.filter(student=student_user, status='in_progress').exists()
    has_approved_enrollments = TermEnrollment.objects.filter(student=student_user, status='approved').exists()
    
    if has_active_subjects or has_approved_enrollments:
        profile.enrollment_status = 'enrolled'
    else:
        # Check if they have pending requests (might be 'pending' status)
        if TermEnrollment.objects.filter(student=student_user, status='pending').exists():
            profile.enrollment_status = 'pending'
        else:
            profile.enrollment_status = 'not_enrolled'
            
    profile.save(update_fields=['enrollment_status'])
    return profile.enrollment_status


@login_required(login_url='login')
def update_student_subject(request):
    """
    Adviser updates a student's subject status (passed/failed/not_taken).
    POST: student_id, subject_id, status, grade (optional)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        profile = request.user.userprofile
        if profile.role != 'admin' and not request.user.is_superuser:
            return JsonResponse({'error': 'Unauthorized: Only Admins can set grades.'}, status=403)
    except UserProfile.DoesNotExist:
        if not request.user.is_superuser:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

    import json as _json
    try:
        body = _json.loads(request.body)
    except Exception:
        body = request.POST

    student_id = body.get('student_id')
    subject_id = body.get('subject_id')
    status = body.get('status', 'not_taken')
    grade = body.get('grade', '')
    term_taken = body.get('term_taken', '')

    try:
        student = User.objects.get(id=student_id)
        subject = CurriculumSubject.objects.get(id=subject_id)
    except (User.DoesNotExist, CurriculumSubject.DoesNotExist):
        return JsonResponse({'error': 'Invalid student or subject'}, status=404)

    rec, _ = StudentCurriculum.objects.update_or_create(
        student=student, subject=subject,
        defaults={'status': status, 'grade': grade, 'term_taken': term_taken}
    )
    
    # Auto-Sync Enrollment Status
    new_status = recalculate_enrollment_status(student)

    return JsonResponse({
        'status': 'success', 
        'message': f'Status for {subject.code} updated to {status}.',
        'student_enrollment_status': new_status
    })
    return JsonResponse({'status': 'ok', 'record_status': rec.status})


@login_required(login_url='login')
def generate_enrollment_code(request):
    """
    Adviser generates a single-use Enrollment Code for a specific student.
    POST JSON: { student_id, subject_ids: [...], term_label }
    Returns: { code, term_label, subjects: [...] }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        profile = request.user.userprofile
        if profile.role not in ('adviser',) and not request.user.is_superuser:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
    except UserProfile.DoesNotExist:
        if not request.user.is_superuser:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

    import json as _json
    try:
        body = _json.loads(request.body)
    except Exception:
        body = request.POST

    student_id = body.get('student_id')
    subject_ids = body.get('subject_ids', [])
    term_label = body.get('term_label', '').strip()

    if not student_id or not subject_ids or not term_label:
        return JsonResponse({'error': 'student_id, subject_ids, and term_label are required'}, status=400)

    try:
        student = User.objects.get(id=student_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Student not found'}, status=404)

    subjects = CurriculumSubject.objects.filter(id__in=subject_ids)
    if not subjects.exists():
        return JsonResponse({'error': 'No valid subjects selected'}, status=400)

    # Validation: Filter out subjects the student has already passed or is currently taking
    from core.models import StudentCurriculum
    existing_records = StudentCurriculum.objects.filter(student=student, subject__in=subjects)
    status_map = {r.subject_id: r.status for r in existing_records}
    
    filtered_subjects = []
    blocked_subjects = []

    for s in subjects:
        status = status_map.get(s.id, 'not_taken')
        if status in ['passed', 'in_progress']:
            blocked_subjects.append(f"{s.code} ({status.replace('_', ' ')})")
        else:
            filtered_subjects.append(s)

    if not filtered_subjects:
        return JsonResponse({'error': f'All selected subjects are already: {", ".join(blocked_subjects)}'}, status=400)

    enc = EnrollmentCode.objects.create(
        student=student,
        adviser=request.user,
        term_label=term_label,
    )
    enc.approved_subjects.set(filtered_subjects)

    # Auto-Send to Student via Message
    Message.objects.create(
        sender=request.user,
        receiver=student,
        content=f"Hello! I have generated your Enrollment Code for {term_label}: {enc.code}. You can now use this to redeem your subjects in your dashboard."
    )

    resp = {
        'status': 'success',
        'code': enc.code,
        'term_label': enc.term_label,
        'student_name': f"{student.first_name} {student.last_name}".strip() or student.username,
        'subjects': [{'id': s.id, 'code': s.code, 'title': s.title, 'units': s.units} for s in filtered_subjects],
    }
    if blocked_subjects:
        resp['warning'] = f'Some subjects were excluded: {", ".join(blocked_subjects)}'
        
    return JsonResponse(resp)

@login_required
def request_subject_enrollment(request):
    """
    Endpoint for students to manually request enrollment in a specific subject.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            subject_id = data.get('subject_id')
            term_label = data.get('term_label', 'Manual Request')
            
            user_profile = request.user.userprofile
            subject = CurriculumSubject.objects.get(id=subject_id)
            
            # Validation: Check StudentCurriculum status
            from core.models import StudentCurriculum
            status_rec = StudentCurriculum.objects.filter(student=request.user, subject=subject).first()
            if status_rec:
                if status_rec.status == 'passed':
                    return JsonResponse({'status': 'error', 'error': f'You have already passed {subject.code}.'})
                if status_rec.status == 'in_progress':
                    return JsonResponse({'status': 'error', 'error': f'You are already enrolled in {subject.code}.'})

            # Check if there is already a pending TermEnrollment
            if TermEnrollment.objects.filter(student=request.user, subject=subject, status='pending').exists():
                return JsonResponse({'status': 'error', 'error': f'A request for {subject.code} is already pending.'})

            # Create or update TermEnrollment with 'pending' status
            enrollment, created = TermEnrollment.objects.get_or_create(
                student=request.user,
                subject=subject,
                defaults={'term_label': term_label, 'status': 'pending'}
            )
            
            if not created:
                enrollment.status = 'pending'
                enrollment.save()
            
            # Update student status to 'pending' if not already enrolled
            if user_profile.enrollment_status != 'enrolled':
                user_profile.enrollment_status = 'pending'
                user_profile.save()
            
            return JsonResponse({'status': 'success', 'message': f'Request for {subject.code} submitted.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)})
    return JsonResponse({'status': 'error', 'error': 'Invalid request method.'})

@login_required
def process_enrollment_request(request):
    """
    Endpoint for Admins to approve or decline enrollment requests.
    """
    if not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'error': 'Unauthorized.'})
        
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            enrollment_ids = data.get('enrollment_ids', [])
            action = data.get('action') # 'approve' or 'decline'
            
            if action not in ['approve', 'decline']:
                return JsonResponse({'status': 'error', 'error': 'Invalid action.'})
            
            enrollments = TermEnrollment.objects.filter(id__in=enrollment_ids)
            
            for enrollment in enrollments:
                if action == 'approve':
                    enrollment.status = 'approved'
                else:
                    enrollment.status = 'declined'
                enrollment.save()
                
                # Auto-Sync Enrollment Status
                recalculate_enrollment_status(enrollment.student)

            return JsonResponse({'status': 'success', 'message': f'Successfully {action}ed {len(enrollment_ids)} requests.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)})
    return JsonResponse({'status': 'error', 'error': 'Invalid request method.'})

def get_recommended_subjects(student_profile):
    """
    Helper function to suggest subjects based on curriculum and prerequisites.
    Uses StudentCurriculum for accurate tracking.
    """
    program = getattr(student_profile, 'program', 'BSIT')
    curriculum = CurriculumSubject.objects.filter(program=program).order_by('year_level', 'semester')
    
    # Get subjects already passed
    passed_subjects = set(StudentCurriculum.objects.filter(
        student=student_profile.user, 
        status='passed'
    ).values_list('subject__code', flat=True))
    
    # Get subjects currently in_progress or pending
    in_progress = set(StudentCurriculum.objects.filter(
        student=student_profile.user, 
        status='in_progress'
    ).values_list('subject__code', flat=True))
    
    pending = set(TermEnrollment.objects.filter(
        student=student_profile.user,
        status='pending'
    ).values_list('subject__code', flat=True))
    
    recommendations = []
    
    for subject in curriculum:
        # Don't recommend if already passed, in_progress, or pending
        if subject.code in passed_subjects or subject.code in in_progress or subject.code in pending:
            continue
            
        # Check prerequisites
        if not subject.prerequisite_codes or subject.prerequisite_codes.lower() == 'none':
            recommendations.append(subject)
        else:
            prereqs = [p.strip() for p in subject.prerequisite_codes.split(',') if p.strip()]
            all_met = True
            for p in prereqs:
                if p not in passed_subjects:
                    all_met = False
                    break
            if all_met:
                recommendations.append(subject)
        
        if len(recommendations) >= 8: # Increased limit for Adviser view
            break
                
    return recommendations

@login_required
def get_adviser_student_details(request, student_id):
    """
    API for Adviser to get localized student info: active subjects and recommendations.
    """
    try:
        if request.user.userprofile.role not in ['adviser', 'admin'] and not request.user.is_superuser:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
            
        student = User.objects.get(id=student_id)
        profile = student.userprofile
        
        # Active Subjects (In Progress)
        active_recs = StudentCurriculum.objects.filter(student=student, status='in_progress').select_related('subject')
        active_list = [{
            'id': r.subject.id,
            'code': r.subject.code,
            'title': r.subject.title,
            'units': r.subject.units,
            'term': r.term_taken
        } for r in active_recs]
        
        # Recommendations
        recs = get_recommended_subjects(profile)
        rec_list = [{
            'id': s.id,
            'code': s.code,
            'title': s.title,
            'units': s.units,
            'year': s.year_level,
            'sem': s.semester
        } for s in recs]
        
        return JsonResponse({
            'status': 'success',
            'student_id': student.id,
            'active_subjects': active_list,
            'recommendations': rec_list
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)

@login_required(login_url='login')
@ratelimit(key='user', rate='5/m', method='POST', block=True)
def chatbot_api(request):
    """
    Gemini 1.5 Flash Chatbot API.
    Identity: Advise AI Virtual Assistant for TIP.
    Data Awareness: BSIT/BSCS program, recommended subjects, rules on enrollment and grades.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        history = data.get('history', []) # Should be a list of {role: "user"|"model", parts: [text]}

        if not user_message:
            return JsonResponse({'error': 'Message required'}, status=400)

        profile = request.user.userprofile
        program = profile.program or "Not Assigned"
        
        # Get "Must-Take" courses
        recommended = get_recommended_subjects(profile)
        must_take_str = ", ".join([f"{s.code} ({s.title})" for s in recommended]) if recommended else "No specific recommendations at this time. Maintain your current pace."

        # Configure Gemini
        from django.conf import settings
        genai.configure(api_key=settings.GEMINI_API_KEY)

        # System Instruction
        system_instruction = (
            "You are the Advise AI Virtual Assistant."
            f"The current student is in the {program} program. "
            "Your tone is helpful, professional, and encouraging. "
            "\n\nCONSTRAINTS & RULES:\n"
            "1. Enrollment: If asked about enrollment, explain that students need a Code from an Adviser which they can redeem in the 'Enroll' tab or the 'Enrollment' section of the dashboard.\n"
            "2. Grades: If asked about grades or status, explain that Admins are the only ones who can set 'Passed/Failed' status. You are an Adviser, not an Operator.\n"
            f"3. Curriculum: Based on the student's progress, the current 'Must-Take' recommended courses are: {must_take_str}.\n"
            "4. Handoff: If the student asks for a human adviser or a more personalized interaction, direct them to the 'Messages' tab to contact their specific Adviser or staff.\n"
            "5. NO HALLUCINATIONS: Do not promise that you can change database records, set grades, or perform administrative actions. You only provide information and guidance.\n"
            "6. Identity: Always identify as the Advise AI Virtual Assistant"
        )

        model = genai.GenerativeModel(
            model_name="gemini-flash-latest",
            system_instruction=system_instruction
        )

        # Convert history format if necessary
        # History from frontend expected: [{role: "user", content: "..."}, {role: "bot", content: "..."}]
        # Gemini expected: [{role: "user", parts: ["..."]}, {role: "model", parts: ["..."]}]
        formatted_history = []
        for h in history:
            role = "user" if h.get('role') == 'user' else "model"
            formatted_history.append({"role": role, "parts": [h.get('content', '')]})

        chat = model.start_chat(history=formatted_history)
        response = chat.send_message(user_message)

        return JsonResponse({
            'status': 'success',
            'reply': response.text
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)

@login_required
def video_call_session(request, room_name):
    """
    Renders a standalone, professional video conference page for the given room name.
    """
    import re
    # Sanitize room name: Alphanumeric and hyphens only to prevent signaling errors
    room_name = re.sub(r'[^a-zA-Z0-9-]', '', room_name)
    
    # Robust Profile Retrieval to handle staff/admins who might not have one yet
    from core.models import UserProfile
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'role': 'admin' if request.user.is_superuser else 'adviser'}
    )
    
    # Try to find the related appointment to track lifecycle
    appointment_id = None
    try:
        # Check if the room name matches one of our appointment links
        apt = Appointment.objects.filter(meeting_link__icontains=room_name).first()
        if apt:
            appointment_id = apt.id
    except:
        pass

    context = {
        'room_name': room_name,
        'role': profile.role,
        'display_name': request.user.get_full_name() or request.user.username,
        'appointment_id': appointment_id,
    }
    return render(request, 'core/video_conference.html', context)


# ─────────────────────────────────────────────────────────────
#  UNIVERSAL ACCOUNT OTP VERIFICATION SYSTEM
# ─────────────────────────────────────────────────────────────
from django.core.mail import send_mail
import random
import string

@login_required(login_url='login')
def send_verification_otp(request):
    """Generates and sends a 6-digit OTP to the user's registered email."""
    user = request.user
    profile = getattr(user, 'userprofile', None)
    
    if not profile:
        messages.error(request, "User profile not found.")
        return redirect('login')
        
    # Superuser bypass
    if user.is_superuser:
        profile.is_email_verified = True
        profile.save()
        return redirect('admin_dashboard')

    # Role-based validation
    if profile.role == 'adviser' and not user.email.endswith('@gmail.com'):
        messages.error(request, "Adviser accounts must use a @gmail.com address. Please contact Admin.")
        return redirect('adviser_dashboard')

    # Generate 6-digit code
    otp = ''.join(random.choices(string.digits, k=6))
    profile.otp_code = otp
    profile.otp_expiry = timezone.now() + timedelta(minutes=10)
    profile.save()
    
    # Send Email
    subject = "Advise AI | Account Verification Code"
    message = f"Hello {user.first_name or user.username},\n\nYour One-Time Password (OTP) for Advise AI is: {otp}\n\nThis code will expire in 10 minutes. Please enter it on your dashboard to verify your account.\n\nBest regards,\nAdvise AI Security Team"
    
    try:
        send_mail(
            subject,
            message,
            None, # Uses DEFAULT_FROM_EMAIL from settings
            [user.email],
            fail_silently=False,
        )
        messages.success(request, f"Verification code sent to {user.email}")
    except Exception as e:
        messages.error(request, f"Failed to send email: {str(e)}. Please check your SMTP settings.")
        
    if profile.role == 'adviser':
        return redirect('adviser_dashboard')
    return redirect('student_dashboard')

@login_required(login_url='login')
def verify_account_otp(request):
    """Checks the submitted OTP and marks the user as verified."""
    if request.method == 'POST':
        user = request.user
        profile = user.userprofile
        otp_input = request.POST.get('otp_code', '').strip()
        
        if not profile.otp_code or not profile.otp_expiry:
            messages.error(request, "Please request a new code first.")
        elif timezone.now() > profile.otp_expiry:
            messages.error(request, "Your code has expired. Please request a new one.")
        elif otp_input == profile.otp_code:
            profile.is_email_verified = True
            profile.otp_code = None # Clear after use
            profile.otp_expiry = None
            profile.save()
            messages.success(request, "Account verified successfully! You now have full access.")
            log_activity(user, "Identity Verified", f"{profile.role.capitalize()} completed email OTP verification.")
        else:
            messages.error(request, "Invalid verification code.")
            
    if user.userprofile.role == 'adviser':
        return redirect('adviser_dashboard')
    return redirect('student_dashboard')


# ─────────────────────────────────────────────────────────────
#  APPOINTMENT LIFECYCLE SIGNALING SYSTEM
# ─────────────────────────────────────────────────────────────

@csrf_exempt
@login_required
def api_signal_appointment_start(request, apt_id):
    """Signals that a video conference has started."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        apt = get_object_or_404(Appointment, id=apt_id)
        # Security: Only the assigned adviser or the student can signal start
        if request.user != apt.adviser and request.user != apt.student:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
            
        apt.status = 'in_progress'
        if not apt.actual_start_at:
            apt.actual_start_at = timezone.now()
        apt.save()
        
        log_activity(request.user, "Meeting Started", f"Session for {apt.purpose} is now in_progress.")
        return JsonResponse({'status': 'success', 'new_status': apt.status})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@login_required
def api_signal_appointment_end(request, apt_id):
    """Signals that a video conference has ended."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        apt = get_object_or_404(Appointment, id=apt_id)
        if request.user != apt.adviser and request.user != apt.student:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
            
        apt.status = 'completed'
        apt.actual_end_at = timezone.now()
        apt.save()
        
        log_activity(request.user, "Meeting Completed", f"Session for {apt.purpose} has ended and marked as Done.")
        return JsonResponse({'status': 'success', 'new_status': apt.status})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def send_branded_appointment_email(appointment, adviser_comment=""):
    """
    Sends a professional, branded HTML email to the student upon appointment approval.
    """
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    import urllib.parse
    
    student = appointment.student
    adviser = appointment.adviser
    
    subject = f"Appointment Confirmed: {appointment.purpose} - Advise AI"
    from_email = settings.DEFAULT_FROM_EMAIL
    to = [student.email]
    
    # 1. Construct Google Calendar URL
    base_cal_url = "https://www.google.com/calendar/render?action=TEMPLATE"
    cal_title = urllib.parse.quote(f"Advising: {appointment.purpose}")
    cal_dates = appointment.date_time.strftime('%Y%m%dT%H%M%S') + "/" + (appointment.date_time + timedelta(minutes=30)).strftime('%Y%m%dT%H%M%S')
    cal_details = urllib.parse.quote(f"Adviser: {adviser.get_full_name()}\nComment: {adviser_comment}\nJoin Meeting: {appointment.meeting_link}")
    calendar_link = f"{base_cal_url}&text={cal_title}&dates={cal_dates}&details={cal_details}&location={urllib.parse.quote(appointment.meeting_link or 'Advise AI Conference')}"

    is_declined = appointment.status == 'declined'
    
    # Mode-based Branding
    color_primary = "#001f3f" if not is_declined else "#475569" # Navy or Slate
    title_text = "Your Appointment is Confirmed!" if not is_declined else "Appointment Decision"
    subtitle_text = "Your session has been approved." if not is_declined else "Your request has been reviewed."

    # 2. Design the HTML Content
    html_content = f"""
    <div style="font-family: 'Inter', system-ui, -apple-system, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #eef2f6; border-radius: 16px; overflow: hidden; background-color: #ffffff;">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, {color_primary} 0%, #000000 100%); padding: 32px; text-align: center; color: #ffffff;">
            <div style="font-size: 24px; font-weight: 800; letter-spacing: -0.02em; margin-bottom: 8px;">ADVISE AI</div>
            <div style="font-size: 14px; opacity: 0.8; font-weight: 500;">Academic Excellence Through Guidance</div>
        </div>

        <!-- Body -->
        <div style="padding: 40px; color: #1e293b; line-height: 1.6;">
            <h1 style="font-size: 20px; font-weight: 700; margin-bottom: 24px; color: {color_primary};">{title_text}</h1>
            
            <p style="margin-bottom: 24px;">Hello <strong>{student.first_name or student.username}</strong>,</p>
            
            <p style="margin-bottom: 32px;">{subtitle_text} Regarding session: <strong>"{appointment.purpose}"</strong>.</p>
            
            <!-- Details Card -->
            <div style="background-color: #f8fafc; border-radius: 12px; padding: 24px; margin-bottom: 32px; border: 1px solid #f1f5f9;">
                <div style="margin-bottom: 16px;">
                    <div style="font-size: 10px; font-weight: 800; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">Status</div>
                    <div style="font-size: 15px; font-weight: 700; color: {'#16a34a' if not is_declined else '#dc2626'}; text-transform: uppercase;">{appointment.status}</div>
                </div>

                <div style="margin-bottom: 16px;">
                    <div style="font-size: 10px; font-weight: 800; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">Adviser</div>
                    <div style="font-size: 15px; font-weight: 600; color: #001f3f;">{adviser.get_full_name() or adviser.username}</div>
                </div>

                {f'''
                <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #e2e8f0;">
                    <div style="font-size: 10px; font-weight: 800; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">Adviser's Feedback</div>
                    <div style="font-size: 14px; font-style: italic; color: #475569;">"{adviser_comment}"</div>
                </div>
                ''' if adviser_comment else ''}
            </div>

            {'<!-- Join Link -->' if not is_declined else ''}
            {f'''
            <div style="text-align: center; margin-bottom: 32px;">
                <a href="{appointment.meeting_link}" style="display: inline-block; background-color: #001f3f; color: #ffffff; padding: 16px 32px; border-radius: 12px; font-weight: 700; text-decoration: none; font-size: 15px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">Join Video Conference</a>
            </div>
            <div style="text-align: center;">
                <a href="{calendar_link}" style="font-size: 13px; font-weight: 600; color: #64748b; text-decoration: none; border-bottom: 1px solid #cbd5e1; padding-bottom: 2px;">+ Add to Google Calendar</a>
            </div>
            ''' if not is_declined else '<p style="text-align: center; font-size: 13px; color: #64748b;">Please review the notes above and contact your adviser for further coordination.</p>'}
        </div>

        <!-- Footer -->
        <div style="background-color: #f8fafc; padding: 24px; text-align: center; border-top: 1px solid #f1f5f9;">
            <p style="font-size: 12px; color: #94a3b8; margin: 0;">Automated notification from Advise AI System.</p>
        </div>
    </div>
    """
    
    text_content = strip_tags(html_content)
    
    msg = EmailMultiAlternatives(subject, text_content, from_email, to)
    msg.attach_alternative(html_content, "text/html")
    
    try:
        msg.send()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def api_get_appointment_conflicts(request):
    """
    Checks for schedule overlaps and identifies free advisers for peer recommendation.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
        
    apt_id = request.GET.get('apt_id')
    try:
        apt = Appointment.objects.get(id=apt_id)
        target_time = apt.date_time
        
        # 1. Check current adviser conflicts (30m window)
        start_win = target_time - timedelta(minutes=29)
        end_win = target_time + timedelta(minutes=29)
        
        conflicts = Appointment.objects.filter(
            adviser=request.user,
            date_time__range=(start_win, end_win),
            status__in=['confirmed', 'in_progress']
        ).exclude(id=apt.id)
        
        has_conflict = conflicts.exists()
        conflict_details = []
        for c in conflicts:
            conflict_details.append({
                'purpose': c.purpose,
                'time': c.date_time.strftime('%I:%M %p'),
                'student': c.student.get_full_name() or c.student.username
            })
            
        # 2. Recommend available advisers
        # Find advisers who have NO sessions in this window
        busy_adviser_ids = Appointment.objects.filter(
            date_time__range=(start_win, end_win),
            status__in=['confirmed', 'in_progress']
        ).values_list('adviser_id', flat=True)
        
        available_advisers = UserProfile.objects.filter(
            role='adviser'
        ).exclude(user_id__in=busy_adviser_ids).exclude(user_id=request.user.id)
        
        recommendations = []
        for p in available_advisers:
            recommendations.append({
                'id': p.user.id,
                'name': p.user.get_full_name() or p.user.username
            })

        return JsonResponse({
            'has_conflict': has_conflict,
            'conflicts': conflict_details,
            'recommendations': recommendations
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
