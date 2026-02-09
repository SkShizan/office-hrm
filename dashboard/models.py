from django.db import models
from accounts.models import User, Company

# ==========================================
# 1. LEAVE QUOTA (BALANCE)
# ==========================================
class LeaveBalance(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='leave_balance')
    casual_leave = models.PositiveIntegerField(default=0)
    sick_leave = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} - CL:{self.casual_leave}, SL:{self.sick_leave}"


# ==========================================
# 2. LEAVE REQUESTS
# ==========================================
class LeaveRequest(models.Model):
    LEAVE_TYPES = (
        ('Casual', 'Casual Leave'),
        ('Sick', 'Sick Leave'),
        ('Notify', 'Notify Only (No Approval Needed)'), # <--- ADDED THIS
    )
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests')
    
    # Tagging multiple people (Team Leader, Manager, HR)
    approvers = models.ManyToManyField(User, related_name='incoming_leave_requests')
    
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES) # Increased max_length
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    applied_on = models.DateTimeField(auto_now_add=True)
    
    # Who actually clicked 'Approve/Reject'
    action_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leaves_actioned')

    @property
    def days_requested(self):
        delta = self.end_date - self.start_date
        return delta.days + 1

    def __str__(self):
        return f"{self.user.username} - {self.leave_type} ({self.status})"


# ==========================================
# 3. ATTENDANCE & CALENDAR
# ==========================================
class AttendanceRecord(models.Model):
    STATUS_CHOICES = (
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('WFH', 'Work From Home'),
        ('Leave', 'On Leave'),
        ('2nd Late', '2nd Late (Half Day)'), # <--- ADDED
        ('3rd Late', '3rd Late (Full Day)'), # <--- ADDED
        ('Holiday', 'Holiday'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Present')
    
    # Store exact login time
    login_time = models.TimeField(null=True, blank=True)
    
    # Who marked/edited this record
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='marked_attendance')

    class Meta:
        unique_together = ('user', 'date')

    def __str__(self):
        return f"{self.user.username} - {self.date} - {self.status}"


# ==========================================
# 4. HOLIDAYS
# ==========================================
class PublicHoliday(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    date = models.DateField()
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} - {self.date}"


# ==========================================
# 5. NOTIFICATIONS (NEW)
# ==========================================
class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications')
    title = models.CharField(max_length=100)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notif for {self.recipient.username}: {self.title}"



class TrackSheet(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='track_sheets')
    date = models.DateField()
    
    # Work Log
    work_done = models.TextField(null=True, blank=True)
    
    # Task Assignment
    assigned_task = models.TextField(null=True, blank=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # NEW: Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')

    class Meta:
        unique_together = ('user', 'date')