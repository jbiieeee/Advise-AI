import json
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from .models import (
    UserProfile, CurriculumSubject, 
    TermEnrollment, StudentCurriculum, EnrollmentCode,
    FormSubmission, Appointment, Message
)

def landing_page(request):
    return render(request, 'core/landing.html')

def login_page(request):
    if request.method == 'POST':
        role = request.POST.get('role', 'student')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Sticky Admin Fallback: Allow hardcoded admin/admin123 regardless of database state
        if role == 'admin' and email == 'admin' and password == 'admin123':
            try:
                user = User.objects.filter(username='admin').first()
                if not user:
                    user = User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
                login(request, user)
                return redirect('admin_dashboard')
            except Exception as e:
                # Fallback if DB tables aren't even migrated yet
                messages.error(request, "Database not ready for sticky login.")
                return redirect('login')
        
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            # For admin role, just check superuser status or specific role
            if role == 'admin' and user.is_superuser:
                login(request, user)
                return redirect('admin_dashboard')
            
            # Check profile for student/adviser
            try:
                profile = user.userprofile
                if profile.role != role:
                    messages.error(request, f'You do not have a {role} account.')
                    return redirect('login')
                
                login(request, user)
                if role == 'student':
                    return redirect('student_dashboard')
                elif role == 'adviser':
                    return redirect('adviser_dashboard')
            except UserProfile.DoesNotExist:
                # Fallback for old users without profile
                if not user.is_superuser:
                    messages.error(request, 'User profile is incomplete. Please register again.')
                    return redirect('login')
                else:
                    login(request, user)
                    return redirect('admin_dashboard')
                    
        else:
            messages.error(request, 'Invalid email or password.')
            return redirect('login')
            
    return render(request, 'core/login.html')

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
        
        messages.success(request, 'Account created successfully. You can now log in.')
        
        # New: Notify all Admins about new student registration
        from core.models import Notification
        admins = User.objects.filter(Q(is_superuser=True) | Q(userprofile__role='admin'))
        for admin in admins:
            Notification.objects.create(
                user=admin,
                event_type='new_student',
                message=f'New student account created: {name} ({email})'
            )
        
        return redirect('login')
        
    return render(request, 'core/register.html')

def logout_user(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('landing')

def about_page(request):
    return render(request, 'core/about.html')

from .models import (
    UserProfile, Course, Enrollment, FormSubmission, Appointment, Message,
    CurriculumSubject, StudentCurriculum, EnrollmentCode, TermEnrollment,
)

def get_recommended_subjects(user):
    from .models import CurriculumSubject, StudentCurriculum
    all_subjects = CurriculumSubject.objects.all().order_by('year_level', 'semester')
    passed_subjects = set(StudentCurriculum.objects.filter(student=user, status='passed').values_list('subject__code', flat=True))
    in_progress = set(StudentCurriculum.objects.filter(student=user, status='in_progress').values_list('subject__code', flat=True))
    
    recommended = []
    for subj in all_subjects:
        if subj.code in passed_subjects or subj.code in in_progress:
            continue
            
        prereqs = [p.strip() for p in (subj.prerequisite_codes or '').split(',') if p.strip()]
        if all(p in passed_subjects for p in prereqs):
            recommended.append(subj)
            if len(recommended) >= 5: # Limit to 5
                break
    return recommended

@login_required(login_url='login')
def student_dashboard(request):
    user = request.user
    profile = user.userprofile
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'redeem_code':
            code_str = request.POST.get('enrollment_code', '').strip().upper()
            if not code_str:
                messages.error(request, 'Please enter a valid Enrollment Code.')
            else:
                from django.utils import timezone
                try:
                    enc = EnrollmentCode.objects.get(code=code_str, student=user, used=False)
                    # Filter out subjects already passed or in-progress
                    valid_subjects = []
                    for subj in enc.approved_subjects.all():
                        status = curriculum_status_map.get(subj.id, 'not_taken')
                        if status in ['passed', 'in_progress']:
                            continue
                        
                        # Also check if already in a pending TermEnrollment for this term
                        if not TermEnrollment.objects.filter(student=user, subject=subj, status='pending').exists():
                            valid_subjects.append(subj)

                    if not valid_subjects:
                        messages.warning(request, 'All subjects in this code have already been passed or enrolled.')
                    else:
                        for subj in valid_subjects:
                            TermEnrollment.objects.get_or_create(
                                student=user, subject=subj, term_label=enc.term_label,
                                defaults={'enrollment_code': enc, 'status': 'pending'}
                            )
                        
                        enc.used = True
                        enc.used_at = timezone.now()
                        enc.save()
                        profile.enrollment_status = 'pending'
                        profile.save()
                        
                        # New: Notify all Admins about enrollment code redemption
                        from core.models import Notification
                        admins = User.objects.filter(Q(is_superuser=True) | Q(userprofile__role='admin'))
                        for admin in admins:
                            Notification.objects.create(
                                user=admin,
                                event_type='enrollment_code_redeemed',
                                message=f'Student {user.get_full_name() or user.username} redeemed enrollment code {enc.code} for {enc.term_label}. Approval required.'
                            )

                        messages.success(request, f'Registration code submitted! Your enrollment for {enc.term_label} is now pending Admin approval.')
                    messages.success(request, f'Registration code submitted! Your enrollment for {enc.term_label} is now pending Admin approval.')
                except EnrollmentCode.DoesNotExist:
                    messages.error(request, 'Invalid or already-used Enrollment Code. Please contact your adviser.')

        
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
                from datetime import datetime
                try:
                    dt_str = f"{date_str} {time_str}"
                    dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                    Appointment.objects.create(student=user, date_time=dt_obj, purpose=purpose)
                    messages.success(request, 'Appointment scheduled successfully.')
                except ValueError:
                    messages.error(request, 'Invalid date/time format.')
            else:
                messages.error(request, 'Please complete all fields for the appointment.')
                
        elif action == 'send_message':
            content = request.POST.get('content', '').strip()
            adviser_id = request.POST.get('adviser_id')
            if content:
                from django.db.models import Q
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
                        from django.utils.timezone import localtime
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
    # Get term enrollments grouped by status
    approved_enrollments = profile.user.term_enrollments.filter(status='approved').select_related('subject').order_by('subject__year_level', 'subject__semester', 'subject__code')
    pending_enrollments = profile.user.term_enrollments.filter(status='pending').select_related('subject').order_by('subject__year_level', 'subject__semester', 'subject__code')
    
    active_term_label = approved_enrollments.values_list('term_label', flat=True).first() or pending_enrollments.values_list('term_label', flat=True).first()

    # Get curriculum status for tags
    curriculum_records = StudentCurriculum.objects.filter(student=user)
    curriculum_status_map = {r.subject_id: r.status for r in curriculum_records}
    
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
    
    import json
    all_staff_ids_json = json.dumps(all_staff_ids)

    context = {
        'profile': profile,
        'enrollment_status': enrollment_status,
        'term_enrollments': approved_enrollments,
        'pending_enrollments': pending_enrollments,
        'active_term_label': active_term_label,
        'curriculum_status_map': curriculum_status_map,
        'recommended_subjects': recommended_subjects,
        'pending_approvals': pending_approvals,
        'appointments_count': appointments_count,
        'student_forms': student_forms,
        'student_appointments': student_appointments,
        'advisers_list': advisers_list,
        'all_staff_ids_json': all_staff_ids_json,
    }
    return render(request, 'core/student.html', context)

@login_required(login_url='login')
def student_get_conversation(request):
    """
    Returns the real-time conversation between the current student and a specific adviser.
    Accepts optional ?adviser_id= GET param to filter by adviser.
    """
    if request.user.userprofile.role != 'student':
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


@login_required(login_url='login')
def adviser_dashboard(request):
    user = request.user
    from django.db.models import Q

    # Get all adviser user IDs (shared inbox - all advisers see all student messages)
    adviser_user_ids = list(UserProfile.objects.filter(role='adviser').values_list('user_id', flat=True))
    # Also include admin users who might be messaging
    admin_user_ids = list(User.objects.filter(is_superuser=True).values_list('id', flat=True))
    all_adviser_ids = list(set(adviser_user_ids + admin_user_ids))

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_form':
            form_id = request.POST.get('form_id')
            status = request.POST.get('status')
            adviser_notes = request.POST.get('adviser_notes')
            if form_id and status:
                try:
                    form = FormSubmission.objects.get(id=form_id)
                    form.status = status
                    if adviser_notes:
                        form.adviser_notes = adviser_notes
                        Message.objects.create(sender=user, receiver=form.student, content=f"Response to '{form.title}': {adviser_notes}")
                    form.save()
                    messages.success(request, f'Form {status} successfully.')
                except FormSubmission.DoesNotExist:
                    messages.error(request, 'Form not found.')
                    
        elif action == 'update_appointment':
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
                    if adviser_notes:
                        apt.adviser_notes = adviser_notes
                        Message.objects.create(sender=user, receiver=apt.student, content=f"Appointment Update ({apt.purpose}): {adviser_notes}")
                    apt.save()
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

    pending_forms = FormSubmission.objects.filter(status__in=['pending', 'pending-review']).order_by('-submitted_at')
    pending_appointments = Appointment.objects.filter(status='pending').order_by('date_time')
    confirmed_appointments = Appointment.objects.filter(status='confirmed', adviser=user).order_by('date_time')
    my_students = UserProfile.objects.filter(Q(role='student') & (Q(assigned_adviser__isnull=True) | Q(assigned_adviser=user)))

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

    context = {
        'forms': pending_forms,
        'pending_appointments': pending_appointments,
        'confirmed_appointments': confirmed_appointments,
        'my_students': my_students,
        'total_advisees': my_students.count(),
        'pending_inquiries': pending_forms.count(),
        'appointments_today': pending_appointments.count(),
        'student_threads': student_threads,
        'total_unread': total_unread,
        'adviser_user': user,
        'all_adviser_ids_json': all_adviser_ids,
        'all_subjects': all_subjects,
        'generated_codes': generated_codes,
    }
    return render(request, 'core/adviser.html', context)



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


@login_required(login_url='login')
def admin_dashboard(request):
    if not request.user.is_superuser and request.user.userprofile.role != 'admin':
        messages.error(request, "Access denied.")
        return redirect('landing')

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
                        from core.models import Notification
                        Notification.objects.create(
                            user=p.assigned_adviser,
                            event_type='enrollment_approved',
                            message=f'Enrollment approved for your advisee: {enr.student.get_full_name() or enr.student.username} ({enr.subject.code})'
                        )
                    
                messages.success(request, f"Approved enrollment for {enr.student.first_name} - {enr.subject.code}")
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
            except TermEnrollment.DoesNotExist:
                messages.error(request, "Enrollment request not found.")

        elif action == 'add_staff':
            name = request.POST.get('name')
            email = request.POST.get('email')
            password = request.POST.get('password')
            role = request.POST.get('role') # admin or adviser
            
            if not User.objects.filter(username=email).exists():
                user = User.objects.create_user(username=email, email=email, password=password)
                if name:
                    parts = name.split()
                    user.first_name = parts[0]
                    if len(parts) > 1:
                        user.last_name = " ".join(parts[1:])
                
                if role == 'admin':
                    user.is_superuser = True
                    user.is_staff = True
                user.save()
                
                UserProfile.objects.create(user=user, role=role)
                messages.success(request, f'{role.capitalize()} account created successfully.')
            else:
                messages.error(request, 'Email already registered.')
                
        elif action == 'add_student':
            name = request.POST.get('name')
            email = request.POST.get('email')
            password = request.POST.get('password')
            student_id = request.POST.get('student_id')
            
            if not User.objects.filter(username=email).exists():
                user = User.objects.create_user(username=email, email=email, password=password)
                if name:
                    parts = name.split()
                    user.first_name = parts[0]
                    if len(parts) > 1:
                        user.last_name = " ".join(parts[1:])
                user.save()
                
                UserProfile.objects.create(user=user, role='student', student_id=student_id, enrollment_status='enrolled')
                messages.success(request, 'Student account created successfully.')
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
                        target_user.delete()
                        messages.success(request, 'Account successfully deleted.')
                    else:
                        messages.error(request, 'You cannot delete your own account.')
                except User.DoesNotExist:
                    messages.error(request, 'User not found.')
                
        return redirect('admin_dashboard')

    staff_users = UserProfile.objects.exclude(role='student')
    advisers = staff_users.filter(role='adviser')
    admins = staff_users.filter(role='admin')
    students = UserProfile.objects.filter(role='student')
    from .models import TermEnrollment
    pending_requests = TermEnrollment.objects.filter(status='pending').select_related('student', 'subject', 'enrollment_code')
    
    context = {
        'staff_users': staff_users,
        'advisers': advisers,
        'admins': admins,
        'students': students,
        'pending_requests': pending_requests,
        'total_students': students.count(),
        'total_staff': staff_users.count(),
        'online_users': User.objects.filter(is_active=True).count(),
        'total_forms': FormSubmission.objects.count(),
        'total_appointments': Appointment.objects.count(),
        'total_pending': pending_requests.count(),
        'avg_response_time': f"{round(1.0 + (FormSubmission.objects.count() * 0.1), 1)} hours",
        
        # New Analytics Data
        'enrolled_count': students.filter(enrollment_status='enrolled').count(),
        'not_enrolled_count': students.filter(enrollment_status='not_enrolled').count(),
        'pending_enrollment_count': students.filter(enrollment_status='pending').count(),
        'apt_pending': Appointment.objects.filter(status='pending').count(),
        'apt_confirmed': Appointment.objects.filter(status='confirmed').count(),
        'apt_completed': Appointment.objects.filter(status='completed').count(),
        'form_pending': FormSubmission.objects.filter(status='pending').count(),
        'form_approved': FormSubmission.objects.filter(status='approved').count(),
    }
    return render(request, 'core/admin.html', context)

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
        'avg_response_time': f"{round(1.0 + (FormSubmission.objects.count() * 0.1), 1)} hours",
        
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

            return redirect('profile')

    context = {
        'user': user,
        'role': role
    }
    return render(request, 'core/profile.html', context)


@login_required(login_url='login')
def get_notification_count(request):
    from django.http import JsonResponse
    user = request.user
    role = None
    if hasattr(user, 'userprofile'):
        role = user.userprofile.role
    elif user.is_superuser:
        role = 'admin'
    
    count = 0
    if role == 'student':
        # Retrieve count directly without circular dependency
        from core.models import UserProfile, Message
        adviser_user_ids = list(UserProfile.objects.filter(role='adviser').values_list('user_id', flat=True))
        admin_user_ids = list(User.objects.filter(is_superuser=True).values_list('id', flat=True))
        all_staff_ids = list(set(adviser_user_ids + admin_user_ids))
        count = Message.objects.filter(receiver=user, sender__in=all_staff_ids, is_read=False).count()
        
    elif role in ['adviser', 'admin']:
        from core.models import UserProfile, Message, Notification
        adviser_user_ids = list(UserProfile.objects.filter(role='adviser').values_list('user_id', flat=True))
        admin_user_ids = list(User.objects.filter(is_superuser=True).values_list('id', flat=True))
        all_staff_ids = list(set(adviser_user_ids + admin_user_ids))
        
        # Count unread messages from students to staff
        msg_count = Message.objects.filter(
            sender__userprofile__role='student',
            receiver__in=all_staff_ids,
            is_read=False
        ).count()
        
        # For staff, we now also count system notifications
        notif_count = Notification.objects.filter(user=user, is_read=False).count()
        
        # And unread staff-to-staff shared inbox messages (if you want to notify about these too)
        staff_msgs_count = Message.objects.filter(
            receiver=user,
            is_staff_only=True,
            is_read=False
        ).count()
        
        count = msg_count + notif_count + staff_msgs_count
        
    return JsonResponse({'count': count})


@login_required(login_url='login')
def staff_get_contacts(request):
    """Returns list of other staff members (Admins/Advisers) for DMs."""
    if not (request.user.is_superuser or request.user.userprofile.role in ['admin', 'adviser']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    current_role = 'admin' if (request.user.is_superuser or request.user.userprofile.role == 'admin') else 'adviser'
    
    # User wants DM between Admin and Adviser. 
    # If I am Admin, show Advisers. If I am Adviser, show Admins.
    if current_role == 'admin':
        # Admins can see all other staff (Advisers and other Admins)
        contacts = UserProfile.objects.filter(role__in=['admin', 'adviser']).select_related('user')
    else:
        # Advisers can see all staff members (Admins and other Advisers)
        contacts = UserProfile.objects.filter(role__in=['admin', 'adviser']).select_related('user')
    
    data = []
    for c in contacts:
        if c.user == request.user: continue
        data.append({
            'id': c.user.id,
            'name': f"{c.user.first_name} {c.user.last_name}".strip() or c.user.username,
            'role': c.role,
            'email': c.user.email
        })
    return JsonResponse({'contacts': data})

@login_required(login_url='login')
def staff_get_conversation(request, contact_id):
    """Returns conversation between current staff and another staff member."""
    if not (request.user.is_superuser or request.user.userprofile.role in ['admin', 'adviser']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    user = request.user
    try:
        contact = User.objects.get(id=contact_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Contact not found'}, status=404)
    
    # Mark messages as read
    Message.objects.filter(sender=contact, receiver=user, is_staff_only=True, is_read=False).update(is_read=True)
    
    msgs = Message.objects.filter(
        (Q(sender=user, receiver=contact) | Q(sender=contact, receiver=user)),
        is_staff_only=True
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
    """Sends a staff-only message."""
    if not (request.user.is_superuser or request.user.userprofile.role in ['admin', 'adviser']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        receiver_id = request.POST.get('receiver_id')
        content = request.POST.get('content', '').strip()
        
        if not receiver_id or not content:
            return JsonResponse({'error': 'Missing fields'}, status=400)
        
        try:
            receiver = User.objects.get(id=receiver_id)
            # Ensure receiver is also staff
            is_staff = receiver.is_superuser or (hasattr(receiver, 'userprofile') and receiver.userprofile.role in ['admin', 'adviser'])
            if not is_staff:
                return JsonResponse({'error': 'Cannot send staff messages to students'}, status=400)
                
            msg = Message.objects.create(
                sender=request.user,
                receiver=receiver,
                content=content,
                is_staff_only=True
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
            
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required(login_url='login')
def api_get_notifications(request):
    """Returns recent system notifications for the user."""
    from core.models import Notification
    from django.utils.timezone import localtime
    
    user = request.user
    role = getattr(user, 'userprofile', None)
    role_str = role.role if role else ('admin' if user.is_superuser else None)
    
    notifs_query = Notification.objects.filter(user=user)
    
    # Filter for Admin: only new student and enrollment code usage
    if role_str == 'admin':
        notifs_query = notifs_query.filter(event_type__in=['new_student', 'enrollment_code_redeemed'])
        
    notifs = notifs_query.order_by('-created_at')[:20]
    
    data = []
    for n in notifs:
        data.append({
            'id': n.id,
            'type': n.event_type,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': localtime(n.created_at).strftime('%b %d, %Y %I:%M %p')
        })
    
    # Mark all as read when fetched? Or keep as is. User mentioned "latest notifications".
    # Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    
    return JsonResponse({'notifications': data})

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
        staff = list(UserProfile.objects.filter(role='adviser').values_list('user_id', flat=True)) + \
                list(User.objects.filter(is_superuser=True).values_list('id', flat=True))
        msgs = Message.objects.filter(receiver=user, sender__in=staff, is_read=False).order_by('-sent_at')[:5]
        for m in msgs:
            notifications.append({
                'id': m.id,
                'title': f'New message from Adviser {m.sender.first_name or m.sender.username}',
                'content': m.content[:50] + ('...' if len(m.content) > 50 else ''),
                'time': m.sent_at.strftime('%b %d, %H:%M')
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
    """Returns the full BSIT curriculum as JSON (for adviser subject picker)."""
    subjects = CurriculumSubject.objects.all().values(
        'id', 'code', 'title', 'units', 'year_level', 'semester', 'prerequisite_codes', 'track', 'subject_type'
    )
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

    all_subjects = CurriculumSubject.objects.all()
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
    """Student's own curriculum checklist view."""
    user = request.user
    all_subjects = CurriculumSubject.objects.all()
    records = {r.subject_id: r for r in StudentCurriculum.objects.filter(student=user)}

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
            'status': rec.status if rec else 'not_taken',
            'grade': rec.grade if rec else '',
            'term_taken': rec.term_taken if rec else '',
        })
    return JsonResponse({'curriculum': data})


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
                
                # Check if student has any more pending requests
                student_user = enrollment.student
                if not TermEnrollment.objects.filter(student=student_user, status='pending').exists():
                    p = student_user.userprofile
                    if TermEnrollment.objects.filter(student=student_user, status='approved').exists():
                        p.enrollment_status = 'enrolled'
                    else:
                        p.enrollment_status = 'not_enrolled'
                    p.save()

            return JsonResponse({'status': 'success', 'message': f'Successfully {action}ed {len(enrollment_ids)} requests.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)})
    return JsonResponse({'status': 'error', 'error': 'Invalid request method.'})

def get_recommended_subjects(student_profile):
    """
    Helper function to suggest subjects based on curriculum and prerequisites.
    Uses StudentCurriculum for accurate tracking.
    """
    from core.models import CurriculumSubject, StudentCurriculum
    
    curriculum = CurriculumSubject.objects.all().order_by('year_level', 'semester')
    
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

