from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import UserProfile

def landing_page(request):
    return render(request, 'core/landing.html')

def login_page(request):
    if request.method == 'POST':
        role = request.POST.get('role', 'student')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
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
        return redirect('login')
        
    return render(request, 'core/register.html')

def logout_user(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('landing')

def about_page(request):
    return render(request, 'core/about.html')

from .models import UserProfile, Course, Enrollment, FormSubmission, Appointment, Message

@login_required(login_url='login')
def student_dashboard(request):
    user = request.user
    profile = user.userprofile
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'enroll_verification':
            code = request.POST.get('curriculum_code')
            if code:
                profile.curriculum_code = code
                profile.enrollment_status = 'pending'
                profile.save()
                messages.success(request, 'Enrollment code submitted! Waiting for adviser approval.')
            else:
                messages.error(request, 'Please enter a valid code.')
        
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
            content = request.POST.get('content')
            if content:
                # Find an adviser to send the message to (defaulting to any for now)
                adviser_profile = UserProfile.objects.filter(role='adviser').first()
                if adviser_profile:
                    Message.objects.create(sender=user, receiver=adviser_profile.user, content=content)
                    messages.success(request, 'Message sent successfully.')
                else:
                    messages.error(request, 'No adviser available to message right now.')
            
        return redirect('student_dashboard')

    # Fetch data for dashboard
    enrollment_status = profile.enrollment_status
    courses = Enrollment.objects.filter(student=user) if enrollment_status == 'enrolled' else []
    
    student_forms = FormSubmission.objects.filter(student=user).order_by('-submitted_at')
    student_appointments = Appointment.objects.filter(student=user).order_by('-date_time')
    
    pending_approvals = student_forms.filter(status='pending').count()
    appointments_count = student_appointments.filter(status='pending').count()
    
    # Adviser messages
    adviser_messages = Message.objects.filter(receiver=user).order_by('-sent_at')[:5]

    context = {
        'profile': profile,
        'enrollment_status': enrollment_status,
        'courses': courses,
        'pending_approvals': pending_approvals,
        'appointments_count': appointments_count,
        'student_forms': student_forms,
        'student_appointments': student_appointments,
        'adviser_messages': adviser_messages,
    }
    return render(request, 'core/student.html', context)

@login_required(login_url='login')
def adviser_dashboard(request):
    user = request.user
    
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
                        # Send as message to student
                        Message.objects.create(sender=user, receiver=form.student, content=f"Response to {form.title}: {adviser_notes}")
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
                    if adviser_notes:
                        apt.adviser_notes = adviser_notes
                        Message.objects.create(sender=user, receiver=apt.student, content=f"Appointment Update ({apt.purpose}): {adviser_notes}")
                    apt.save()
                    messages.success(request, f'Appointment {status} successfully.')
                except Appointment.DoesNotExist:
                    messages.error(request, 'Appointment not found.')
                    
        return redirect('adviser_dashboard')

    pending_forms = FormSubmission.objects.filter(status__in=['pending', 'pending-review']).order_by('-submitted_at')
    pending_appointments = Appointment.objects.filter(status='pending').order_by('date_time')
    confirmed_appointments = Appointment.objects.filter(status='confirmed', adviser=user).order_by('date_time')
    my_students = UserProfile.objects.filter(role='student') # For simplicity, all students
    
    context = {
        'forms': pending_forms,
        'pending_appointments': pending_appointments,
        'confirmed_appointments': confirmed_appointments,
        'my_students': my_students,
        'total_advisees': my_students.count(),
        'pending_inquiries': pending_forms.count(),
        'appointments_today': pending_appointments.count(), # roughly
    }
    return render(request, 'core/adviser.html', context)

@login_required(login_url='login')
def admin_dashboard(request):
    if not request.user.is_superuser and request.user.userprofile.role != 'admin':
        messages.error(request, "Access denied.")
        return redirect('landing')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_staff':
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
                
        return redirect('admin_dashboard')

    staff_users = UserProfile.objects.exclude(role='student')
    advisers = staff_users.filter(role='adviser')
    admins = staff_users.filter(role='admin')
    students = UserProfile.objects.filter(role='student')
    pending_enrollments = UserProfile.objects.filter(role='student', enrollment_status='pending')
    
    context = {
        'staff_users': staff_users,
        'advisers': advisers,
        'admins': admins,
        'students': students,
        'pending_enrollments': pending_enrollments,
        'total_students': students.count(),
        'total_staff': staff_users.count(),
        'online_users': User.objects.filter(is_active=True).count(),
        'total_forms': FormSubmission.objects.count(),
        'total_appointments': Appointment.objects.count(),
        'avg_response_time': f"{round(1.0 + (FormSubmission.objects.count() * 0.1), 1)} hours"
    }
    return render(request, 'core/admin.html', context)

def forms_portal(request):
    return render(request, 'core/forms.html')

def admin_users(request):
    return render(request, 'core/admin.html')

def admin_settings(request):
    return render(request, 'core/admin.html')
