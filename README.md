# PostHog production

This repository is used to run our own production cluster of PostHog (app.posthog.com). It enables anyone to sign up to an account and create a new team, 

NOTE: This repository is copyrighted, unlike our [main repo](https://github.com/posthog/posthog). You're not allowed to use this code to host your own version of app.posthog.com.

## Structure

We pull in our main repo using the script into the `/deploy` folder. We then copy in the contents of `multi_tenancy` into `/deploy`. We also use `settings.py`, which has a few changes to the open source, mainly adding this new `multi_tenancy` app.

## Developing locally

1. Make sure you have python 3 installed `python3 --version`
2. Make sure you have postgres installed `brew install postgres`
3. Start postgres, run `brew services start postgresql`
4. Create Database `createdb posthog`
5. Navigate into the correct folder `cd posthog`
6. Run `python3 -m venv env` (creates virtual environment in current direction called 'env')
7. Run `source env/bin/activate` (activates virtual environment)
8. Run `bin/develop_posthog`
9. Run `cd deploy` and `python manage.py runserver`
10. Run `bin/start-frontend`
11. You can now edit `/settings.py` or any files in `multi_tenancy`. They're automatically linked to `/deploy`.