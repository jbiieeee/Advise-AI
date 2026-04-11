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

    # ── Curriculum & Enrollment Code APIs ─────────────────────
    path('api/curriculum/', views.get_all_curriculum, name='get_all_curriculum'),
    path('api/curriculum/<int:student_id>/', views.get_student_curriculum, name='get_student_curriculum'),
    path('api/curriculum/mine/', views.get_my_curriculum, name='get_my_curriculum'),
    path('api/curriculum/update-subject/', views.update_student_subject, name='update_student_subject'),
    path('api/curriculum/details/<int:student_id>/', views.get_adviser_student_details, name='get_student_details'),
    path('api/enrollment/generate-code/', views.generate_enrollment_code, name='generate_enrollment_code'),
    path('api/enrollment/request-subject/', views.request_subject_enrollment, name='request_subject_enrollment'),
    path('api/enrollment/process/', views.process_enrollment_request, name='process_enrollment_request'),
    # ── Staff Messaging & Notifications ───────────────────────
    path('api/staff/contacts/', views.staff_get_contacts, name='staff_get_contacts'),
    path('api/staff/conversation/<int:contact_id>/', views.staff_get_conversation, name='staff_get_conversation'),
    path('api/staff/send/', views.staff_send_message, name='staff_send_message'),
    path('api/notifications/system/', views.api_get_notifications, name='api_get_notifications'),
    path('api/analytics/sync/', views.api_analytics_sync, name='api_analytics_sync'),
    path('api/admin/active-sessions/', views.api_get_active_sessions, name='api_get_active_sessions'),
    path('api/admin/send-official-notice/', views.api_send_official_notice, name='api_send_official_notice'),

    path('api/notifications/mark-read/', views.api_mark_notifications_read, name='api_mark_notifications_read'),
    path('api/chatbot/', views.chatbot_api, name='chatbot_api'),
]
