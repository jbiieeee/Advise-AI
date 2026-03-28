from django.db import models
from django.contrib.auth.models import User
import uuid

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
    assigned_adviser = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='assigned_students', null=True, blank=True)
    
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


# ─────────────────────────────────────────────────────────────
#  CURRICULUM & ENROLLMENT CODE SYSTEM
# ─────────────────────────────────────────────────────────────

class CurriculumSubject(models.Model):
    """Master list of subjects in the BSIT curriculum."""
    SEMESTER_CHOICES = (
        ('1st', '1st Semester'),
        ('2nd', '2nd Semester'),
        ('Summer', 'Summer'),
    )
    code = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=200)
    units = models.IntegerField(default=3)
    year_level = models.IntegerField()          # 1, 2, 3, 4
    semester = models.CharField(max_length=10, choices=SEMESTER_CHOICES)
    prerequisite_codes = models.CharField(
        max_length=500, blank=True,
        help_text='Comma-separated subject codes that must be passed first'
    )
    track = models.CharField(
        max_length=50, blank=True,
        help_text='IT elective track (Track 1 / Track 2 / Track 3) or blank for core subjects'
    )
    subject_type = models.CharField(
        max_length=20, default='core',
        help_text='core / it_elective / pe / nstp / professional_elective / ge'
    )

    class Meta:
        ordering = ['year_level', 'semester', 'code']

    def __str__(self):
        return f"{self.code} – {self.title}"


class StudentCurriculum(models.Model):
    """Tracks each student's progress on every curriculum subject."""
    STATUS_CHOICES = (
        ('not_taken', 'Not Yet Taken'),
        ('in_progress', 'In Progress'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
    )
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='curriculum_records')
    subject = models.ForeignKey(CurriculumSubject, on_delete=models.CASCADE, related_name='student_records')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_taken')
    grade = models.CharField(max_length=10, blank=True, null=True)
    term_taken = models.CharField(max_length=50, blank=True, null=True, help_text='e.g. AY 2025-2026 1st Sem')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'subject')

    def __str__(self):
        return f"{self.student.username} – {self.subject.code} ({self.status})"


class EnrollmentCode(models.Model):
    """Single-use enrollment code generated by an adviser for a specific student."""
    code = models.CharField(max_length=20, unique=True)
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollment_codes')
    adviser = models.ForeignKey(User, on_delete=models.CASCADE, related_name='generated_codes')
    approved_subjects = models.ManyToManyField(CurriculumSubject, related_name='enrollment_codes')
    term_label = models.CharField(max_length=100, default='', help_text='e.g. AY 2025-2026 2nd Sem')
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.code:
            import random
            import string
            length = 12
            chars = string.ascii_uppercase + string.digits
            # Generate a truly random 12-char alphanumeric code: XXXX-XXXX-XXXX
            raw = ''.join(random.choice(chars) for _ in range(length))
            self.code = f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Code {self.code} for {self.student.username} ({'used' if self.used else 'active'})"


class TermEnrollment(models.Model):
    """Subjects a student is enrolled in for a specific term, created upon code redemption."""
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('declined', 'Declined'),
    )
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='term_enrollments')
    subject = models.ForeignKey(CurriculumSubject, on_delete=models.CASCADE, related_name='term_enrollments')
    enrollment_code = models.ForeignKey(EnrollmentCode, on_delete=models.SET_NULL, null=True, related_name='term_enrollments')
    term_label = models.CharField(max_length=100)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    class Meta:
        unique_together = ('student', 'subject', 'term_label')

    def __str__(self):
        return f"{self.student.username} – {self.subject.code} ({self.term_label})"
