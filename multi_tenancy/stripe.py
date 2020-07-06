from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import stripe
import logging

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_API_KEY


def create_subscription(email, customer_id=""):

    if not stripe.api_key or not settings.STRIPE_GROWTH_PRICE_ID:
        logger.warning(
            "Cannot process billing setup because Stripe env vars are not set."
        )
        return None

    payload = {
        "payment_method_types": ["card"],
        "line_items": [{"price": settings.STRIPE_GROWTH_PRICE_ID, "quantity": 1,}],
        "mode": "subscription",
        "customer_email": email,
        "success_url": settings.SITE_URL
        + "/billing/welcome?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": settings.SITE_URL
        + "/billing/failed?session_id={CHECKOUT_SESSION_ID}",
    }

    if customer_id:
        payload["customer"] = customer_id

    if settings.TEST:
        logger.info(f"Simulating Stripe checkout session: {payload}")
        return "cs_1234567890"

    session = stripe.checkout.Session.create(**payload)

    return session.id
