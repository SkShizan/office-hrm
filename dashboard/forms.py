from django import forms
from django.db.models import Q
from .models import LeaveRequest, LeaveBalance
from accounts.models import User

class LeaveApplicationForm(forms.ModelForm):
    approvers = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(), 
        widget=forms.CheckboxSelectMultiple,
        label="Select Approvers (Manager / Team Leaders)"
    )

    class Meta:
        model = LeaveRequest
        fields = ['approvers', 'leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # LOGIC: 
        # Combine "My Direct Boss" + "All Leaders in My Team"
        
        # 1. Start with an empty filter
        criteria = Q(pk__in=[]) 
        
        # 2. Add Direct Reporting Manager (if set)
        if user.reports_to:
            criteria |= Q(pk=user.reports_to.id)
            
        # 3. Add Team Leaders & Managers from the SAME Team
        if user.team:
            criteria |= (Q(team=user.team) & Q(role__in=['TL', 'Manager']))

        # 4. Execute Query
        # Ensure we filter by Company and exclude the user themselves (if they are a TL)
        approver_options = User.objects.filter(criteria, company=user.company).exclude(id=user.id)
        
        # 5. Fallback: If list is empty (No Boss & No Team Leaders found), show HR/Directors
        if not approver_options.exists():
            approver_options = User.objects.filter(
                company=user.company, 
                role__in=['HR', 'Director']
            ).exclude(id=user.id)
            self.fields['approvers'].label = "No Team Leaders found. Tag HR/Director:"

        # 6. Set the final queryset
        self.fields['approvers'].queryset = approver_options
        
        # Auto-select the direct boss if they exist (User can uncheck if needed)
        if user.reports_to:
            self.fields['approvers'].initial = [user.reports_to]

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        end = cleaned_data.get("end_date")

        if start and end and end < start:
            raise forms.ValidationError("End date cannot be before start date.")
        return cleaned_data

class LeaveAllocationForm(forms.ModelForm):
    class Meta:
        model = LeaveBalance
        fields = ['casual_leave', 'sick_leave']