import datetime
from django.utils import timezone
import json
import logging
from distutils.util import strtobool
from typing import Dict, Optional

import posthoganalytics
import stripe
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import get_template
from django.views.decorators.csrf import csrf_exempt
from posthog.api.signup import SignupViewset
from posthog.urls import render_template
from rest_framework import mixins, status
from rest_framework.viewsets import GenericViewSet, ModelViewSet
from sentry_sdk import capture_exception, capture_message

from multi_tenancy.hubspot_api import create_contact, update_contact
from multi_tenancy.models import OrganizationBilling, Plan
from multi_tenancy.serializers import (
    BillingSerializer,
    BillingSubscribeSerializer,
    MultiTenancyOrgSignupSerializer,
    PlanSerializer,
)
from multi_tenancy.stripe import (
    cancel_payment_intent,
    customer_portal_url,
    parse_webhook,
    set_default_payment_method_for_customer,
)
from multi_tenancy.tasks import (
    report_card_validated,
    update_subscription_billing_period,
)
from multi_tenancy.utils import (
    get_error_status,
    is_cors_origin_ok,
    transform_response_add_cors,
)

logger = logging.getLogger(__name__)


class MultiTenancyOrgSignupViewset(SignupViewset):
    serializer_class = MultiTenancyOrgSignupSerializer


class PlanViewset(ModelViewSet):
    serializer_class = PlanSerializer
    lookup_field = "key"

    def get_queryset(self):
        queryset = Plan.objects.filter(is_active=True)

        self_serve: Optional[str] = self.request.query_params.get("self_serve", None)
        if self_serve is not None:
            queryset = queryset.filter(self_serve=bool(strtobool(self_serve)))

        return queryset


class BillingViewset(mixins.RetrieveModelMixin, GenericViewSet):
    serializer_class = BillingSerializer

    def get_object(self) -> OrganizationBilling:
        instance, _ = OrganizationBilling.objects.get_or_create(
            organization=self.request.user.organization
        )
        return instance


class BillingSubscribeViewset(mixins.CreateModelMixin, GenericViewSet):
    serializer_class = BillingSubscribeSerializer


def stripe_checkout_view(request: HttpRequest):
    return render_template(
        "stripe-checkout.html",
        request,
        {"STRIPE_PUBLISHABLE_KEY": settings.STRIPE_PUBLISHABLE_KEY},
    )


def stripe_billing_portal(request: HttpRequest):
    url = ""

    if not request.user.is_authenticated:
        return HttpResponse("Unauthorized", status=status.HTTP_401_UNAUTHORIZED)

    instance, _ = OrganizationBilling.objects.get_or_create(
        organization=request.user.organization,
    )

    if instance.stripe_customer_id:
        url = customer_portal_url(instance.stripe_customer_id)

    # Report event manually because this page doesn't load any HTML (i.e. there's no autocapture available).
    posthoganalytics.capture(
        request.user.distinct_id,
        "visited billing customer portal",
        {"portal_available": bool(url)},
    )

    return redirect(url or "/")


@csrf_exempt
def stripe_webhook(request: HttpRequest) -> JsonResponse:
    response: JsonResponse = JsonResponse({"success": True}, status=status.HTTP_200_OK)
    error_response: JsonResponse = JsonResponse(
        {"success": False}, status=status.HTTP_400_BAD_REQUEST,
    )
    signature: str = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event: Dict = parse_webhook(request.read(), signature)
    except Exception as e:
        capture_exception(e)
        return error_response

    try:

        customer_id = event["data"]["object"]["customer"]

        try:
            instance = OrganizationBilling.objects.get(stripe_customer_id=customer_id)
        except OrganizationBilling.DoesNotExist:

            # Check this is a Cloud customer first
            prices = list(Plan.objects.all().values_list("price_id", flat=True))

            invoice_lines = []

            if event["type"] == "invoice.payment_succeeded":
                invoice_lines = event["data"]["object"]["lines"]["data"]
            elif event["type"] == "customer.subscription.deleted":
                invoice_lines = event["data"]["object"]["items"]["data"]

            for line in invoice_lines:
                if line["price"]["id"] in prices:
                    capture_message(
                        f"Received {event['type']} on Cloud product"
                        f" for {customer_id}, but customer is not in the database.",
                    )
                    return error_response  # We return an error response so Stripe retries this

            return response

        if event["type"] == "invoice.payment_succeeded":
            subscription_id: str = event["data"]["object"]["subscription"]

            if instance.stripe_subscription_id:
                if instance.stripe_subscription_id != subscription_id:
                    capture_message(
                        "Stripe webhook does not match subscription on file "
                        f"({instance.stripe_subscription_id}): {json.dumps(event)}",
                        "error",
                    )
                    return error_response
            else:
                # First time receiving the subscription_id, record it
                instance.stripe_subscription_id = subscription_id

            instance.should_setup_billing = False
            instance.save()

            update_subscription_billing_period.delay(
                organization_id=instance.organization.id
            )

        # Special handling for plans that only do card validation (e.g. startup or metered-billing plans)
        elif event["type"] == "payment_intent.amount_capturable_updated":
            instance = instance.handle_post_card_validation()

            # Attempt to cancel the validation charge
            try:
                cancel_payment_intent(event["data"]["object"]["id"])
            except stripe.error.StripeError as e:
                capture_exception(e)

            # Attempt to set the newly added card as default
            try:
                set_default_payment_method_for_customer(
                    customer_id, event["data"]["object"]["payment_method"]
                )
            except stripe.error.StripeError as e:
                capture_exception(e)

            report_card_validated(organization_id=instance.organization.id)

        elif event["type"] == "customer.subscription.deleted":
            if instance.plan.key == "startup" and event["data"]["object"]["cancel_at"]:
                if (
                    event["data"]["object"]["cancel_at"]
                    == event["data"]["object"]["canceled_at"]
                ):
                    # Startup plan ended for user based on a schedule, transition the organization to the standard plan.
                    # EDEGE CASE RISK: we manually schedule a plan cancellation (e.g. user required) for a startup
                    # plan which would result in a new subscription being created anyways.
                    instance.plan = Plan.objects.get(key="standard")
                    instance.handle_post_card_validation()
            else:
                instance.register_cancellation(
                    timezone.make_aware(
                        datetime.datetime.fromtimestamp(
                            event["data"]["object"]["canceled_at"]
                        )
                    )
                )

    except KeyError:
        # Malformed request
        return error_response

    return response


@csrf_exempt
def plan_template(request: HttpRequest, key: str) -> HttpResponse:
    plan: Optional[Plan] = None
    try:
        plan = Plan.objects.get(key=key, is_active=True)
    except Plan.DoesNotExist:
        pass

    if not plan:
        return HttpResponse(status=status.HTTP_204_NO_CONTENT)

    try:
        template = get_template(f"plans/{key}.html")
    except TemplateDoesNotExist:
        return HttpResponse(status=status.HTTP_204_NO_CONTENT)

    html = template.render(request=request)
    return HttpResponse(html)


@csrf_exempt
def create_web_contact(request: HttpRequest) -> JsonResponse:
    origin = request.headers.get("Origin")
    cors_origin_ok = is_cors_origin_ok(origin)
    response = JsonResponse({}, status=status.HTTP_200_OK)

    if not cors_origin_ok:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response

    if request.method == "POST":
        try:
            email = request.POST.get("email")
            lead_source = request.POST.get("lead_source", None)
            create_contact(email=email, lead_source=lead_source)
        except Exception as e:
            capture_exception(e)
            if settings.DEBUG:
                print(e)
            response = JsonResponse({"success": False}, status=get_error_status(e))
        else:
            response = JsonResponse({"success": True}, status=status.HTTP_201_CREATED)

    return transform_response_add_cors(response, origin, ["POST"])


@csrf_exempt
def update_web_contact(request: HttpRequest) -> JsonResponse:
    origin = request.headers.get("Origin")
    cors_origin_ok = is_cors_origin_ok(origin)
    response = JsonResponse({}, status=status.HTTP_200_OK)

    if not cors_origin_ok:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response

    if request.method == "POST":
        try:
            email = request.POST.get("email")
            update_contact(email, request.POST)
        except Exception as e:
            capture_exception(e)
            if settings.DEBUG:
                print(e)
            response = JsonResponse({"success": False}, status=get_error_status(e))
        else:
            response = JsonResponse({"success": True}, status=status.HTTP_200_OK)

    return transform_response_add_cors(response, origin, ["POST"])
