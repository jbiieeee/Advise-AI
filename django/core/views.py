from django.shortcuts import render

def landing_page(request):
    return render(request, 'core/landing.html')

def login_page(request):
    return render(request, 'core/login.html')

def register_page(request):
    return render(request, 'core/register.html')

def about_page(request):
    return render(request, 'core/about.html')

def student_dashboard(request):
    return render(request, 'core/student.html')

def adviser_dashboard(request):
    return render(request, 'core/adviser.html')

def admin_dashboard(request):
    return render(request, 'core/admin.html')

def forms_portal(request):
    return render(request, 'core/forms.html')

def admin_users(request):
    return render(request, 'core/admin.html')

def admin_settings(request):
    return render(request, 'core/admin.html')
