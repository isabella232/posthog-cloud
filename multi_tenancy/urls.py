from posthog.urls import urlpatterns as posthog_urls, home, render_template
from django.urls import path, include, re_path
from django.shortcuts import redirect
from django.contrib.auth import login, decorators
from django.template.loader import render_to_string
from django.http import HttpResponse
from posthog.models import User, Team
from .views import user_with_billing

import posthoganalytics

def signup_view(request):
    if request.method == 'GET':
        if request.user.is_authenticated:
            return redirect('/')
        return render_template('signup.html', request)
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        company_name = request.POST.get('company_name')
        is_first_user = not User.objects.exists()
        try:
            user = User.objects.create_user(email=email, password=password, first_name=request.POST.get('name'))
        except:
            return render_template('signup.html', request=request, context={'error': True, 'email': request.POST['email'], 'company_name': request.POST.get('company_name'), 'name': request.POST.get('name')})
        team = Team.objects.create_with_data(users=[user], name=company_name)
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        posthoganalytics.capture(user.distinct_id, 'user signed up', properties={'is_first_user': is_first_user})
        posthoganalytics.identify(user.distinct_id, properties={
            'email': user.email,
            'company_name': company_name,
            'name': user.first_name
        })
        return redirect('/')

urlpatterns = posthog_urls[:-1]
urlpatterns[5] = path("api/user/", user_with_billing) # Override to include billing information


urlpatterns += [
    path('signup', signup_view, name='signup'),
    re_path(r'^.*', decorators.login_required(home)),
]