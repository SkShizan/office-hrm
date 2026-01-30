from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import SignUpForm # <--- Updated import
from .models import Company

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            
            # FORCE SECURITY SETTINGS:
            user.role = 'Employee'      # Public signups are ALWAYS employees
            user.is_approved = False    # Public signups must wait for approval
            
            # These are set by HR later via Dashboard
            user.section = None         
            user.team = None            
            
            user.save()
            
            login(request, user)
            return redirect('dashboard')
    else:
        form = SignUpForm()
    
    return render(request, 'registration/signup.html', {'form': form})