from posthog.urls import render_template
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.contrib.auth import login
from posthog.models import User, Team
from django.shortcuts import redirect
from posthog.api.user import user
from multi_tenancy.models import TeamBilling
from multi_tenancy.stripe import create_subscription, customer_portal_url
import json
import posthoganalytics


def signup_view(request):
    if request.method == "GET":
        if request.user.is_authenticated:
            return redirect("/")
        return render_template("signup.html", request)
    if request.method == "POST":
        email = request.POST["email"]
        password = request.POST["password"]
        company_name = request.POST.get("company_name")
        is_first_user = not User.objects.exists()
        try:
            user = User.objects.create_user(
                email=email, password=password, first_name=request.POST.get("name")
            )
        except:
            return render_template(
                "signup.html",
                request=request,
                context={
                    "error": True,
                    "email": request.POST["email"],
                    "company_name": request.POST.get("company_name"),
                    "name": request.POST.get("name"),
                },
            )
        team = Team.objects.create_with_data(users=[user], name=company_name)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        posthoganalytics.capture(
            user.distinct_id,
            "user signed up",
            properties={"is_first_user": is_first_user},
        )
        posthoganalytics.identify(
            user.distinct_id,
            properties={
                "email": user.email,
                "company_name": company_name,
                "name": user.first_name,
            },
        )
        return redirect("/")


def user_with_billing(request):
    """
    Overrides the posthog.api.user.user response to include
    appropriate billing information in the request
    """

    response = user(request)

    if response.status_code == 200:
        # TO-DO: (Future) Handle user having multiple teams
        instance, created = TeamBilling.objects.get_or_create(
            team=request.user.team_set.first()
        )

        if instance.should_setup_billing and not instance.is_billing_active:

            checkout_session, customer_id = create_subscription(
                request.user.email, instance.stripe_customer_id
            )

            if checkout_session:
                output = json.loads(response.content)

                TeamBilling.objects.filter(pk=instance.pk).update(
                    stripe_checkout_session=checkout_session,
                    stripe_customer_id=customer_id,
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
