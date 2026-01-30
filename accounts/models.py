from django.db import models
from django.contrib.auth.models import AbstractUser

class Company(models.Model):
    name = models.CharField(max_length=100)
    hr_email = models.EmailField(unique=True)

    def __str__(self):
        return self.name

class Team(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=50) # e.g. "Alpha", "Beta"
    
    class Meta:
        unique_together = ('company', 'name')

    def __str__(self):
        return self.name

class User(AbstractUser):
    # 1. Sections
    SECTION_CHOICES = (
        ('Frontside', 'Frontside'),
        ('Backside', 'Backside'),
        ('Management', 'Management'), 
    )
    
    # 2. Roles (Strict Hierarchy)
    ROLE_CHOICES = (
        ('Director', 'Director'),
        ('Manager', 'Manager'),
        ('TL', 'Team Leader'),
        ('Employee', 'Employee'),
        ('HR', 'HR'),
    )

    # Links
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    
    # Attributes
    section = models.CharField(max_length=20, choices=SECTION_CHOICES, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Employee')
    designation = models.CharField(max_length=100, null=True, blank=True)
    
    is_approved = models.BooleanField(default=False)
    
    # Reporting Manager
    reports_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subordinates')

    def __str__(self):
        return f"{self.username} ({self.role})"