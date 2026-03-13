from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    ENROLLMENT_STATUS = (
        ('not_enrolled', 'Not Enrolled'),
        ('pending', 'Pending Approval'),
        ('enrolled', 'Enrolled'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=50, blank=True, null=True)
    institution = models.CharField(max_length=255, blank=True, null=True)
    program = models.CharField(max_length=255, blank=True, null=True)
    year_level = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, default='student') # student, adviser, admin
    
    # New fields for enrollment workflow
    enrollment_status = models.CharField(max_length=20, choices=ENROLLMENT_STATUS, default='not_enrolled')
    curriculum_code = models.CharField(max_length=50, blank=True, null=True)
    
    def __str__(self):
        return self.user.username

class Course(models.Model):
    title = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    units = models.IntegerField(default=3)
    schedule = models.CharField(max_length=100)
    instructor = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.code} - {self.title}"

class Enrollment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    grade = models.CharField(max_length=10, blank=True, null=True)
    
    def __str__(self):
        return f"{self.student.username} - {self.course.code}"

class FormSubmission(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forms')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    adviser_notes = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.student.username} - {self.title} ({self.status})"

class Appointment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='student_appointments')
    adviser = models.ForeignKey(User, on_delete=models.CASCADE, related_name='adviser_appointments', null=True, blank=True)
    date_time = models.DateTimeField()
    purpose = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    adviser_notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        if self.adviser:
            return f"{self.student.username} with {self.adviser.username} at {self.date_time}"
        return f"{self.student.username} at {self.date_time}"

class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    def __str__(self):
        return f"From {self.sender.username} to {self.receiver.username} at {self.sent_at}"
