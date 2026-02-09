import random
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.core.mail import send_mail, get_connection
from .forms import EmployeeSignupForm 
from .models import User, Company  # <--- THIS IMPORT WAS MISSING

def signup(request):
    if request.method == 'POST':
        form = EmployeeSignupForm(request.POST)
        
        # 1. Check if email exists (Handle retry logic for inactive users)
        email = request.POST.get('email')
        
        # Use User model safely now
        existing_user = User.objects.filter(email=email).first()

        if existing_user:
            if existing_user.is_active:
                messages.error(request, "Account already exists. Please login.")
                return redirect('login')
            else:
                # RETRY LOGIC: User failed verification before. Resend OTP.
                otp = str(random.randint(100000, 999999))
                existing_user.otp = otp
                
                # Update info if valid form (optional)
                if form.is_valid():
                    existing_user.username = form.cleaned_data['username']
                    # We don't change password here to keep it simple
                
                existing_user.save()
                
                send_otp_email(existing_user, otp)
                request.session['verify_email'] = email
                messages.info(request, "Account inactive. A new OTP has been sent.")
                return redirect('verify_otp')

        if form.is_valid():
            # 2. New User Signup
            user = form.save(commit=False)
            user.is_active = False  # Deactivate until verified
            user.is_approved = False 
            user.role = 'Employee'
            
            otp = str(random.randint(100000, 999999))
            user.otp = otp
            user.save()
            
            send_otp_email(user, otp)
            
            request.session['verify_email'] = user.email
            messages.success(request, "Signup successful! OTP sent to your email.")
            return redirect('verify_otp')
            
    else:
        form = EmployeeSignupForm()
        
    return render(request, 'registration/signup.html', {'form': form})

def verify_otp(request):
    email = request.session.get('verify_email')
    
    if not email:
        messages.error(request, "Session expired. Please sign up again.")
        return redirect('signup')
        
    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        try:
            user = User.objects.get(email=email)
            if user.otp == entered_otp:
                # SUCCESS
                user.is_active = True
                user.otp = None # Clear OTP
                user.save()
                
                del request.session['verify_email']
                messages.success(request, "Email verified! Please wait for HR approval to login.")
                return redirect('login')
            else:
                messages.error(request, "Invalid OTP. Please try again.")
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect('signup')

    return render(request, 'registration/verify_otp.html', {'email': email})

# --- HELPER: Send Email via Company SMTP ---
def send_otp_email(user, otp):
    # Use the user's selected company SMTP
    company = user.company
    
    connection = None
    from_email = 'noreply@hrms.com'
    
    if company and company.smtp_email:
        try:
            connection = get_connection(
                host=company.smtp_server,
                port=company.smtp_port,
                username=company.smtp_email,
                password=company.smtp_password,
                use_tls=True
            )
            from_email = company.smtp_email
        except Exception as e:
            print(f"SMTP Error: {e}")

    subject = "Verify Your Employee Account"
    message = f"Hello {user.username},\n\nYour OTP is: {otp}\n\nEnter this code to verify your email address."
    
    try:
        send_mail(subject, message, from_email, [user.email], connection=connection, fail_silently=False)
    except Exception as e:
        print(f"Mail Send Error: {e}")