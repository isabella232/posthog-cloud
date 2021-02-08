# PostHog Cloud

This repository is used to run PostHog Cloud (app.posthog.com). It enables anyone to sign up to an account and create their own account along with an organization.

NOTE: This repository **is copyrighted** (unlike our [main repo](https://github.com/posthog/posthog)). You are not allowed to use this code to host your own version of app.posthog.com

## Current Infrastructure
![Infra Diagram](https://uc1bb21bf621abf8f7adafced790.previews.dropboxusercontent.com/p/thumb/ABEhGjy-h7xVH8ciFB_5alLkQMYP0iFfrcvjv5T7ESkuL4_J5elgKPVa0L2bnpG1VFLfDYoT0LE1qy-opLHLAnnTZyzemmZ_1HbghXcD32clAZi-ySOtTb2qtuctlo3MXQ-sU4wDI5kQqEUeo_fgI6avg-YUevkwR9l4AVPImIU0TVC9UcaYKsUaDjVG63p7396uIawIrePX3PpZdqYYKNxuhzJ7Q6KtVsUWC4XlhzdMWHCQHZCcZjV8-MYk6CwlcDYasU3H2jsIjHnetMBVZCVDOpr5taPEtQSKJNTRUDRJBcpuHFUdqf9nQjC_UKhR3P1Wwq1AAH-2GZB6qn841NhaWK77dis0UVhYkuNMZztaAOK6XvcVMWBcEQyRCMQITlrqfq5VNZUAHUWzN3H4OrkK/p.png?size=2048x1536&size_mode=3)

## Structure

The main repo is pulled using the script into the `/deploy` folder. The contents of `multi_tenancy` & `messaging` are then added into `/deploy` (if on development, folders are symlinked instead of copied so changes are updated automatically in both locations). We also use `multi_tenancy_settings.py` & `requirements.txt` to introduce a few changes to the base code.

## Developing locally

> Please note running locally now **requires Clickhouse. Tests will NOT PASS if Clickhouse is not available.**

Below you'll find the recommended steps to run locally. While running everything on Docker is possible (see [developing locally](https://posthog.com/docs/developing-locally) for the main repo), this would require more setup.

1. Set up a virtual environment (sample code below).
   ```bash
   python3 -m venv env
   ```
1. Run `bin/develop`. If you need to develop relative to a main repo branch other than `master`, pass branch name as command line argument, like so:
   ```
   bin/develop some-branch
   ```
1. Load the sample environment variables by running,
   ```bash
   source .env.template
   ```
1. Run Clickhouse (and dependencies) using Docker,
   ```bash
   docker-compose -f deploy/ee/docker-compose.ch.yml up clickhouse kafka zookeeper
   ```
1. You can run the server by running,
   ```bash
   cd deploy && bin/start
   ```
1. **Alternatively**, you can just run the local tests by doing
   ```bash
   python manage.py test multi_tenancy messaging --exclude-tag=skip_on_multitenancy
   ```

Origin repo test suite can be run doing

```bash
python manage.py test posthog --exclude-tag=skip_on_multitenancy
```

Any file on the `multi_tenancy/` or `messaging/` folder will automatically be updated on your working copy at `/deploy`. Please note however that any change to `requirements.txt` or `multi_tenancy_settings.py` **requires manually running `bin/develop` again**.

## Environment variables

Below is the documentation for the environment variables specifically scoped to this project. For the environment variables applicable to the main repo please visit the [docs](https://posthog.com/docs/configuring-posthog/environment-variables).

- `STRIPE_API_KEY`. Secret API key for Stripe. For security reasons only restricted keys should be used.
- `STRIPE_PUBLISHABLE_KEY`. Publishable API key for Stripe to generate checkout sessions.
- `STRIPE_WEBHOOK_SECRET`. Secret to verify webhooks indeed come from Stripe.
- `BILLING_TRIAL_DAYS`. Number of days (integer) to set up a trial for on each new metered or tiered-based subscription. Can be set to `0` for no trial.

## Questions?

### [Join our Slack community.](https://join.slack.com/t/posthogusers/shared_invite/enQtOTY0MzU5NjAwMDY3LTc2MWQ0OTZlNjhkODk3ZDI3NDVjMDE1YjgxY2I4ZjI4MzJhZmVmNjJkN2NmMGJmMzc2N2U3Yjc3ZjI5NGFlZDQ)
