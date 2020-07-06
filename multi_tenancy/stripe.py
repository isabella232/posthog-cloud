from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import stripe
import logging

logger = logging.getLogger(__name__)


def create_subscription(email, customer_id=""):

    if not settings.STRIPE_API_KEY or not settings.STRIPE_GROWTH_PRICE_ID:
        logger.warning(
            "Cannot process billing setup because Stripe env vars are not set."
        )
        return (None, None)

    stripe.api_key = settings.STRIPE_API_KEY

    # Create the customer first if it doesn't exist
    if not customer_id:
        customer_id = (
            stripe.Customer.create(email=email).id
            if not settings.TEST
            else "cus_000111222"
        )

    payload = {
        "payment_method_types": ["card"],
        "line_items": [{"price": settings.STRIPE_GROWTH_PRICE_ID, "quantity": 1,}],
        "mode": "subscription",
        "customer": customer_id,
        "success_url": settings.SITE_URL
        + "/billing/welcome?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": settings.SITE_URL
        + "/billing/failed?session_id={CHECKOUT_SESSION_ID}",
    }

    if settings.TEST:
        logger.info(f"Simulating Stripe checkout session: {payload}")
        return ("cs_1234567890", customer_id)

    session = stripe.checkout.Session.create(**payload)

    return (session.id, customer_id)


def customer_portal_url(customer_id):

    if not settings.STRIPE_API_KEY:
        logger.warning(
            "Cannot process billing management because Stripe API key is not set."
        )
        return None

    if settings.TEST:
        return f"/manage-my-billing/{customer_id}"

    stripe.api_key = settings.STRIPE_API_KEY

    session = stripe.billing_portal.Session.create(customer=customer_id,)

    return session.url

