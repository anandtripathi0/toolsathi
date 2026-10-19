import json
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from .models import Preferences

@require_http_methods(['GET', 'POST'])
def signup(request):
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.save())
        return redirect('dashboard')
    return render(request, 'accounts/signup.html', {'form': form, 'page_title': 'Optional account | ToolSathi'})

@login_required
def dashboard(request):
    preferences, _ = Preferences.objects.get_or_create(user=request.user)
    return render(request, 'accounts/dashboard.html', {'preferences': preferences, 'page_title': 'Your workspace | ToolSathi'})

@require_http_methods(['GET', 'POST'])
def preferences(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Sign in only to sync preferences. All tools remain free without an account.'}, status=401)
    from apps.tools.registry import REGISTRY
    pref, _ = Preferences.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            if not isinstance(data, dict):
                raise ValueError
            favorites = data.get('favorites', pref.favorites)
            recent = data.get('recent', pref.recent)
            enabled = data.get('history_enabled', pref.history_enabled)
            if not isinstance(enabled, bool) or not all(isinstance(x, list) for x in (favorites, recent)):
                raise ValueError
            if len(favorites) > 150 or len(recent) > 50 or not all(isinstance(x, str) and x in REGISTRY for x in favorites + recent):
                raise ValueError
            pref.favorites = list(dict.fromkeys(favorites))
            pref.history_enabled = enabled
            pref.recent = list(dict.fromkeys(recent))[:20] if enabled else []
            pref.save()
        except (ValueError, TypeError, UnicodeDecodeError):
            return JsonResponse({'error': 'Invalid preference data. Only known tool IDs are accepted.'}, status=400)
    return JsonResponse({'favorites': pref.favorites, 'history_enabled': pref.history_enabled, 'recent': pref.recent})
