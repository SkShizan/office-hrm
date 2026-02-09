from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from accounts import views as account_views
from dashboard import views as dash_views # <--- We will use 'dash_views' for everything

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Auth
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', account_views.signup, name='signup'),
    path('verify-otp/', account_views.verify_otp, name='verify_otp'),

    # Dashboard
    path('', dash_views.dashboard, name='dashboard'), # Root URL
    path('hr/', dash_views.hr_dashboard, name='hr_dashboard'),
    path('approve/<int:user_id>/', dash_views.approve_employee, name='approve_employee'),
    path('edit-employee/<int:user_id>/', dash_views.edit_employee, name='edit_employee'),
    path('delete-employee/<int:user_id>/', dash_views.delete_employee, name='delete_employee'),
    
    # Leave & Attendance
    path('apply-leave/', dash_views.apply_leave, name='apply_leave'),
    path('manage-quota/<int:user_id>/', dash_views.manage_quota, name='manage_quota'),
    path('leave-requests/', dash_views.leave_requests_list, name='leave_requests_list'),
    path('leave-action/<int:leave_id>/<str:action>/', dash_views.action_leave, name='action_leave'),
    path('attendance/<int:user_id>/', dash_views.view_attendance, name='view_attendance'),
    
    # Teams
    path('manage-teams/', dash_views.manage_teams, name='manage_teams'),

    # --- NEW FEATURES (Use dash_views prefix) ---
    path('hr/smtp/', dash_views.smtp_settings, name='smtp_settings'),
    path('notifications/', dash_views.notifications_view, name='notifications_view'),

    # Add inside urlpatterns:
    path('track-sheet/<int:user_id>/', dash_views.track_sheet, name='track_sheet'),
    path('track-actions/<int:user_id>/', dash_views.handle_track_actions, name='handle_track_actions'),
    path('task/archive/<int:task_id>/', dash_views.delete_task_assignment, name='delete_task_assignment'),
]