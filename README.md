# PostHog production

This repository is used to run our own production cluster of PostHog (app.posthog.com). It enables anyone to sign up to an account and create a new team, 

NOTE: This repository is copyrighted, unlike our [main repo](https://github.com/posthog/posthog). You're not allowed to use this code to host your own version of app.posthog.com.

## Structure

We pull in our main repo using the script into the `/deploy` folder. We then copy in the contents of `multi_tenancy` into `/deploy`. We also use `settings.py`, which has a few changes to the open source, mainly adding this new `multi_tenancy` app.

## Developing locally

1. Run `docker-compose -f docker-compose.dev.yml up`
