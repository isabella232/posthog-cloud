from django.http import JsonResponse
from posthog.api.user import user
from .models import TeamBilling
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

        if instance.should_setup_billing:
            output = json.loads(response.content)

            checkout_session = 1
            output["billing"] = {
                "should_setup_billing": instance.should_setup_billing,
                "stripe_checkout_session": checkout_session,
            }

            response = JsonResponse(output)

    return response

