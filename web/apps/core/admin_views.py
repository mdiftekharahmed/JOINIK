from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from apps.accounts.models import Organization, UserProfile
from apps.ai_engine.models import AIModelVersion
from apps.audit.models import AuditLog

def is_admin(user):
    return user.is_superuser or (hasattr(user, 'profile') and user.profile.role == 'SYSTEM_ADMIN')

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    context = {
        'user_count': User.objects.count(),
        'org_count': Organization.objects.count(),
        'ai_models_count': AIModelVersion.objects.count(),
        'audit_count': AuditLog.objects.count()
    }
    return render(request, 'core/admin/dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def users(request):
    users_list = User.objects.select_related('profile', 'profile__organization').all()
    return render(request, 'core/admin/users.html', {'users_list': users_list})

@login_required
@user_passes_test(is_admin)
def organizations(request):
    orgs = Organization.objects.all()
    return render(request, 'core/admin/organizations.html', {'orgs': orgs})

@login_required
@user_passes_test(is_admin)
def sensor_config(request):
    return redirect('parameter_list')

@login_required
@user_passes_test(is_admin)
def sensor_edit(request, pk):
    return redirect('parameter_list')

@login_required
@user_passes_test(is_admin)
def ai_model(request):
    models = AIModelVersion.objects.all().order_by('-trained_at')
    return render(request, 'core/admin/ai_models.html', {'models': models})

@login_required
@user_passes_test(is_admin)
def audit_log(request):
    logs = AuditLog.objects.select_related('user').all().order_by('-timestamp')[:500]
    return render(request, 'core/admin/audit.html', {'logs': logs})
