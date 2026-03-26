from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('login/', views.login_page, name='login'),
    path('register/', views.register_page, name='register'),
    path('logout/', views.logout_user, name='logout'),
    path('about/', views.about_page, name='about'),
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('student/conversation/', views.student_get_conversation, name='student_get_conversation'),
    path('adviser/', views.adviser_dashboard, name='adviser_dashboard'),
    path('adviser/conversation/<int:student_id>/', views.get_conversation, name='get_conversation'),
    path('api/notifications/count/', views.get_notification_count, name='get_notification_count'),
    path('api/notifications/latest/', views.get_latest_notifications, name='get_latest_notifications'),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('forms_portal/', views.forms_portal, name='forms_portal'),
    path('admin/users/', views.admin_users, name='admin_users'),
    path('admin/settings/', views.admin_settings, name='admin_settings'),
]
