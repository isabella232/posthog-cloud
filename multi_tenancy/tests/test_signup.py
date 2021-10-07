from unittest.mock import patch

from multi_tenancy.models import OrganizationBilling, Plan
from multi_tenancy.tests.base import CloudAPIBaseTest
from posthog.models import Organization, Team, User
from rest_framework import status


class TestTeamSignup(CloudAPIBaseTest):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        User.objects.create(
            email="firstuser@posthog.com",
        )  # to ensure consistency in tests

    @patch("messaging.tasks.process_organization_signup_messaging.delay")
    @patch("posthoganalytics.identify")
    @patch("posthoganalytics.capture")
    def test_api_sign_up(self, mock_capture, mock_identify, mock_messaging):
        """
        Overridden from posthog.api.test.test_organization to patch Redis call. Original test will not be run
        on multitenancy.
        """

        with self.settings(EE_AVAILABLE=False):
            response = self.client.post(
                "/api/signup/",
                {
                    "first_name": "John",
                    "email": "hedgehog@posthog.com",
                    "password": "notsecure",
                    "organization_name": "Hedgehogs United, LLC",
                    "email_opt_in": False,
                },
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user: User = User.objects.order_by("-pk")[0]
        team: Team = user.teams.first()
        organization: Organization = user.organizations.first()
        self.assertEqual(
            response.data,
            {
                "id": user.pk,
                "uuid": str(user.uuid),
                "distinct_id": user.distinct_id,
                "first_name": "John",
                "email": "hedgehog@posthog.com",
                "redirect_url": "/ingestion",
            },
        )

        # Assert that the user was properly created
        self.assertEqual(user.first_name, "John")
        self.assertEqual(user.email, "hedgehog@posthog.com")
        self.assertEqual(user.email_opt_in, False)

        # Assert that the team was properly created
        self.assertEqual(organization.name, "Hedgehogs United, LLC")
        self.assertEqual(team.name, "Default Project")

        mock_capture.assert_called_once()
        self.assertEqual(user.distinct_id, mock_capture.call_args.args[0])
        self.assertEqual("user signed up", mock_capture.call_args.args[1])
        # Assert that the sign up event & identify calls were sent to PostHog analytics
        key_analytics_props = {
            "is_first_user": False,
            "is_organization_first_user": True,
            "new_onboarding_enabled": False,
            "signup_backend_processor": "OrganizationSignupSerializer",
            "signup_social_provider": "",
            "realm": "cloud",
        }
        event_props = mock_capture.call_args.kwargs["properties"]
        for prop, val in key_analytics_props.items():
            self.assertEqual(event_props[prop], val)

        mock_identify.assert_called_once()
        self.assertEqual(user.distinct_id, mock_identify.call_args.args[0])
        identify_props = mock_identify.call_args.args[1]
        for prop, val in key_analytics_props.items():
            self.assertEqual(identify_props[prop], val)


        # Assert that the user is logged in
        response = self.client.get("/api/users/@me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["email"], "hedgehog@posthog.com")

        # Assert that the password was correctly saved
        self.assertTrue(user.check_password("notsecure"))

        # Check that the process_organization_signup_messaging task was fired
        mock_messaging.assert_called_once_with(
            user_id=user.id, organization_id=str(organization.id)
        )

    @patch("messaging.tasks.process_organization_signup_messaging.delay")
    @patch("posthoganalytics.identify")
    @patch("posthoganalytics.capture")
    def test_api_sign_up_existing_email(
        self, mock_capture, mock_identify, mock_messaging
    ):
        response = self.client.post(
            "/api/signup/",
            {
                "first_name": "John",
                "email": "firstuser@posthog.com",
                "password": "notsecure",
                "organization_name": "Hedgehogs United, LLC",
                "email_opt_in": False,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response.data.pop("detail")  # Message might be changed in main repo
        self.assertEqual(
            response.data,
            {"type": "validation_error", "code": "unique", "attr": "email"},
        )

    @patch("posthoganalytics.capture")
    @patch("messaging.tasks.process_organization_signup_messaging.delay")
    def test_default_user_sign_up(self, mock_messaging, mock_capture):
        """
        Most of the behavior is tested on the main repo @ posthog.api.test.test_organization,
        goal of this test is to assert that the signup_messaging logic is called.
        """

        response = self.client.post(
            "/api/signup/",
            {
                "first_name": "John",
                "email": "hedgehog5@posthog.com",
                "password": "notsecure",
                "email_opt_in": False,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user: User = User.objects.order_by("-pk")[0]
        organization: Organization = user.organizations.first()

        # Assert that the user was properly created
        self.assertEqual(user.email, "hedgehog5@posthog.com")

        # Assert that the sign up event & identify calls were sent to PostHog analytics
        mock_capture.assert_called_once()

        self.assertEqual(user.distinct_id, mock_capture.call_args.args[0])
        self.assertEqual("user signed up", mock_capture.call_args.args[1])
        # Assert that the sign up event & identify calls were sent to PostHog analytics
        key_analytics_props = {
            "is_first_user": False,
            "is_organization_first_user": True,
            "new_onboarding_enabled": False,
            "signup_backend_processor": "OrganizationSignupSerializer",
            "signup_social_provider": "",
            "realm": "cloud",
        }
        event_props = mock_capture.call_args.kwargs["properties"]
        for prop, val in key_analytics_props.items():
            self.assertEqual(event_props[prop], val)

        # Assert that the user is logged in
        response = self.client.get("/api/users/@me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["email"], "hedgehog5@posthog.com")

        # Check that the process_organization_signup_messaging task was fired
        mock_messaging.assert_called_once_with(
            user_id=user.id, organization_id=str(organization.id)
        )

    @patch("posthoganalytics.capture")
    @patch("messaging.tasks.process_organization_signup_messaging.delay")
    def test_user_can_sign_up_with_a_custom_plan(self, mock_messaging, mock_capture):
        plan = Plan.objects.create(
            key="startup",
            default_should_setup_billing=True,
            price_id="price_12345678",
            name="Test Plan",
        )

        response = self.client.post(
            "/api/signup",
            {
                "first_name": "John",
                "email": "hedgehog@posthog.com",
                "password": "notsecure",
                "organization_name": "Hedgehogs United, LLC",
                "plan": "startup",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user: User = User.objects.order_by("-pk")[0]
        organization: Organization = user.organizations.first()

        self.assertEqual(user.first_name, "John")
        self.assertEqual(user.email, "hedgehog@posthog.com")
        self.assertEqual(organization.name, "Hedgehogs United, LLC")

        org_billing: OrganizationBilling = organization.billing
        self.assertEqual(org_billing.plan, plan)
        self.assertEqual(org_billing.should_setup_billing, True)

        # Check that the process_organization_signup_messaging task was fired
        mock_messaging.assert_called_once_with(
            user_id=user.id,
            organization_id=str(organization.id),
        )

        # Check that we send the sign up event to PostHog analytics
        mock_capture.assert_called_once()
        self.assertEqual(user.distinct_id, mock_capture.call_args.args[0])
        self.assertEqual("user signed up", mock_capture.call_args.args[1])
        # Assert that the sign up event & identify calls were sent to PostHog analytics
        key_analytics_props = {
            "is_first_user": False,
            "is_organization_first_user": True,
            "new_onboarding_enabled": False,
            "signup_backend_processor": "OrganizationSignupSerializer",
            "signup_social_provider": "",
            "realm": "cloud",
        }
        event_props = mock_capture.call_args.kwargs["properties"]
        for prop, val in key_analytics_props.items():
            self.assertEqual(event_props[prop], val)

    @patch("posthoganalytics.capture")
    @patch("messaging.tasks.process_organization_signup_messaging.delay")
    def test_user_can_sign_up_with_an_invalid_plan(self, mock_messaging, mock_capture):

        response = self.client.post(
            "/api/signup/",
            {
                "first_name": "Jane",
                "email": "hedgehog6@posthog.com",
                "password": "notsecure",
                "plan": "NOTVALID",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user: User = User.objects.order_by("-pk")[0]
        organization: Organization = user.organizations.first()

        self.assertEqual(user.first_name, "Jane")
        self.assertEqual(user.email, "hedgehog6@posthog.com")
        self.assertFalse(
            OrganizationBilling.objects.filter(organization=organization).exists(),
        )  # OrganizationBilling is not created yet

        # Check that we send the sign up event to PostHog analytics
        mock_capture.assert_called_once()
        self.assertEqual(user.distinct_id, mock_capture.call_args.args[0])
        self.assertEqual("user signed up", mock_capture.call_args.args[1])
        # Assert that the sign up event & identify calls were sent to PostHog analytics
        key_analytics_props = {
            "is_first_user": False,
            "is_organization_first_user": True,
            "new_onboarding_enabled": False,
            "signup_backend_processor": "OrganizationSignupSerializer",
            "signup_social_provider": "",
            "realm": "cloud",
        }
        event_props = mock_capture.call_args.kwargs["properties"]
        for prop, val in key_analytics_props.items():
            self.assertEqual(event_props[prop], val)

        # Check that the process_organization_signup_messaging task was fired
        mock_messaging.assert_called_once_with(
            user_id=user.pk,
            organization_id=str(organization.id),
        )

    @patch("messaging.tasks.process_organization_signup_messaging.delay")
    @patch("posthoganalytics.capture")
    def test_sign_up_multiple_teams_multi_tenancy(
        self,
        mock_capture,
        mock_messaging,
    ):

        # Create a user first to make sure additional users can be created
        User.objects.create(email="i_was_first@posthog.com")

        response = self.client.post(
            "/api/signup/",
            {
                "first_name": "John",
                "email": "multi@posthog.com",
                "password": "eruceston",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user: User = User.objects.order_by("-pk")[0]
        self.assertEqual(
            response.data,
            {
                "id": user.pk,
                "uuid": str(user.uuid),
                "distinct_id": user.distinct_id,
                "first_name": "John",
                "email": "multi@posthog.com",
                "redirect_url": "/ingestion",
            },
        )

        # Assert that the user was properly created
        self.assertEqual(user.first_name, "John")
        self.assertEqual(user.email, "multi@posthog.com")

        # Assert that the sign up event & identify calls were sent to PostHog analytics
        mock_capture.assert_called_once()
        self.assertEqual(user.distinct_id, mock_capture.call_args.args[0])
        self.assertEqual("user signed up", mock_capture.call_args.args[1])
        # Assert that the sign up event & identify calls were sent to PostHog analytics
        key_analytics_props = {
            "is_first_user": False,
            "is_organization_first_user": True,
            "new_onboarding_enabled": False,
            "signup_backend_processor": "OrganizationSignupSerializer",
            "signup_social_provider": "",
            "realm": "cloud",
        }
        event_props = mock_capture.call_args.kwargs["properties"]
        for prop, val in key_analytics_props.items():
            self.assertEqual(event_props[prop], val)

        # Assert that the user is logged in
        response = self.client.get("/api/users/@me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["email"], "multi@posthog.com")

        # Assert that the password was correctly saved
        self.assertTrue(user.check_password("eruceston"))

        # Check that the process_organization_signup_messaging task was fired
        mock_messaging.assert_called_once_with(
            user_id=user.pk,
            organization_id=str(user.organization.id),
        )
