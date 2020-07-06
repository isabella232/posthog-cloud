from posthog.urls import urlpatterns as posthog_urls, home
from django.urls import path, re_path
from django.contrib.auth import decorators
from multi_tenancy.views import (
    signup_view,
    user_with_billing,
    stripe_checkout_view,
    stripe_billing_portal,
    billing_welcome_view,
    billing_failed_view,
)


urlpatterns = posthog_urls[:-1]
urlpatterns[5] = path(
    "api/user/", user_with_billing
)  # Override to include billing information


urlpatterns += [
    path("signup", signup_view, name="signup"),
    path("billing/setup", stripe_checkout_view, name="billing-setup"),
    path("billing/manage", stripe_billing_portal, name="billing-manage"),
    path("billing/welcome", billing_welcome_view, name="billing-welcome"),
    path("billing/failed", billing_failed_view, name="billing-failed"),
    re_path(r"^.*", decorators.login_required(home)),
]
