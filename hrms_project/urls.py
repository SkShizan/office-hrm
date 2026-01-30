from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from accounts import views as account_views
from dashboard import views as dash_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Auth
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', account_views.signup, name='signup'),

    # Dashboard
    path('', dash_views.dashboard, name='dashboard'), # Root URL
    path('hr/', dash_views.hr_dashboard, name='hr_dashboard'),
    path('approve/<int:user_id>/', dash_views.approve_employee, name='approve_employee'),
    path('edit-employee/<int:user_id>/', dash_views.edit_employee, name='edit_employee'),
    path('apply-leave/', dash_views.apply_leave, name='apply_leave'),
    path('manage-quota/<int:user_id>/', dash_views.manage_quota, name='manage_quota'),
    path('leave-requests/', dash_views.leave_requests_list, name='leave_requests_list'),
    path('leave-action/<int:leave_id>/<str:action>/', dash_views.action_leave, name='action_leave'),
    path('attendance/<int:user_id>/', dash_views.view_attendance, name='view_attendance'),
    path('delete-employee/<int:user_id>/', dash_views.delete_employee, name='delete_employee'),
    path('manage-teams/', dash_views.manage_teams, name='manage_teams'),
]