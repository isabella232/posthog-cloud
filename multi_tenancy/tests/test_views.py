import vcr

from unittest.mock import patch
from multi_tenancy.tests.base import CloudBaseTest
from rest_framework import status

test_hubspot_api_key = "hubspot_test_abcdef0123456789"

class TestUtils(CloudBaseTest):

    @vcr.use_cassette(cassette_library_dir="multi_tenancy/tests/cassettes")
    @patch('posthoganalytics.feature_enabled')
    def test_create_web_contact_success(self, feature_enabled):
        feature_enabled.return_value = True
        with self.settings(HUBSPOT_API_KEY=test_hubspot_api_key):
            response = self.client.post("/create_web_contact", { "email": "test+thingie@posthog.com" }, HTTP_ORIGIN="https://posthog.com")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    @vcr.use_cassette(cassette_library_dir="multi_tenancy/tests/cassettes")
    @patch('posthoganalytics.feature_enabled')
    def test_create_web_contact_failure_duplicated(self, feature_enabled):
        feature_enabled.return_value = True
        with self.settings(HUBSPOT_API_KEY=test_hubspot_api_key):
            response = self.client.post("/create_web_contact", { "email": "test+thingie@posthog.com" }, HTTP_ORIGIN="https://posthog.com")
            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    @vcr.use_cassette(cassette_library_dir="multi_tenancy/tests/cassettes")
    @patch('posthoganalytics.feature_enabled')
    def test_create_web_contact_failure_no_origin(self, feature_enabled):
        feature_enabled.return_value = True
        with self.settings(HUBSPOT_API_KEY=test_hubspot_api_key):
            response = self.client.post("/create_web_contact", { "email": "test@posthog.com" })
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @vcr.use_cassette(cassette_library_dir="multi_tenancy/tests/cassettes")
    @patch('posthoganalytics.feature_enabled')
    def test_create_web_contact_failure_incorrect_origin(self, feature_enabled):
        feature_enabled.return_value = True
        with self.settings(HUBSPOT_API_KEY=test_hubspot_api_key):
            response = self.client.post("/create_web_contact", { "email": "test@posthog.com" }, HTTP_ORIGIN="https://posthog.com.some-malicious-site.com")
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('posthoganalytics.feature_enabled')
    def test_create_web_contact_failure_no_email(self, feature_enabled):
        feature_enabled.return_value = True
        with self.settings(HUBSPOT_API_KEY=test_hubspot_api_key):
            response = self.client.post("/create_web_contact", { }, HTTP_ORIGIN="https://posthog.com")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('posthoganalytics.feature_enabled')
    def test_create_web_contact_failure_invalid_email(self, feature_enabled):
        feature_enabled.return_value = True
        with self.settings(HUBSPOT_API_KEY=test_hubspot_api_key):
            response = self.client.post("/create_web_contact", { "email": "clearly-not-an-email" }, HTTP_ORIGIN="https://posthog.com")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_web_contact_no_featureflag(self):
        with self.settings(HUBSPOT_API_KEY=test_hubspot_api_key):
            response = self.client.post("/create_web_contact", { "email": "test@posthog.com", "selected_deployment_type": "hosted" }, HTTP_ORIGIN="https://posthog.com")
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    @vcr.use_cassette(cassette_library_dir="multi_tenancy/tests/cassettes")
    @patch('posthoganalytics.feature_enabled')
    def test_update_web_contact_success(self, feature_enabled):
        feature_enabled.return_value = True
        with self.settings(HUBSPOT_API_KEY=test_hubspot_api_key):
            response = self.client.post("/update_web_contact", { "email": "test+thingie@posthog.com", "selected_deployment_type": "hosted" }, HTTP_ORIGIN="https://posthog.com")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    @vcr.use_cassette(cassette_library_dir="multi_tenancy/tests/cassettes")
    @patch('posthoganalytics.feature_enabled')
    def test_update_web_contact_failure_not_found(self, feature_enabled):
        feature_enabled.return_value = True
        with self.settings(HUBSPOT_API_KEY=test_hubspot_api_key):
            response = self.client.post("/update_web_contact", { "email": "noreply@does-not-exist.com", "selected_deployment_type": "hosted" }, HTTP_ORIGIN="https://posthog.com")
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @vcr.use_cassette(cassette_library_dir="multi_tenancy/tests/cassettes")
    @patch('posthoganalytics.feature_enabled')
    def test_update_web_contact_failure_property_nonexistent(self, feature_enabled):
        feature_enabled.return_value = True
        with self.settings(HUBSPOT_API_KEY=test_hubspot_api_key):
            response = self.client.post("/update_web_contact", { "email": "test+thingie@posthog.com", "nonexistent_property": "value" }, HTTP_ORIGIN="https://posthog.com")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('posthoganalytics.feature_enabled')
    def test_update_web_contact_failure_no_email(self, feature_enabled):
        feature_enabled.return_value = True
        with self.settings(HUBSPOT_API_KEY=test_hubspot_api_key):
            response = self.client.post("/update_web_contact", { }, HTTP_ORIGIN="https://posthog.com")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('posthoganalytics.feature_enabled')
    def test_update_web_contact_failure_invalid_email(self, feature_enabled):
        feature_enabled.return_value = True
        with self.settings(HUBSPOT_API_KEY=test_hubspot_api_key):
            response = self.client.post("/update_web_contact", { "email": "clearly-not-an-email", "selected_deployment_type": "hosted" }, HTTP_ORIGIN="https://posthog.com")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_web_contact_no_featureflag(self):
        with self.settings(HUBSPOT_API_KEY=test_hubspot_api_key):
            response = self.client.post("/update_web_contact", { "email": "test@posthog.com", "selected_deployment_type": "hosted" }, HTTP_ORIGIN="https://posthog.com")
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
