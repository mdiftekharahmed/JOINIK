from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
import json
from .models import AIModelVersion

def ai_hub(request):
    models = AIModelVersion.objects.all().order_by('-trained_at')
    context = {
        'models': models,
        'page': 'ai',
    }
    return render(request, 'ai_engine/hub.html', context)

def ai_model_upload(request):
    if request.method == 'POST':
        version_tag = request.POST.get('version_tag')
        features_json = request.POST.get('feature_list', '[]')
        model_file = request.FILES.get('model_file')
        
        try:
            features = json.loads(features_json)
        except Exception:
            messages.error(request, "Invalid JSON for feature list.")
            return redirect('ai_hub')
            
        if version_tag and model_file:
            AIModelVersion.objects.create(
                version_tag=version_tag,
                model_file=model_file,
                feature_list=features,
                notes=request.POST.get('notes', '')
            )
            messages.success(request, f"Model {version_tag} uploaded successfully.")
        else:
            messages.error(request, "Missing required fields.")
            
    return redirect('ai_hub')

def ai_model_activate(request, model_id):
    if request.method == 'POST':
        with transaction.atomic():
            # Deactivate all
            AIModelVersion.objects.update(is_active=False)
            # Activate target
            target = get_object_or_404(AIModelVersion, id=model_id)
            target.is_active = True
            target.save()
            messages.success(request, f"Model {target.version_tag} is now ACTIVE.")
    return redirect('ai_hub')
