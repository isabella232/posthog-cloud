# TODO: Standardize to use main repo's Dockerfile to avoid duplicated harder-to-maintain code
FROM python:3.8-slim
ENV PYTHONUNBUFFERED=1
ENV JS_URL='https://app-static.posthog.com'
RUN mkdir /code
WORKDIR /code

# Grab posthog from local (You must have posthog cloned here)
COPY ./deploy .

# install javascript and other system level dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends 'curl=7.*' 'git=1:2.*' 'build-essential=12.*' \
    && apt-get install -y --no-install-recommends 'pkg-config=0.*' 'libxml2-dev=2.*' 'libxmlsec1-dev=1.*' 'libxmlsec1-openssl=1.*' 'musl-dev=1.*' \
    && ln -s /usr/lib/x86_64-linux-musl/libc.so /lib/libc.musl-x86_64.so.1 \
    && curl -sL https://deb.nodesource.com/setup_14.x | bash - \
    && apt-get install -y --no-install-recommends 'nodejs=14.*' \
    && npm install -g yarn@1 \
    && yarn config set network-timeout 300000 \
    && yarn --frozen-lockfile \
    && yarn build \
    && yarn cache clean \
    && apt-get purge -y build-essential \
    && rm -rf node_modules \
    && rm -rf /var/lib/apt/lists/*

# Build plugin-server
RUN cd plugin-server \
    && yarn --frozen-lockfile --ignore-optional \
    && yarn build \
    && yarn cache clean \
    && cd ..

# Block for posthog cloud additions
COPY requirements.txt /code/cloud_requirements.txt
RUN cat cloud_requirements.txt >> requirements.txt
COPY ./multi_tenancy /code/multi_tenancy/
COPY ./messaging /code/messaging/
COPY multi_tenancy_settings.py /code/cloud_settings.py
RUN cat /code/cloud_settings.py > /code/posthog/settings/cloud.py

# install dependencies but ignore any we don't need for dev environment
RUN pip install $(grep -ivE "psycopg2" requirements.txt | cut -d'#' -f1) --no-cache-dir --compile\
    && pip install psycopg2-binary --no-cache-dir --compile\
    && pip uninstall ipython-genutils pip -y

RUN DATABASE_URL='postgres:///' REDIS_URL='redis:///' SECRET_KEY='no' python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["./gunicorn posthog.wsgi --log-file -"]
