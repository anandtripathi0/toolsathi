# Deployment

For the existing **anandtrip22** free account and `https://anandtrip22.pythonanywhere.com/`, follow [PYTHONANYWHERE_FREE_DEPLOY.md](PYTHONANYWHERE_FREE_DEPLOY.md). It includes the account-specific scripts, private environment loading, platform WSGI template, static mapping, storage limits and safe update procedure. [GOOGLE_SEO_SETUP.md](GOOGLE_SEO_SETUP.md) covers ownership verification after deployment. The notes below are for other installations.

## Local operation — no paid services

The README's virtualenv, pip, migrate and runserver commands run the full app with SQLite. Python, Django, the tool libraries and Android source are free. A public service additionally needs a running host, network access and HTTPS. No account, host or domain was created during this build.

## Small production installation

Use Python 3.12+ in a virtual environment, a dedicated service account and a private persistent application directory. Install the pinned requirements. Set these environment variables through your service manager or hosting dashboard:

```text
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<a newly generated random secret of at least 50 characters>
DJANGO_ALLOWED_HOSTS=<your exact hostname>
SITE_URL=https://<your exact hostname>
TRUST_PROXY_HTTPS=false
RESULT_DIR=<private ephemeral directory outside the web root>
APK_DIR=<directory containing verified artifacts>
```

Generate the secret directly into private configuration using Python's `secrets.token_urlsafe(64)` without printing it; the PythonAnywhere initializer does this automatically. Keep it out of source control. `.env.example` is documentation; configure actual environment variables or explicitly select an absolute private file outside the checkout using `TOOLSATHI_ENV_FILE`. POSIX files must belong to the current user with mode `0600`. Leave `TRUST_PROXY_HTTPS=false` unless the hosting proxy is verified to replace `X-Forwarded-Proto`; trusting a user-supplied value is unsafe.

Run migrations and collectstatic, then run deployment checks:

```sh
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy --fail-level WARNING
python -m waitress --listen=127.0.0.1:8000 --threads=2 config.wsgi:application
```

Terminate TLS with a trusted reverse proxy or hosting platform. Restrict direct access to the application port. Set the proxy's upload body limit to 22 MiB and a practical request timeout. WhiteNoise serves compressed, versioned static assets. HTTPS cookies and one-year HSTS apply in production; set these only on an HTTPS-ready hostname you control.

On a host that actually provides a scheduler, schedule cleanup using your virtualenv and project working directory. New PythonAnywhere free accounts do not include scheduled tasks; use the request-triggered cleanup and manual maintenance described in the account guide. Example for a Linux host with cron:

```cron
* * * * * cd /srv/toolsathi && /srv/toolsathi/.venv/bin/python manage.py cleanup_results >> /dev/null 2>&1
```

Also run Django `clearsessions` periodically. On Windows, create a Task Scheduler task for the same cleanup command using the service account. Do not back up the result directory. Session-bound links expire after ten minutes even if cleanup has not yet run, but expired bytes stay on disk until cleanup runs or another processing request removes them.

For PostgreSQL, configure `DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE` and require TLS according to your provider (for example `?sslmode=require`). Keep database credentials in environment secrets. A database backup contains optional account hashes, sessions and tool IDs, not tool inputs. Treat backups as private. SQLite is suitable for a small single instance with persistent disk; avoid running SQLite on ephemeral storage for durable accounts.

The supplied synchronous worker has bounded inputs/outputs but is not a hardened distributed file-processing service. For high traffic or hostile uploads, isolate workers with CPU, memory and execution-time limits, cap concurrency, monitor availability/storage, and add an edge rate limiter. The application intentionally ignores arbitrary forwarded client-IP headers. Behind a shared proxy, its fallback IP bucket may group clients together; use a trusted edge limiter and configure an appropriate architecture before scaling.

## Free-tier options and limits

**PythonAnywhere:** its current free account includes one web app/worker with an expiry/renewal policy. Check its [free account features](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/) and [available Python versions](https://help.pythonanywhere.com/pages/PythonVersions/) before choosing it. Account system images differ; select Python 3.12 or later. Resource, storage and outbound-network limits apply. The application itself does not need outbound API calls during normal operation.

1. Use the existing `anandtrip22` account and the account-specific guide above. Do not create another account. Keep local environments, runtime files, databases and secrets out of source uploads.
2. In its console create a virtualenv, install `requirements.txt`, and set the production environment values.
3. Create a manually configured Python web app using that virtualenv. In the platform's WSGI configuration add the project path to `sys.path`, set the production variables, then import `application` from `config.wsgi`.
4. Run migrations, collectstatic and `check --deploy` with the same environment. Enable HTTPS for the assigned hostname; set `SITE_URL` and `DJANGO_ALLOWED_HOSTS` to it. The platform may serve `/static/` directly from `staticfiles/`, or use WhiteNoise.
5. Keep SQLite/artifacts in private persistent storage. Configure the cleanup cadence your plan actually supports. If minute-level scheduled cleanup is unavailable, request-triggered cleanup still removes expired output on the next tool run, but **do not claim guaranteed ten-minute deletion**. For stricter retention choose a host that can schedule cleanup.
6. Monitor resource limits and renew the web app when required. Verify uploads, anonymous downloads, optional login, secure cookies and mobile behavior on the actual HTTPS origin.

**Render free web services:** these can run Python with the same install/migrate/collectstatic/start flow, but they currently sleep after 15 minutes of inactivity and use an ephemeral filesystem. SQLite accounts and APK files written at runtime can disappear on restart/redeploy. They are suitable for temporary evaluations only unless you separately provide durable storage/database/artifact handling. Do not call ephemeral SQLite durable production hosting. See [Render's free service limits](https://render.com/docs/free) and [filesystem/deploy behavior](https://render.com/docs/deploys).

Free tiers change and can impose quotas, account requirements, expiry, sleeping, bandwidth restrictions or paid upgrades. No free host was provisioned or tested in this delivery; verify current terms before committing. Running locally requires none of these services.

## APK artifacts

Build against the real HTTPS origin after the website is deployed. Release-sign with secrets outside the repository. Use `publish_apk` as documented in ANDROID.md, then deploy both the resulting APK and `release.json` into `APK_DIR`. This directory must survive redeployments if you promise a stable download. Files need not be mapped to a public static directory: Django verifies the artifact's SHA-256 and serves the anonymous endpoint with the required MIME and attachment headers.

At high download volume, serve the verified artifact through your own static artifact host/CDN, preserving the exact checksum/version and APK response headers. Explicitly update the route/configuration and re-test it; the current implementation serves directly through Django. No missing file is linked when the verified artifact is absent.

## Release checks

Run the Python tests and deployment checks, verify migrations and static files, browse the real HTTPS domain on mobile/desktop, process/download images and PDFs anonymously, inspect the sitemap/canonical URLs, confirm cleanup and persistence, and test the Android release on devices. Keep dependencies patched; pins reproduce this build, not future security updates. Neither a passing framework check nor a valid APK signature replaces operational testing.
