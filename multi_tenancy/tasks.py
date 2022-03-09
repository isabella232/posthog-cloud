import datetime
from typing import Optional

import dateutil
import posthoganalytics
import pytz
from django.utils import timezone
from posthog.celery import app
from posthog.models import Organization
from sentry_sdk import capture_message

from multi_tenancy.stripe import get_subscription, report_subscription_item_usage
from multi_tenancy.utils import get_event_usage_for_timerange

from .models import OrganizationBilling, Plan


def compute_daily_usage_for_organizations(
    for_date: Optional[datetime.datetime] = None,
) -> None:
    """
    Creates a separate async task to calculate the daily usage for each organization the day before.
    """

    for instance in OrganizationBilling.objects.filter(
        plan__is_metered_billing=True
    ).exclude(stripe_subscription_id=""):
        _compute_daily_usage_for_organization.delay(
            organization_billing_pk=str(instance.pk), for_date=for_date,
        )


@app.task(bind=True, ignore_result=True, max_retries=3)
def _compute_daily_usage_for_organization(
    self, organization_billing_pk: str, for_date: Optional[str]
) -> None:

    target_date = (
        dateutil.parser.parse(for_date)
        if for_date
        else timezone.now()
        - datetime.timedelta(days=1)  # by default we do the day before
    )

    instance = OrganizationBilling.objects.get(pk=organization_billing_pk)
    start_time = datetime.datetime.combine(target_date, datetime.time.min)
    end_time = datetime.datetime.combine(target_date, datetime.time.max)
    event_usage = get_event_usage_for_timerange(
        organization=instance.organization, start_time=start_time, end_time=end_time
    )

    if event_usage is None:
        # Clickhouse not available, retry
        raise self.retry()

    report_monthly_usage.delay(
        subscription_id=instance.stripe_subscription_id,
        billed_usage=event_usage,
        for_date=start_time,
    )


@app.task(bind=True, ignore_result=True, max_retries=3)
def report_monthly_usage(
    self, subscription_id: str, billed_usage: int, for_date: str
) -> None:

    success = report_subscription_item_usage(
        subscription_id=subscription_id,
        billed_usage=billed_usage,
        timestamp=dateutil.parser.parse(for_date),
    )

    if not success:
        raise self.retry()


@app.task(ignore_result=True, max_retries=3)
def report_invoice_payment_succeeded(organization_id: str, initial: bool) -> None:

    organization = Organization.objects.get(id=organization_id)
    payload = {
        "plan_key": organization.billing.get_plan_key(only_active=False),
        "billing_period_ends": organization.billing.billing_period_ends,
        "organization_id": str(organization.id),
    }
    event = "billing subscription activated" if initial else "billing subscription paid"

    for user in organization.members.all():
        posthoganalytics.capture(
            user.distinct_id, event, payload,
        )


@app.task(ignore_result=True, max_retries=3)
def report_card_validated(organization_id: str) -> None:

    organization = Organization.objects.get(id=organization_id)
    payload = {
        "plan_key": organization.billing.get_plan_key(only_active=False),
        "billing_period_ends": organization.billing.billing_period_ends,
        "organization_id": str(organization.id),
    }

    for user in organization.members.all():
        posthoganalytics.capture(
            user.distinct_id, "billing card validated", payload,
        )


@app.task(bind=True, ignore_result=True, max_retries=3)
def update_subscription_billing_period(self, organization_id: str) -> None:
    """
    Fetches the current billing period for a subscription from Stripe and updates internal records accordingly.
    """

    organization = Organization.objects.get(id=organization_id)
    initial_billing = (
        not organization.billing.billing_period_ends
    )  # first time (or reactivation) of billing agreement (i.e. not continuing use)

    if not organization.billing.stripe_subscription_id:
        raise ValueError(
            "Invalid update_subscription_billing_period received for billing without a subscription ID."
        )

    subscription = get_subscription(organization.billing.stripe_subscription_id)

    if not subscription["status"] == "active":
        capture_message(
            "Received update_subscription_billing_period but subscription is"
            f" not active ({organization.billing.stripe_subscription_id}).",
        )
        return self.retry(countdown=3600)

    organization.billing.billing_period_ends = datetime.datetime.utcfromtimestamp(
        subscription["current_period_end"],
    ).replace(tzinfo=pytz.utc)
    organization.billing.save()

    report_invoice_payment_succeeded.delay(
        organization_id=organization.id, initial=initial_billing,
    )


def transition_startup_users() -> None:
    tomorrow = timezone.now().replace(
        hour=23, minute=59, second=59
    ) + datetime.timedelta(days=1)
    standard_plan = Plan.objects.get(key="standard")

    # Transition legacy startup plans. Previously for startup plans we would create a billing record with an expiration a year from now,
    # and not create any subscription record on Stripe.
    orgs_to_transition = OrganizationBilling.objects.filter(
        plan__key="startup",
        billing_period_ends__lte=tomorrow,
        stripe_subscription_id=None,  # Newer customers on startup plan will have a subscription ID set
    )

    for instance in orgs_to_transition:
        if not instance.stripe_customer_id:
            capture_message(
                f"Cannot transition organization from startup plan because no Stripe record was found. ID: {instance.id}"
            )
            continue

        instance.plan = standard_plan
        instance.handle_post_card_validation()
