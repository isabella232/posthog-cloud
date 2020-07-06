from posthog.urls import render_template
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.shortcuts import redirect
from posthog.api.user import user
from multi_tenancy.models import TeamBilling
from multi_tenancy.stripe import create_subscription, customer_portal_url
import json


def user_with_billing(request):
    """
    Overrides the posthog.api.user.user response to include
    appropriate billing information in the request
    """

    response = user(request)

    if response.status_code == 200:
        # TO-DO: Handle user having multiple teams
        instance, created = TeamBilling.objects.get_or_create(
            team=request.user.team_set.first()
        )

        if instance.should_setup_billing and not instance.is_billing_active:

            checkout_session = create_subscription(
                request.user.email, instance.stripe_customer_id
            )

            if checkout_session:
                output = json.loads(response.content)

                TeamBilling.objects.filter(pk=instance.pk).update(
                    stripe_checkout_session=checkout_session,
                )
                output["billing"] = {
                    "should_setup_billing": instance.should_setup_billing,
                    "stripe_checkout_session": checkout_session,
                    "subscription_url": f"/billing/setup?session_id={checkout_session}",
                }

                response = JsonResponse(output)

    return response


def stripe_checkout_view(request):
    return render_template(
        "stripe-checkout.html",
        request,
        {"STRIPE_PUBLISHABLE_KEY": settings.STRIPE_PUBLISHABLE_KEY},
    )


def stripe_billing_portal(request):

    if not request.user.is_authenticated:
        return HttpResponse("Unauthorized", status=401)

    instance, created = TeamBilling.objects.get_or_create(
        team=request.user.team_set.first()
    )

    if instance.stripe_customer_id:
        url = customer_portal_url(instance.stripe_customer_id)
        if url:
            return redirect(url)

    return redirect("/")


def billing_welcome_view(request):
    return render_template("billing-welcome.html", request)


def billing_failed_view(request):
    return render_template("billing-failed.html", request)
