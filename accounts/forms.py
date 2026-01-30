from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Company

class SignUpForm(UserCreationForm):
    # Replace HR Email input with a Company Dropdown
    company = forms.ModelChoiceField(
        queryset=Company.objects.all(),
        required=True,
        label="Select Your Company",
        empty_label="-- Choose Company --"
    )
    
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        # We allow the user to select the company directly here
        fields = ('username', 'email', 'company')

    # No custom save method is needed here because:
    # 1. 'company' is in 'fields', so Django saves the relationship automatically.
    # 2. 'role' and 'is_approved' are set in views.py (as 'Employee' and False).