import calendar
from datetime import date, datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction 
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from accounts.models import User
from .models import LeaveRequest, LeaveBalance, AttendanceRecord, PublicHoliday
from .forms import LeaveApplicationForm, LeaveAllocationForm
from accounts.models import Team # Import Team
from django.db.models import Q

# ==========================================
# 1. CORE DASHBOARD ROUTING
# ==========================================

@login_required
def dashboard(request):
    """
    Traffic controller: Sends user to the correct dashboard based on role/status.
    """
    user = request.user
    
    # 1. If not approved, show pending page
    if not user.is_approved:
        return render(request, 'dashboard/pending.html')
    
    # 2. If HR, go to HR Dashboard
    if user.role == 'HR':
        return redirect('hr_dashboard')
    
    # 3. If Employee (Manager, TL, or Standard), go to Employee Dashboard
    else:
        # LOGIC: Fetch 'My Team' if I am a Manager or TL
        my_team_members = User.objects.none()
        
        if user.role in ['Manager', 'TL']:
            # Fetch users who Report to me OR are in my Team (excluding myself)
            my_team_members = User.objects.filter(
                Q(reports_to=user) | Q(team=user.team)
            ).filter(is_approved=True).exclude(id=user.id).distinct()

        return render(request, 'dashboard/employee_dashboard.html', {
            'my_team_members': my_team_members
        })
# ==========================================
# 2. HR MANAGEMENT VIEWS
# ==========================================

@login_required
def hr_dashboard(request):
    if request.user.role != 'HR':
        return redirect('dashboard')
    
    pending_users = User.objects.filter(company=request.user.company, is_approved=False)
    active_users = User.objects.filter(company=request.user.company, is_approved=True)
    teams = Team.objects.filter(company=request.user.company) # <--- Add this

    return render(request, 'dashboard/hr_dashboard.html', {
        'pending_users': pending_users,
        'active_users': active_users,
        'teams': teams, # <--- Pass it here
    })

@login_required
def approve_employee(request, user_id):
    if request.user.role != 'HR':
        return redirect('dashboard')
        
    employee = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        # 1. Basic Details
        employee.designation = request.POST.get('designation')
        employee.section = request.POST.get('section') # Frontside/Backside
        employee.role = request.POST.get('role')       # Manager/TL/Employee
        
        # 2. Team Assignment
        team_id = request.POST.get('team_id')
        if team_id:
            employee.team = Team.objects.get(id=team_id)
            
        # 3. Reporting Manager Assignment
        reports_to_id = request.POST.get('reports_to')
        if reports_to_id:
            employee.reports_to = User.objects.get(id=reports_to_id)
        else:
            employee.reports_to = None
            
        employee.is_approved = True
        employee.save()
        
        # Auto-create leave balance
        LeaveBalance.objects.get_or_create(user=employee)
        
        messages.success(request, f"{employee.username} onboarded to {employee.section} - {employee.team.name}.")
        return redirect('hr_dashboard')
        
    return redirect('hr_dashboard')

@login_required
def edit_employee(request, user_id):
    if request.user.role != 'HR':
        return redirect('dashboard')
    
    employee = get_object_or_404(User, id=user_id, company=request.user.company)
    
    # --- FIX: Fetch the teams for the dropdown ---
    teams = Team.objects.filter(company=request.user.company)
    # ---------------------------------------------
    
    # Get all potential managers (exclude the person being edited)
    active_users = User.objects.filter(
        company=request.user.company, 
        is_approved=True
    ).exclude(id=employee.id)

    if request.method == 'POST':
        employee.designation = request.POST.get('designation')
        employee.section = request.POST.get('section') # Update Section
        
        # Update Team
        team_id = request.POST.get('team_id')
        if team_id:
            employee.team = Team.objects.get(id=team_id)
        else:
            employee.team = None # Allow unassigning team
        
        # SAFETY: Only allow changing Role if you are NOT editing yourself
        if employee.id != request.user.id:
            role_input = request.POST.get('role') 
            if role_input:
                employee.role = role_input 

        # Handle Reporting Manager
        reports_to_id = request.POST.get('reports_to')
        if reports_to_id:
            employee.reports_to = User.objects.get(id=reports_to_id)
        else:
            employee.reports_to = None
            
        employee.save()
        messages.success(request, f"Profile for {employee.username} updated.")
        return redirect('hr_dashboard')

    return render(request, 'dashboard/edit_employee.html', {
        'employee': employee,
        'active_users': active_users,
        'teams': teams # <--- PASS TEAMS HERE
    })

# ==========================================
# 3. LEAVE MANAGEMENT VIEWS
# ==========================================

@login_required
def apply_leave(request):
    balance, created = LeaveBalance.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        # Pass 'user' to form to filter approvers correctly
        form = LeaveApplicationForm(request.user, request.POST) 
        if form.is_valid():
            leave = form.save(commit=False)
            leave.user = request.user
            
            # Balance Check
            days = leave.days_requested
            if leave.leave_type == 'Casual' and balance.casual_leave < days:
                messages.error(request, f"Insufficient Casual Leaves.")
                return redirect('apply_leave')
            elif leave.leave_type == 'Sick' and balance.sick_leave < days:
                messages.error(request, f"Insufficient Sick Leaves.")
                return redirect('apply_leave')

            leave.save()
            
            # Save ManyToMany Data (Approvers)
            form.save_m2m() 
            
            # EMAIL NOTIFICATION
            approver_emails = [u.email for u in leave.approvers.all()]
            send_mail(
                subject=f'Leave Request: {request.user.username}',
                message=f'{request.user.username} has requested leave from {leave.start_date} to {leave.end_date}.\nReason: {leave.reason}\n\nPlease login to approve.',
                from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@hrms.com',
                recipient_list=approver_emails,
                fail_silently=True
            )
            
            messages.success(request, "Leave request sent to tagged approvers.")
            return redirect('dashboard')
    else:
        form = LeaveApplicationForm(user=request.user) 
    
    return render(request, 'dashboard/apply_leave.html', {'form': form, 'balance': balance})


@login_required
def manage_quota(request, user_id):
    if request.user.role != 'HR': return redirect('dashboard')
    
    employee = get_object_or_404(User, id=user_id)
    balance, created = LeaveBalance.objects.get_or_create(user=employee)
    
    if request.method == 'POST':
        form = LeaveAllocationForm(request.POST, instance=balance)
        if form.is_valid():
            form.save()
            messages.success(request, f"Leave quota updated for {employee.username}")
            return redirect('hr_dashboard')
    else:
        form = LeaveAllocationForm(instance=balance)
    
    return render(request, 'dashboard/manage_quota.html', {'form': form, 'employee': employee})


@login_required
def leave_requests_list(request):
    # Show requests where 'approvers' contains ME and status is Pending
    my_approvals = LeaveRequest.objects.filter(
        approvers=request.user, 
        status='Pending'
    ).order_by('-applied_on').distinct()
    
    return render(request, 'dashboard/leave_requests_list.html', {'pending_leaves': my_approvals})


@login_required
@transaction.atomic
def action_leave(request, leave_id, action):
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    
    # Security: Ensure the person acting was actually tagged
    if request.user not in leave.approvers.all():
        messages.error(request, "You are not authorized to approve this leave.")
        return redirect('leave_requests_list')

    balance = get_object_or_404(LeaveBalance, user=leave.user)
    days = leave.days_requested

    if action == 'approve':
        # 1. Deduct Balance
        if leave.leave_type == 'Casual':
            if balance.casual_leave >= days:
                balance.casual_leave -= days
                balance.save()
            else:
                messages.error(request, "User has insufficient balance.")
                return redirect('leave_requests_list')
        elif leave.leave_type == 'Sick':
            if balance.sick_leave >= days:
                balance.sick_leave -= days
                balance.save()
            else:
                messages.error(request, "User has insufficient balance.")
                return redirect('leave_requests_list')

        # 2. Auto-Update Attendance Calendar
        current_date = leave.start_date
        while current_date <= leave.end_date:
            AttendanceRecord.objects.update_or_create(
                user=leave.user,
                date=current_date,
                defaults={
                    'status': 'Leave',
                    'marked_by': request.user
                }
            )
            current_date += timedelta(days=1)
        
        leave.status = 'Approved'
        messages.success(request, "Leave Approved and Calendar Updated.")

    elif action == 'reject':
        leave.status = 'Rejected'
        messages.warning(request, "Leave Rejected.")

    leave.action_by = request.user
    leave.save()
    
    return redirect('leave_requests_list')


# ==========================================
# 4. ATTENDANCE & CALENDAR VIEWS
# ==========================================

@login_required
def view_attendance(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    
    # ==========================================
    # 1. SMART PERMISSION CHECK
    # ==========================================
    is_manager = False
    
    # Rule 1: HR can edit everyone
    if request.user.role == 'HR':
        is_manager = True
        
    # Rule 2: The Direct "Reports To" Manager can edit their subordinate
    elif target_user.reports_to == request.user:
        is_manager = True
        
    # Rule 3: Team Leader/Manager fallback
    # If I am a Manager/TL in the SAME team, and the target is an Employee
    elif target_user.team and (target_user.team == request.user.team):
        if request.user.role in ['Manager', 'TL'] and target_user.role == 'Employee':
            is_manager = True
    
    # SECURITY: If not a manager and not viewing own profile -> Kick out
    if not is_manager and request.user != target_user:
         messages.error(request, "Access Denied. You are not the manager of this user.")
         return redirect('dashboard')

    # ==========================================
    # 2. DATE & CALENDAR LOGIC
    # ==========================================
    today = date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except ValueError:
        year, month = today.year, today.month
    
    first_weekday, num_days = calendar.monthrange(year, month)
    start_index = (first_weekday + 1) % 7 

    # ==========================================
    # 3. MANAGER ACTIONS (EDIT ATTENDANCE)
    # ==========================================
    if request.method == 'POST' and is_manager:
        date_str = request.POST.get('date')
        new_status = request.POST.get('status')
        time_str = request.POST.get('login_time')
        
        new_time = None
        if time_str:
            try:
                new_time = datetime.strptime(time_str, '%H:%M').time()
            except ValueError:
                pass 
        
        AttendanceRecord.objects.update_or_create(
            user=target_user,
            date=date_str,
            defaults={
                'status': new_status, 
                'login_time': new_time, 
                'marked_by': request.user
            }
        )
        messages.success(request, f"Attendance updated for {date_str}")
        return redirect(f"{request.path}?year={year}&month={month}")

    # ==========================================
    # 4. FETCH DATA
    # ==========================================
    records = AttendanceRecord.objects.filter(
        user=target_user,
        date__year=year,
        date__month=month
    )
    attendance_map = {record.date: record for record in records}

    try:
        holiday_qs = PublicHoliday.objects.filter(
            company=target_user.company,
            date__year=year,
            date__month=month
        )
        holiday_dates = {h.date for h in holiday_qs}
    except NameError:
        holiday_dates = set()

    month_days = []
    
    stats = {
        'absent': 0, 'leave': 0, 'wfh': 0, 'present': 0, 
        'holiday': 0, 
        'total_days': num_days
    }
    
    for _ in range(start_index):
        month_days.append(None)

    for day in range(1, num_days + 1):
        current_date = date(year, month, day)
        record = attendance_map.get(current_date)
        login_time = record.login_time if record else None
        
        if record:
            status = record.status
        else:
            if current_date in holiday_dates:
                status = 'Holiday'
            else:
                status = 'Present'
        
        # Stats
        if status == 'Absent': stats['absent'] += 1
        elif status == 'Leave': 
            stats['leave'] += 1
            stats['present'] += 1
        elif status == 'WFH': 
            stats['wfh'] += 1
            stats['present'] += 1
        elif status == 'Present': 
            stats['present'] += 1
        elif status == 'Holiday':
            stats['holiday'] += 1
            
        month_days.append({
            'day': day,
            'date': current_date,
            'status': status,
            'login_time': login_time,
            'day_name': current_date.strftime("%A")
        })

    return render(request, 'dashboard/view_attendance.html', {
        'target_user': target_user,
        'month_days': month_days,
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'is_manager': is_manager, # Passes True if HR, Reports_To, or TL
        'stats': stats
    })


# dashboard/views.py

@login_required
def delete_employee(request, user_id):
    # 1. Permission Check: Only HR
    if request.user.role != 'HR':
        messages.error(request, "Access Denied.")
        return redirect('dashboard')

    # 2. Fetch User: Must be in the same company
    employee = get_object_or_404(User, id=user_id, company=request.user.company)

    # 3. Safety Check: Prevent Self-Deletion
    if employee.id == request.user.id:
        messages.error(request, "You cannot delete your own account.")
        return redirect('hr_dashboard')

    # 4. Perform Deletion
    # This will cascade delete their Leaves, Attendance, and Balance automatically.
    username = employee.username
    employee.delete()
    
    messages.success(request, f"Employee '{username}' has been permanently deleted.")
    return redirect('hr_dashboard')



@login_required
def manage_teams(request):
    if request.user.role != 'HR':
        return redirect('dashboard')
    
    if request.method == 'POST':
        team_name = request.POST.get('team_name')
        if team_name:
            Team.objects.get_or_create(company=request.user.company, name=team_name)
            messages.success(request, f"Team '{team_name}' created.")
    
    teams = Team.objects.filter(company=request.user.company)
    return render(request, 'dashboard/manage_teams.html', {'teams': teams})