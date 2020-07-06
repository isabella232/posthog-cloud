from typing import Dict
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from posthog.models import User, Team
from posthog.api.test.base import TransactionBaseTest
from multi_tenancy.models import TeamBilling
import multi_tenancy.stripe as multi_tenancy_stripe
import random
import datetime


class TestTeamBilling(TransactionBaseTest):

    TESTS_API = True

    def create_team_and_user(self):
        team: Team = Team.objects.create(api_token="token123")
        user = User.objects.create_user(
            f"user{random.randint(100, 999)}@posthog.com", password=self.TESTS_PASSWORD
        )
        team.users.add(user)
        team.save()
        return (team, user)

    def test_team_should_not_set_up_billing_by_default(self):

        count: int = TeamBilling.objects.count()
        response = self.client.post("/api/user/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response_data: Dict = response.json()
        self.assertNotIn(
            "billing", response_data
        )  # key should not be present if should_setup_billing = `False`

        # TeamBilling object should've been created if non-existent
        self.assertEqual(TeamBilling.objects.count(), count + 1)
        team_billing: TeamBilling = TeamBilling.objects.get(team=self.team)

        # Test default values for TeamBilling
        self.assertEqual(team_billing.should_setup_billing, False)
        self.assertEqual(team_billing.stripe_customer_id, "")
        self.assertEqual(team_billing.stripe_checkout_session, "")

    def test_team_that_should_not_set_up_billing(self):
        team, user = self.create_team_and_user()
        TeamBilling.objects.create(team=team, should_setup_billing=False)
        self.client.force_login(user)

        response = self.client.post("/api/user/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response_data: Dict = response.json()
        self.assertNotIn(
            "billing", response_data,
        )  # key should not be present if should_setup_billing = `False`

    def test_team_that_should_set_up_billing_gets_a_checkout_session_started(self):

        team, user = self.create_team_and_user()
        instance = TeamBilling.objects.create(team=team, should_setup_billing=True)
        self.client.force_login(user)

        with self.assertLogs("multi_tenancy.stripe") as l:

            response = self.client.post("/api/user/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            self.assertIn(
                user.email, l.output[0]
            )  # email is included in the simulated payload to Stripe

        response_data: Dict = response.json()
        self.assertEqual(response_data["billing"]["should_setup_billing"], True)
        self.assertEqual(
            response_data["billing"]["stripe_checkout_session"], "cs_1234567890"
        )

        # Check that the checkout session was saved to the database
        instance.refresh_from_db()
        self.assertEqual(
            instance.stripe_checkout_session,
            response_data["billing"]["stripe_checkout_session"],
        )

    def test_team_that_should_set_up_billing_with_an_active_subscription_is_not_billed_twice(
        self,
    ):
        team, user = self.create_team_and_user()
        instance = TeamBilling.objects.create(
            team=team,
            should_setup_billing=True,
            billing_period_ends=timezone.now()
            + datetime.timedelta(minutes=random.randint(10, 99)),
        )
        self.client.force_login(user)

        # Make sure the billing is already active
        self.assertEqual(instance.is_billing_active, True)

        response_data = self.client.post("/api/user/").json()
        self.assertNotIn("billing", response_data)

    def test_warning_is_logged_if_stripe_variables_are_not_properly_configured(self):

        team, user = self.create_team_and_user()
        instance = TeamBilling.objects.create(team=team, should_setup_billing=True)
        self.client.force_login(user)

        with self.settings(STRIPE_GROWTH_PRICE_ID=""):

            with self.assertLogs("multi_tenancy.stripe") as l:
                response_data = self.client.post("/api/user/").json()
                self.assertEqual(
                    l.output[0],
                    "WARNING:multi_tenancy.stripe:Cannot process billing setup because Stripe env vars are not set.",
                )

            self.assertNotIn(
                "billing", response_data
            )  # even if `should_setup_billing=True`
            instance.refresh_from_db()
            self.assertEqual(instance.stripe_checkout_session, "")

        with self.settings(STRIPE_API_KEY=""):

            with self.assertLogs("multi_tenancy.stripe") as l:
                response_data = self.client.post("/api/user/").json()
                self.assertEqual(
                    l.output[0],
                    "WARNING:multi_tenancy.stripe:Cannot process billing setup because Stripe env vars are not set.",
                )

            self.assertNotIn(
                "billing", response_data
            )  # even if `should_setup_billing=True`
            instance.refresh_from_db()
            self.assertEqual(instance.stripe_checkout_session, "")

