from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('login/', views.login_page, name='login'),
    path('register/', views.register_page, name='register'),
    path('about/', views.about_page, name='about'),
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('adviser/', views.adviser_dashboard, name='adviser_dashboard'),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('forms_portal/', views.forms_portal, name='forms_portal'),
    path('admin/users/', views.admin_users, name='admin_users'),
    path('admin/settings/', views.admin_settings, name='admin_settings'),
]
