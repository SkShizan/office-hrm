import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal 
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction 
from django.contrib import messages
from django.core.mail import send_mail, get_connection
from django.conf import settings
from django.db.models import Q
from accounts.models import User, Team
from .models import LeaveRequest, LeaveBalance, AttendanceRecord, PublicHoliday, Notification, TrackSheet, TaskItem, WorkItem
from .forms import LeaveApplicationForm, LeaveAllocationForm, SMTPSettingsForm

# ==========================================
# 1. CORE DASHBOARD ROUTING
# ==========================================

# In dashboard/views.py

@login_required
def dashboard(request):
    user = request.user
    
    if not user.is_approved:
        return render(request, 'dashboard/pending.html')
    
    if user.role == 'HR':
        return redirect('hr_dashboard')
    
    else:
        # 1. My Team
        my_team_members = User.objects.none()
        if user.role in ['Manager', 'TL']:
            my_team_members = User.objects.filter(
                Q(reports_to=user) | Q(team=user.team)
            ).filter(is_approved=True).exclude(id=user.id).distinct()

        # 2. Fetch Teams
        teams = Team.objects.filter(company=user.company)

        # 3. All Colleagues
        all_colleagues = User.objects.filter(
            company=user.company, 
            is_approved=True
        ).exclude(id=user.id).select_related('team')

        # 4. Tasks I Assigned (FIXED: Now querying TaskItem)
        tasks_i_assigned = TaskItem.objects.filter(
            assigned_by=user,
            sender_archived=False
        ).select_related('track_sheet', 'track_sheet__user').order_by('-track_sheet__date')[:10]

        return render(request, 'dashboard/employee_dashboard.html', {
            'my_team_members': my_team_members,
            'teams': teams,
            'all_colleagues': all_colleagues,
            'tasks_i_assigned': tasks_i_assigned
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
    teams = Team.objects.filter(company=request.user.company)

    return render(request, 'dashboard/hr_dashboard.html', {
        'pending_users': pending_users,
        'active_users': active_users,
        'teams': teams,
    })

@login_required
def approve_employee(request, user_id):
    if request.user.role != 'HR':
        return redirect('dashboard')
        
    employee = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        employee.designation = request.POST.get('designation')
        employee.section = request.POST.get('section')
        employee.role = request.POST.get('role')
        
        team_id = request.POST.get('team_id')
        if team_id:
            employee.team = Team.objects.get(id=team_id)
            
        reports_to_id = request.POST.get('reports_to')
        if reports_to_id:
            employee.reports_to = User.objects.get(id=reports_to_id)
        else:
            employee.reports_to = None
            
        employee.is_approved = True
        employee.save()
        
        LeaveBalance.objects.get_or_create(user=employee)
        
        messages.success(request, f"{employee.username} onboarded successfully.")
        return redirect('hr_dashboard')
        
    return redirect('hr_dashboard')

@login_required
def edit_employee(request, user_id):
    if request.user.role != 'HR':
        return redirect('dashboard')
    
    employee = get_object_or_404(User, id=user_id, company=request.user.company)
    teams = Team.objects.filter(company=request.user.company)
    
    active_users = User.objects.filter(
        company=request.user.company, 
        is_approved=True
    ).exclude(id=employee.id)

    if request.method == 'POST':
        employee.designation = request.POST.get('designation')
        employee.section = request.POST.get('section')
        
        team_id = request.POST.get('team_id')
        if team_id:
            employee.team = Team.objects.get(id=team_id)
        else:
            employee.team = None
        
        if employee.id != request.user.id:
            role_input = request.POST.get('role') 
            if role_input:
                employee.role = role_input 

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
        'teams': teams
    })

@login_required
def delete_employee(request, user_id):
    if request.user.role != 'HR':
        messages.error(request, "Access Denied.")
        return redirect('dashboard')

    employee = get_object_or_404(User, id=user_id, company=request.user.company)

    if employee.id == request.user.id:
        messages.error(request, "You cannot delete your own account.")
        return redirect('hr_dashboard')

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

# ==========================================
# 3. LEAVE MANAGEMENT (UPDATED WITH NOTIFY & SMTP)
# ==========================================

@login_required
def apply_leave(request):
    balance, created = LeaveBalance.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = LeaveApplicationForm(request.user, request.POST) 
        if form.is_valid():
            leave = form.save(commit=False)
            leave.user = request.user
            
            # --- LOGIC 1: BALANCE CHECK (Skip for 'Notify') ---
            if leave.leave_type != 'Notify':
                days = leave.days_requested
                if leave.leave_type == 'Casual' and balance.casual_leave < days:
                    messages.error(request, f"Insufficient Casual Leaves.")
                    return redirect('apply_leave')
                elif leave.leave_type == 'Sick' and balance.sick_leave < days:
                    messages.error(request, f"Insufficient Sick Leaves.")
                    return redirect('apply_leave')
            else:
                # Notifications are auto-approved
                leave.status = 'Approved' 

            leave.save()
            form.save_m2m() # Saves the approvers
            
            # --- LOGIC 2: SEND EMAIL VIA DYNAMIC SMTP ---
            company = request.user.company
            recipients = leave.approvers.all()
            recipient_emails = [u.email for u in recipients]
            
            connection = None
            sender_email = settings.DEFAULT_FROM_EMAIL
            
            if company.smtp_email and company.smtp_password:
                try:
                    connection = get_connection(
                        host=company.smtp_server,
                        port=company.smtp_port,
                        username=company.smtp_email,
                        password=company.smtp_password,
                        use_tls=True
                    )
                    sender_email = company.smtp_email
                except Exception as e:
                    print(f"SMTP Connection Error: {e}")

            subject = f"Leave Notification: {request.user.username}" if leave.leave_type == 'Notify' else f"Leave Request: {request.user.username}"
            email_msg = f"User: {request.user.username}\nType: {leave.leave_type}\nDate: {leave.start_date} to {leave.end_date}\nReason: {leave.reason}"
            
            if recipient_emails:
                send_mail(
                    subject=subject,
                    message=email_msg,
                    from_email=sender_email,
                    recipient_list=recipient_emails,
                    connection=connection, 
                    fail_silently=True
                )
            
            # --- LOGIC 3: CREATE PERSISTENT APP NOTIFICATIONS ---
            for receiver in recipients:
                Notification.objects.create(
                    recipient=receiver,
                    sender=request.user,
                    title=subject,
                    message=email_msg
                )

            if leave.leave_type == 'Notify':
                messages.success(request, "Notification sent successfully.")
            else:
                messages.success(request, "Leave request sent to approvers.")
                
            return redirect('dashboard')
    else:
        form = LeaveApplicationForm(user=request.user) 
    
    return render(request, 'dashboard/apply_leave.html', {'form': form, 'balance': balance})

@login_required
def manage_quota(request, user_id):
    # 1. Fetch the employee first
    employee = get_object_or_404(User, id=user_id)
    
    # 2. Define Permissions
    is_hr = (request.user.role == 'HR')
    is_manager = (employee.reports_to == request.user)

    # 3. Check Access (Must be HR OR the Direct Manager)
    if not (is_hr or is_manager):
        messages.error(request, "Access Denied. You can only manage quota for your direct reports.")
        return redirect('dashboard')
    
    # 4. Get or Create Balance
    balance, created = LeaveBalance.objects.get_or_create(user=employee)
    
    if request.method == 'POST':
        form = LeaveAllocationForm(request.POST, instance=balance)
        if form.is_valid():
            form.save()
            messages.success(request, f"Leave quota updated for {employee.username}")
            
            # 5. Smart Redirect
            if is_hr:
                return redirect('hr_dashboard')
            else:
                return redirect('dashboard') # Managers go back to employee dashboard
    else:
        form = LeaveAllocationForm(instance=balance)
    
    return render(request, 'dashboard/manage_quota.html', {'form': form, 'employee': employee})

@login_required
def leave_requests_list(request):
    my_approvals = LeaveRequest.objects.filter(
        approvers=request.user, 
        status='Pending'
    ).order_by('-applied_on').distinct()
    
    return render(request, 'dashboard/leave_requests_list.html', {'pending_leaves': my_approvals})

@login_required
@transaction.atomic
def action_leave(request, leave_id, action):
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    
    if request.user not in leave.approvers.all():
        messages.error(request, "You are not authorized to approve this leave.")
        return redirect('leave_requests_list')

    balance = get_object_or_404(LeaveBalance, user=leave.user)
    days = leave.days_requested

    if action == 'approve':
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
# 4. ATTENDANCE & PAYROLL VIEWS
# ==========================================

@login_required
def view_attendance(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    
    is_manager = False
    if request.user.role == 'HR':
        is_manager = True
    elif target_user.reports_to == request.user:
        is_manager = True
    elif target_user.team and (target_user.team == request.user.team):
        if request.user.role in ['Manager', 'TL'] and target_user.role == 'Employee':
            is_manager = True
    
    if not is_manager and request.user != target_user:
         messages.error(request, "Access Denied.")
         return redirect('dashboard')

    today = date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except ValueError:
        year, month = today.year, today.month
    
    first_weekday, num_days = calendar.monthrange(year, month)
    start_index = (first_weekday + 1) % 7 

    # --- MANAGER ACTIONS ---
    if request.method == 'POST' and is_manager:
        if 'update_salary' in request.POST:
            target_user.monthly_salary = Decimal(request.POST.get('monthly_salary', 0))
            target_user.esi_percentage = Decimal(request.POST.get('esi_percentage', 0))
            target_user.professional_tax = Decimal(request.POST.get('professional_tax', 0))
            target_user.save()
            messages.success(request, "Payroll details updated.")

        elif 'date' in request.POST:
            date_str = request.POST.get('date')
            new_status = request.POST.get('status')
            time_str = request.POST.get('login_time')
            
            # Special Rule: 3rd Late removes previous 2nd Late
            if new_status == '3rd Late':
                current_date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                prev_late = AttendanceRecord.objects.filter(
                    user=target_user,
                    date__year=year,
                    date__month=month,
                    status='2nd Late',
                    date__lt=current_date_obj
                ).order_by('-date').first()

                if prev_late:
                    prev_late.status = 'Present'
                    prev_late.save()
                    messages.info(request, f"Rule Applied: '2nd Late' on {prev_late.date} reset to 'Present' due to new '3rd Late'.")

            new_time = None
            if time_str:
                try: new_time = datetime.strptime(time_str, '%H:%M').time()
                except ValueError: pass 
            
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

    # --- FETCH DATA ---
    records = AttendanceRecord.objects.filter(user=target_user, date__year=year, date__month=month)
    attendance_map = {record.date: record for record in records}
    
    try:
        holiday_qs = PublicHoliday.objects.filter(company=target_user.company, date__year=year, date__month=month)
        holiday_dates = {h.date for h in holiday_qs}
    except NameError:
        holiday_dates = set()

    month_days = []
    stats = {
        'absent': 0, 'leave': 0, 'wfh': 0, 'present': 0, 'holiday': 0, 
        'late_2nd': 0, 'late_3rd': 0, 
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
            if current_date in holiday_dates: status = 'Holiday'
            else: status = 'Present'
        
        # Stats
        if status == 'Absent': stats['absent'] += 1
        elif status == 'Leave': stats['leave'] += 1
        elif status == 'WFH': stats['wfh'] += 1; stats['present'] += 1
        elif status == 'Present': stats['present'] += 1
        elif status == 'Holiday': stats['holiday'] += 1
        elif status == '2nd Late': stats['late_2nd'] += 1 
        elif status == '3rd Late': stats['late_3rd'] += 1 
            
        month_days.append({
            'day': day, 'date': current_date, 'status': status, 'login_time': login_time, 'day_name': current_date.strftime("%A")
        })

    # --- SALARY CALCULATION ---
    salary_data = {}
    base_salary = target_user.monthly_salary
    
    if base_salary > 0:
        per_day_salary = base_salary / Decimal(num_days)
        
        full_day_cuts = stats['absent'] + stats['late_3rd']
        full_deduction = per_day_salary * Decimal(full_day_cuts)
        
        half_day_cuts = stats['late_2nd']
        half_deduction = (per_day_salary / Decimal(2)) * Decimal(half_day_cuts)
        
        gross_salary = base_salary - (full_deduction + half_deduction)
        
        esi_deduction = (gross_salary * target_user.esi_percentage) / Decimal(100)
        p_tax = target_user.professional_tax
        net_salary = gross_salary - esi_deduction - p_tax

        salary_data = {
            'base_salary': round(base_salary, 2),
            'per_day': round(per_day_salary, 2),
            'absent_days': stats['absent'],
            'late_3rd_days': stats['late_3rd'],
            'full_day_deduction': round(full_deduction, 2),
            'late_2nd_days': stats['late_2nd'],
            'half_day_deduction': round(half_deduction, 2),
            'gross_salary': round(gross_salary, 2),
            'esi_pct': target_user.esi_percentage,
            'esi_amount': round(esi_deduction, 2),
            'p_tax': round(p_tax, 2),
            'net_salary': round(net_salary, 2)
        }

    return render(request, 'dashboard/view_attendance.html', {
        'target_user': target_user,
        'month_days': month_days,
        'year': year, 'month': month,
        'month_name': calendar.month_name[month],
        'is_manager': is_manager,
        'stats': stats,
        'salary_data': salary_data
    })

# ==========================================
# 5. NEW FEATURES (SMTP & NOTIFICATIONS)
# ==========================================

@login_required
def smtp_settings(request):
    if request.user.role != 'HR':
        return redirect('dashboard')
    
    company = request.user.company
    
    if request.method == 'POST':
        form = SMTPSettingsForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, "SMTP Settings Saved Successfully.")
            return redirect('hr_dashboard')
    else:
        form = SMTPSettingsForm(instance=company)
    
    return render(request, 'dashboard/smtp_settings.html', {'form': form})

@login_required
def notifications_view(request):
    notifs = Notification.objects.filter(recipient=request.user)
    return render(request, 'dashboard/notifications.html', {'notifications': notifs})



# ... existing imports ...

@login_required
def track_sheet(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    viewer = request.user
    
    # --- PERMISSIONS ---
    can_view_work = (viewer == target_user) or (target_user.reports_to == viewer) or (viewer.role == 'HR')
    can_assign_task = True # Anyone can assign (as per previous request)

    # --- DATE LOGIC ---
    today = date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except ValueError:
        year, month = today.year, today.month

    # --- CALENDAR DATA ---
    first_weekday, num_days = calendar.monthrange(year, month)
    start_index = (first_weekday + 1) % 7
    
    # Prefetch related items to avoid N+1 queries
    sheets = TrackSheet.objects.filter(
        user=target_user, 
        date__year=year, 
        date__month=month
    ).prefetch_related('work_items', 'task_items')
    
    sheet_map = {s.date: s for s in sheets}
    
    month_days = []
    for _ in range(start_index): month_days.append(None)

    for day in range(1, num_days + 1):
        current_date = date(year, month, day)
        sheet = sheet_map.get(current_date)
        
        # Prepare data for template
        work_items = sheet.work_items.all() if (sheet and can_view_work) else []
        task_items = sheet.task_items.all() if sheet else []
        
        # Calculate summary status for the day (optional logic)
        day_status = "Pending"
        if work_items:
            if all(w.status == 'Completed' for w in work_items):
                day_status = "Completed"
            elif any(w.status == 'In Progress' for w in work_items):
                day_status = "In Progress"

        month_days.append({
            'day': day, 
            'date': current_date, 
            'sheet': sheet,
            'work_items': work_items,
            'task_items': task_items,
            'day_status': day_status,
            'can_view_work': can_view_work # Pass this down for privacy check
        })

    return render(request, 'dashboard/track_sheet.html', {
        'target_user': target_user,
        'month_days': month_days,
        'year': year, 'month': month,
        'month_name': calendar.month_name[month],
        'can_view_work': can_view_work,
        'can_assign_task': can_assign_task,
    })

@login_required
def handle_track_actions(request, user_id):
    """ Helper view to handle Add/Update/Delete of items via POST """
    if request.method != 'POST':
        return redirect('dashboard')

    target_user = get_object_or_404(User, id=user_id)
    action_type = request.POST.get('action_type') # 'add_work', 'add_task', 'update_status'
    date_str = request.POST.get('date')
    
    # Get or Create Sheet
    sheet, _ = TrackSheet.objects.get_or_create(user=target_user, date=date_str)
    
    # 1. ADD WORK LOG
    if action_type == 'add_work' and request.user == target_user:
        task_desc = request.POST.get('task_desc')
        if task_desc:
            WorkItem.objects.create(track_sheet=sheet, task=task_desc, status='Pending')
            messages.success(request, "Work item added.")

    # 2. ADD ASSIGNED TASK
    elif action_type == 'add_task':
        task_desc = request.POST.get('task_desc')
        if task_desc:
            TaskItem.objects.create(
                track_sheet=sheet, 
                task=task_desc, 
                assigned_by=request.user, 
                status='Pending'
            )
            # Notification
            Notification.objects.create(
                recipient=target_user,
                sender=request.user,
                title=f"New Task Assigned: {date_str}",
                message=f"Task: {task_desc}\nBy: {request.user.username}"
            )
            messages.success(request, "Task assigned.")

    # 3. UPDATE STATUS (Work or Task)
    elif action_type == 'update_status':
        item_type = request.POST.get('item_type') # 'work' or 'task'
        item_id = request.POST.get('item_id')
        new_status = request.POST.get('new_status')
        
        if item_type == 'work' and request.user == target_user:
            item = get_object_or_404(WorkItem, id=item_id, track_sheet=sheet)
            item.status = new_status
            item.save()
        
        elif item_type == 'task':
            # Both Assignee (target_user) and Assigner (request.user) can update status
            item = get_object_or_404(TaskItem, id=item_id, track_sheet=sheet)
            item.status = new_status
            item.save()
            
    # Redirect back to track sheet
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    return redirect(f"/track-sheet/{user_id}/?year={date_obj.year}&month={date_obj.month}")
# ... existing imports ...

@login_required
def delete_task_assignment(request, task_id):
    # FIXED: Get TaskItem instead of TrackSheet
    task_item = get_object_or_404(TaskItem, id=task_id)
    
    # Security: Ensure current user is the one who assigned it
    if task_item.assigned_by != request.user:
        messages.error(request, "Permission Denied. You did not assign this task.")
        return redirect('dashboard')
    
    # Archive Logic
    task_item.sender_archived = True
    task_item.save()
    
    messages.success(request, "Task hidden from your dashboard.")
    return redirect('dashboard')

