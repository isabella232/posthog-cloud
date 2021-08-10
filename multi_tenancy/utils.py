import calendar
import datetime
from typing import List, Optional, Tuple

import re
import pytz
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from ee.clickhouse.client import sync_execute
from posthog.models import Organization, Team

EVENT_USAGE_CACHING_TTL: int = settings.EVENT_USAGE_CACHING_TTL

CORS_ORIGIN_REGEX = r"https:\/\/(\w*\.)?posthog.com\/?$"
EMAIL_REGEX = r"(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|\"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*\")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])"

def get_event_usage_for_timerange(
    organization: Organization,
    start_time: datetime.datetime,
    end_time: datetime.datetime,
) -> Optional[int]:
    """
    Returns the number of events ingested in the time range (inclusive) for all
    teams of the organization. Intended mainly for billing purposes.
    """

    result = sync_execute(
        "SELECT count(1) FROM events where team_id IN %(team_ids)s AND timestamp"
        " >= %(date_from)s AND timestamp <= %(date_to)s",
        {
            "date_from": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "date_to": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "team_ids": list(
                Team.objects.filter(organization=organization).values_list(
                    "id", flat=True,
                ),
            ),
        },
    )

    if result:
        return result[0][0]

    return None  # in case CH is not available (mainly to run posthog tests)


def get_monthly_event_usage(
    organization: Organization, at_date: datetime.datetime = None,
) -> int:
    """
    Returns the number of events ingested in the calendar month (UTC) of the date provided for all
    teams of the organization. Intended mainly for billing purposes.
    """
    if not at_date:
        at_date = timezone.now()

    date_range: Tuple[int] = calendar.monthrange(at_date.year, at_date.month)
    start_time: datetime.datetime = datetime.datetime.combine(
        datetime.datetime(at_date.year, at_date.month, 1), datetime.time.min,
    ).replace(tzinfo=pytz.UTC)
    end_time: datetime.datetime = datetime.datetime.combine(
        datetime.datetime(at_date.year, at_date.month, date_range[1]),
        datetime.time.max,
    ).replace(tzinfo=pytz.UTC)

    return get_event_usage_for_timerange(
        organization=organization, start_time=start_time, end_time=end_time
    )


def get_cached_monthly_event_usage(organization: Organization) -> int:
    """
    Returns the cached number of events used in the current calendar month. Results will be cached for 12 hours.
    """

    cache_key: str = f"monthly_usage_{organization.id}"
    cached_result: int = cache.get(cache_key)

    if cached_result is not None:
        return cached_result

    now: datetime.datetime = timezone.now()
    result: int = get_monthly_event_usage(organization=organization, at_date=now)

    if result is None:
        # Don't cache unavailable/error result
        return result

    # Cache the result
    start_of_next_month = datetime.datetime.combine(
        datetime.datetime(now.year, now.month, 1), datetime.time.min,
    ).replace(tzinfo=pytz.UTC) + relativedelta(months=+1)

    cache.set(
        cache_key,
        result,
        min(
            EVENT_USAGE_CACHING_TTL,
            (start_of_next_month - timezone.now()).total_seconds(),
        ),
    )  # cache result for default time or until next month

    return result


def get_billing_cycle_anchor(at_date: datetime.datetime) -> datetime.datetime:
    """
    Computes the billing cycle anchor for a given date to the next applicable's 1st of the month.
    """
    after_trial_date = at_date + datetime.timedelta(days=settings.BILLING_TRIAL_DAYS)

    anchor_date = (
        after_trial_date
        if after_trial_date.day <= 1
        else (after_trial_date + relativedelta(months=+1))
    )

    # Billing anchor is next month
    return datetime.datetime.combine(
        anchor_date.replace(day=1), datetime.time.max,
    ).replace(tzinfo=pytz.UTC)

def is_cors_origin_ok(origin: str) -> bool:
    if not origin:
        return False

    return settings.DEBUG or bool(re.match(CORS_ORIGIN_REGEX, origin))

def transform_response_add_cors(response: Response, origin: str, allowed_methods: List[str]) -> Response:
    response["Access-Control-Allow-Origin"] = origin
    response["Access-Control-Allow-Methods"] = ",".join(allowed_methods)
    response["Access-Control-Allow-Headers"] = "*"
    return response

def get_error_status(e: Exception):
    if e.__class__.__name__ == "ValueError":
        return status.HTTP_400_BAD_REQUEST
    if e.__class__.__name__ == "ApiException":
        return e.status
    return status.HTTP_500_INTERNAL_SERVER_ERROR

def trim_and_validate_email(email: str):
    if not email:
        raise ValueError("Email not provided")
    email = email.strip().lower()
    is_valid = bool(re.match(EMAIL_REGEX, email))
    if not is_valid:
        raise ValueError("Email is invalid")
    return email

