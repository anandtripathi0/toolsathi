# ToolSathi on PythonAnywhere Free

Target: **https://anandtrip22.pythonanywhere.com/** in the existing **anandtrip22** account at **www.pythonanywhere.com**. Source: [anandtripathi0/toolsathi, main](https://github.com/anandtripathi0/toolsathi/tree/main). This guide does not imply the account has been accessed or that deployment has succeeded; check the deployment report and the actual website.

## Account and storage

Use the existing account; no new account, paid plan, domain, SSH access or scheduled task is required. Open [Consoles](https://www.pythonanywhere.com/user/anandtrip22/consoles/) and select **Bash**. If redirected to login, sign in yourself in the browser. Never paste passwords, session cookies, API tokens or signing secrets into chat or source control.

The [free plan](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/) has one web application/worker, 512 MiB disk space, limited CPU and outbound access, and a monthly web-app renewal requirement. New free accounts have no scheduled tasks. Review the account's own quota display and expiry date because account terms can differ. This project requires Python **3.12 or newer**; its pinned Django version is **6.1.2**. The deployment script checks installed interpreters, prefers **3.13**, then **3.12**, then newer compatible interpreters. An existing virtualenv is retained and checked; it is never deleted or replaced automatically. The Web tab's interpreter version must match the reported virtualenv version.

The project, SQLite database and virtualenv are persistent:

```text
/home/anandtrip22/toolsathi/
/home/anandtrip22/toolsathi/.venv/
/home/anandtrip22/toolsathi/db.sqlite3
/home/anandtrip22/toolsathi/staticfiles/
/home/anandtrip22/.toolsathi.env
/home/anandtrip22/.local/share/toolsathi/results/
/home/anandtrip22/.local/share/toolsathi/apk/
```

Temporary results have a **32 MiB** quota, separate from APK artifacts. Individual requests retain the existing 20 MiB upload and 30 MiB output limits, so the free tier supports only modest concurrency. The account's total quota also includes source, dependencies, SQLite, logs, caches and any other files. The script checks estimated account usage and filesystem headroom before installing, retains at least 64 MiB headroom after installation, and uses pip's `--no-cache-dir --only-binary=:all:`. It never clears existing caches or user files or compiles dependencies on the limited server. If space or a compatible pinned wheel is unavailable, inspect the account's Files quota display and pip error before deciding how to proceed. A deployment must stop rather than silently downgrade dependencies or erase data.

## First deployment

In the authenticated account's Bash console, run:

```bash
cd /home/anandtrip22
if [ ! -e toolsathi ]; then
    git clone --branch main --single-branch https://github.com/anandtripathi0/toolsathi.git toolsathi
fi
cd /home/anandtrip22/toolsathi
bash scripts/deploy_pythonanywhere.sh
```

If `toolsathi` already exists, inspect it before proceeding. The script accepts only the expected repository on `main` and refuses tracked changes. It creates or reuses `.venv`, installs pinned dependencies, initializes the private environment only if absent, validates settings and SQLite, runs migrations and `collectstatic`, runs `check --deploy --fail-level WARNING`, checks private storage permissions, and exercises homepage/sitemap/robots configuration in-process. Re-running it preserves the secret, database, user accounts, result files and APKs. It does not reload or replace the platform web app.

The initial environment contains the actual public origin and allowed host, `DJANGO_DEBUG=false`, a secret generated with Python's `secrets` module, persistent SQLite, and private result/APK paths. The file is mode `600`, outside Git. `TOOLSATHI_ENV_FILE` explicitly loads it through the standard-library parser; do **not** shell `source` the file. `.env.example` alone does not configure production. The script prints only non-secret deployment facts.

To edit a known non-secret setting later, use the Files editor for `/home/anandtrip22/.toolsathi.env` or `nano /home/anandtrip22/.toolsathi.env` in Bash. Keep the file private and never paste its full contents into logs or chat. The application uses secure session/CSRF cookies, a fixed trusted origin and HTTPS redirection in production. `TRUST_PROXY_HTTPS=false` retains PythonAnywhere's native WSGI HTTPS scheme instead of trusting a forwarded-protocol header. Separately, `TRUST_PYTHONANYWHERE_PROXY=true` uses the platform's documented [X-Real-IP client address](https://help.pythonanywhere.com/pages/WebAppClientIPAddresses/) for per-client rate limits; arbitrary `X-Forwarded-For` is ignored. Check the actual public redirect behavior after reload.

## Web tab and WSGI

Follow PythonAnywhere's [existing Django project deployment guide](https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/). Open [Web](https://www.pythonanywhere.com/user/anandtrip22/webapps/).

1. Inspect the existing `anandtrip22.pythonanywhere.com` web app. Reuse it. If none exists, choose **Add a new web app**, the existing free domain, **Manual configuration**, and the exact Python major/minor reported by the deployment script. Do not delete a web app or create a second one.
2. Set **Source code** and **Working directory** to `/home/anandtrip22/toolsathi`.
3. Set **Virtualenv** to `/home/anandtrip22/toolsathi/.venv`.
4. Under **Code**, open the actual **WSGI configuration file** link. Its real path is shown by PythonAnywhere. Inspect its current contents and save a private backup through the editor before changing it. Do not assume a `/var/www/...` filename and do not confuse this platform file with `config/wsgi.py` in Git.
5. Replace the platform file with the contents of `/home/anandtrip22/toolsathi/deploy/pythonanywhere_wsgi.py`. That template inserts the project path, explicitly loads `/home/anandtrip22/.toolsathi.env`, sets `config.settings`, and imports `config.wsgi.application`. It contains no secret values.
6. Under **Static files**, add or update only the `/static/` mapping to `/home/anandtrip22/toolsathi/staticfiles`. Do not map the repository, SQLite, private environment, result directory or APK directory to a public URL.
7. Enable **Force HTTPS** if the Web tab offers it for this existing subdomain, then select **Reload** for `anandtrip22.pythonanywhere.com`.

The PythonAnywhere subdomain uses the platform's HTTPS certificate. Do not request a custom domain or paid TLS feature. Verify HTTPS and redirection after reload. The platform WSGI template and private environment are intentionally separate from the repository's normal entry point.

## Verify the actual website

The deployment script's in-process checks do not verify the public proxy, certificate, Web tab settings or DNS. After reload, run these public requests in Bash:

```bash
curl --fail --silent --show-error --location --max-redirs 5 --output /dev/null --write-out '%{http_code} %{url_effective}\n' https://anandtrip22.pythonanywhere.com/
curl --silent --show-error --head http://anandtrip22.pythonanywhere.com/
curl --fail --silent --show-error https://anandtrip22.pythonanywhere.com/robots.txt
curl --fail --silent --show-error --output /dev/null --write-out '%{http_code}\n' https://anandtrip22.pythonanywhere.com/sitemap.xml
```

Expect HTTPS `200`, HTTP redirecting to the same HTTPS origin, and robots pointing to `https://anandtrip22.pythonanywhere.com/sitemap.xml`. Open the website in a signed-out or private browser and check:

- White grid homepage, responsive layout, CSS/JavaScript, tool directory, search and category filtering.
- `/tools/json-formatter/`, `/tools/base64-encoder-decoder/`, `/tools/image-compressor/`, `/tools/pdf-merger/` and a text tool using examples and a small disposable file.
- Anonymous processing, copy and result download; missing/invalid input errors; optional signup/login; a result link rejected in a different browser session.
- Page-source canonical/OG URLs use the public HTTPS origin; sitemap contains available tools only; no localhost canonical appears.
- Developer tools show no missing static files or JavaScript failures. HTTP requests redirect once rather than looping. Secure cookies are present where applicable.
- `/.toolsathi.env`, `/.env`, `/db.sqlite3`, `/config/settings.py` and private storage paths are not publicly served. The Android page says “coming soon” until a verified signed release is published.

For a full automated local check against the same configuration, use the script's recorded virtualenv and the private file:

```bash
cd /home/anandtrip22/toolsathi
TOOLSATHI_ENV_FILE=/home/anandtrip22/.toolsathi.env .venv/bin/python manage.py check --deploy --fail-level WARNING
TOOLSATHI_ENV_FILE=/home/anandtrip22/.toolsathi.env .venv/bin/python manage.py migrate --check
TOOLSATHI_ENV_FILE=/home/anandtrip22/.toolsathi.env .venv/bin/python scripts/pythonanywhere_support.py verify
```

The full `manage.py test tests` suite is best run locally or in CI before pushing because a free Bash console has a limited CPU allowance. Successful framework checks are not a substitute for testing the live site.

## Updates and maintenance

After tested changes reach GitHub `main`, run in Bash:

```bash
cd /home/anandtrip22/toolsathi
bash scripts/update_pythonanywhere.sh
```

The update script checks the exact origin, `main`, and tracked modifications before fetching. It accepts a fast-forward update only and then reuses the deployment routine. Its explicit `--no-overwrite-ignore` flag makes Git refuse collisions with both untracked and ignored files, including the existing `db.sqlite3`. Local commits, branch divergence or modified tracked files stop the update for review; the script never resets or force-pulls. After success, select **Reload** on the existing Web app and repeat the public checks. If an installation/check fails, inspect the error before reloading; existing workers are not deliberately restarted by these scripts. Database migrations can change persistent state, so retain an account-private backup before schema changes.

Output links expire after ten minutes. Expired bytes are removed by the next processing request; with no scheduled task, physical deletion while idle has **no fixed ten-minute guarantee**. The existing `cleanup_results` command removes only expired temporary results and can be run manually when needed:

```bash
cd /home/anandtrip22/toolsathi
TOOLSATHI_ENV_FILE=/home/anandtrip22/.toolsathi.env .venv/bin/python manage.py cleanup_results
```

Do not configure a task the free account does not provide. Do not put result files into backups. Back up the persistent SQLite database and release artifacts privately when appropriate, keep signing keys outside the server/repository, review disk/CPU usage, and use the Web tab's renewal control before the expiry shown there. This document does not create a reminder or automatic renewal.

## Troubleshooting

- **Dependency installation:** inspect the selected interpreter and `python --version`, the first pip error, account quota and allowed outbound access. Installation uses binary wheels only to avoid unexpected compilation and temporary disk use. If a pinned wheel is unavailable for the selected interpreter, inspect available account versions and plan a compatible virtualenv explicitly. No package is silently downgraded. An existing incompatible `.venv` needs a deliberate migration plan; the script preserves it.
- **WSGI error/500:** open the exact **Error log** link in the Web tab, check the project path, the private environment's existence/mode, matching Python/virtualenv and the platform WSGI file. Share only a redacted exception, never environment contents.
- **CSS/JS missing:** rerun deployment/`collectstatic`, verify `/static/` maps to the `staticfiles` directory and reload. The private `umask` must not prevent PythonAnywhere's static server from reading collected public assets; the script sets only the collected static tree to public-readable modes.
- **HTTPS redirect loop:** stop repeated reload attempts and check platform HTTPS/proxy configuration against the official [HTTPS guide](https://help.pythonanywhere.com/pages/ForcingHTTPS/). Never disable production HTTPS merely to hide a loop or trust arbitrary client headers.
- **Bad host/canonical/sitemap:** confirm the private file has the exact hostname and HTTPS origin from this guide and that the WSGI loader reads that file before Django starts.
- **Storage busy:** inspect free disk and the 32 MiB result quota. Expired outputs can be cleaned with the command above. APKs, database and other files need their own space; none is automatically removed.

## Google and Android

Follow [GOOGLE_SEO_SETUP.md](GOOGLE_SEO_SETUP.md) for the URL-prefix property `https://anandtrip22.pythonanywhere.com/`, the real issued HTML verification value, reloading and sitemap submission. Configure only Google's issued value in the private environment file. Google controls crawling/indexing and rankings.

Follow [ANDROID.md](ANDROID.md) to build locally or in an authorized CI environment against `https://anandtrip22.pythonanywhere.com/`. PythonAnywhere Free is not an Android build machine. Public delivery requires a tested, signed release; never publish a debug APK or a keystore. Run the existing `publish_apk` command on a machine with the Android verification tools, then upload the verified `toolsathi-latest.apk` and its `release.json` to `/home/anandtrip22/.local/share/toolsathi/apk/` using the account Files interface. Leave sufficient server quota for both artifacts and dependencies. The website verifies the checksum and anonymously serves `/downloads/toolsathi-latest.apk` only when valid metadata and bytes are present. Until then, `/download-app/` must retain the honest “Android app coming soon” state.
