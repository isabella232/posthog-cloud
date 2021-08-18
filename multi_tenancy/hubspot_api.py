import logging
from .utils import trim_and_validate_email
from typing import Dict

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from hubspot import HubSpot
from hubspot.crm.contacts import SimplePublicObjectInput
from typing import Optional

logger = logging.getLogger(__name__)

hubspot_client = HubSpot()


def _init_hubspot() -> None:
    if not settings.HUBSPOT_API_KEY:
        raise ImproperlyConfigured("Cannot initialize HubSpot because env vars are not set.")

    hubspot_client.api_key = settings.HUBSPOT_API_KEY


def create_contact(email: str, lead_source: Optional[str] = None):
    email = trim_and_validate_email(email)
    _init_hubspot()
    return hubspot_client.crm.contacts.basic_api.create(
        simple_public_object_input=SimplePublicObjectInput(
            properties={"email": email, "lead_source": lead_source}
        )
    )


def update_contact(email: str, properties: Dict):
    email = trim_and_validate_email(email)
    _init_hubspot()
    return hubspot_client.crm.contacts.basic_api.update(
        contact_id=email,
        id_property="email",
        simple_public_object_input=SimplePublicObjectInput(
            properties=properties
        )
    )
