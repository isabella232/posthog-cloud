from typing import List

from django.urls import path, include
from django.contrib import admin
from posthog.urls import opt_slash_path
from posthog.urls import urlpatterns as posthog_urls

from .views import (
    BillingSubscribeViewset,
    BillingViewset,
    MultiTenancyOrgSignupViewset,
    PlanViewset,
    create_web_contact,
    plan_template,
    stripe_billing_portal,
    stripe_checkout_view,
    stripe_webhook,
    update_web_contact,
)

# Include `posthog-cloud` routes first
urlpatterns: List = [
    # admin
    path("admin/", include("loginas.urls")),
    path("admin/", admin.site.urls),
    opt_slash_path(
        "api/signup", MultiTenancyOrgSignupViewset.as_view(),
    ),  # Override to support setting a billing plan on signup
    opt_slash_path("api/plans", PlanViewset.as_view({"get": "list"}), name="billing_plans"),
    path("api/plans/<str:key>/template/", plan_template, name="billing_plan_template"),
    path("api/plans/<str:key>", PlanViewset.as_view({"get": "retrieve"}), name="billing_plan"),
    opt_slash_path("api/billing", BillingViewset.as_view({"get": "retrieve"}), name="billing"),
    opt_slash_path(
        "billing/setup", stripe_checkout_view, name="billing_setup",
    ),  # Redirect to Stripe Checkout to set-up billing (requires session ID)
    opt_slash_path(
        "billing/manage", stripe_billing_portal, name="billing_manage",
    ),  # Redirect to Stripe Customer Portal to manage subscription
    opt_slash_path("billing/stripe_webhook", stripe_webhook, name="billing_stripe_webhook"),  # Stripe Webhook
    opt_slash_path("billing/subscribe", BillingSubscribeViewset.as_view({"post": "create"}), name="billing_subscribe"),
    opt_slash_path("create_web_contact", create_web_contact, name="create_web_contact"),
    opt_slash_path("update_web_contact", update_web_contact, name="update_web_contact"),
]

# Include base `posthog` routes
urlpatterns += posthog_urls
