# ToolSathi

**Every Tool. One Place.** A working Python/Django toolkit with 83 tools, a white responsive interface, optional accounts, and Android source.

## Delivery status

- **83 working tools:** 30 developer, 12 image, 8 PDF, 10 text, 7 SEO, 9 CSS/design and 7 everyday utilities. See [the complete catalog](docs/TOOLS.md).
- Anonymous processing, copying and downloads. No payment, subscription, paid API or forced account.
- Fuzzy search, aliases, keyboard autocomplete, Ctrl/Cmd+K palette, categories, favorites and recent tool IDs.
- Fourteen lightweight tools run locally in the browser, including passwords, JWT decoding, hashes and JSON formatting. Python handles the other tools and file transformations.
- Optional Django signup/login, favorite synchronization and explicit opt-in recent-tool synchronization.
- PWA manifest, install prompt on supported browsers, static asset caching and an offline fallback.
- **Android source is supplied; no APK was generated.** Its target is `https://anandtrip22.pythonanywhere.com/`. JDK/Android SDK installation, private release signing and device acceptance remain required. The app page honestly says “Android app coming soon” until a verified release is published.
- **PythonAnywhere deployment is prepared.** The target is [anandtrip22.pythonanywhere.com](https://anandtrip22.pythonanywhere.com/), using the existing free account. See [the exact deployment guide](docs/PYTHONANYWHERE_FREE_DEPLOY.md). Preparation and local tests do not establish that the public site is running ToolSathi; check the deployment report for observed status.

This is implemented software, with automated and browser checks; it is not a certification of every production workload. Android compilation/device tests and live hosting acceptance remain outstanding.

## Run locally

Use Python **3.12 or newer supported by Django 6.1**. Django is pinned to 6.1.2, the stable release checked on October 19, 2026, along with the installed dependency versions. No Node.js build is needed for the website. SQLite is the default.

PowerShell, from this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Open <http://127.0.0.1:8000/>. On macOS/Linux use `.venv/bin/python` instead. To create an optional administrative account, run `python manage.py createsuperuser` using the same virtual environment.

`.env.example` documents environment variables. Merely copying it to `.env` does **not** load it. Set process variables, or explicitly set `TOOLSATHI_ENV_FILE` to a private absolute file outside the checkout; `manage.py` and WSGI load that file using the standard-library parser. On POSIX it must belong to the current user with mode `0600`. The PythonAnywhere scripts create `/home/anandtrip22/.toolsathi.env` securely without printing its secret.

## Tools and architecture

```text
config/                 Django settings, URL routing, WSGI/ASGI
apps/core/              Home, policies, PWA, common security middleware
apps/tools/             Central registry, search, tool pages and processing API
apps/accounts/          Optional accounts, ID-only preferences, rate buckets
apps/downloads/         Session-bound temporary results and verified APK delivery
apps/seo/               Public sitemap and robots.txt
tools_logic/            Python text, image and PDF handlers
templates/              Django pages and partials
static/                 CSS, vanilla JavaScript, vendored HTMX/Lucide, examples
android/                Kotlin WebView app and genuine Gradle wrapper
tests/                  Django/unittest tests and Playwright browser checks
docs/                   Catalog, deployment, Android, verification
```

The central registry supplies names, IDs/slugs, categories, icons, descriptions, aliases, input controls, examples, instructions, FAQs, processing handlers, extensions, SEO metadata and related tools. To add a tool, add its registry entry and bounded processor, then test its example and invalid inputs. Only entries with `status="available"` enter the directory/search/sitemap. The registry has no hard limit and supports 100+ tools without route duplication.

Each tool has an indexable URL such as `/tools/json-formatter/`. Server-backed processing uses `POST /api/tools/<slug>/process/` with Django CSRF protection; text results and file results offer appropriate downloads. File examples are genuine generated sample PNG/JPEG/WebP/PDF files, not user data. PDF split returns a ZIP of single-page PDFs. Reordering requires every original page exactly once. Image conversion strips image metadata; metadata tools deliberately expose the metadata of the uploaded file.

The HTML/CSS playground and Markdown preview use an opaque-origin, script-disabled sandbox with a restrictive content policy. They do not execute code on the server. JWT decoding explicitly does **not** verify signatures. The frontend keeps inputs/results in page memory, never in localStorage or analytics. Generated passwords use browser cryptographic randomness; the API fallback uses Python `secrets` and does not persist its result.

## Limits, storage and privacy

- Maximum 20 uploads and 20 MiB total per request; JPEG, PNG, WebP or genuine unencrypted PDFs according to the tool.
- Image limit: 25 million pixels per image/output. Combined images-to-PDF limit: 50 million pixels. Animation is rejected explicitly.
- PDF limit: 200 pages combined. Generated image/PDF/ZIP buffers fail while writing when they exceed 30 MiB.
- Text input is bounded at 200,000 characters per field and 220,000 total request characters. Regex evaluation has a 50 ms timeout. YAML aliases/custom tags and unsafe XML constructs are rejected.
- Server processing: 30 requests/minute per source IP. Account/admin login/signup: 10 attempts per 5 minutes. These counters are database-backed and shared across workers; IPs are hashed with the application secret. The PythonAnywhere deployment uses its documented `X-Real-IP` header only when `TRUST_PYTHONANYWHERE_PROXY=true`; other deployments default to the connection address and ignore forwarded headers.
- Uploads use Django's temporary upload lifecycle and are closed/deleted at request completion. Results live outside static files, use random names, are tied to the originating Django session and expire after 10 minutes. A cross-process lock enforces a 256 MiB result-storage quota.
- Expired output files are removed when the next result is saved or by `python manage.py cleanup_results`. Expiry denies access immediately; idle files remain until cleanup actually runs. New PythonAnywhere free accounts have no scheduled tasks: use request-triggered cleanup and manual maintenance without promising deletion at exactly ten minutes. Other hosts may schedule cleanup. Exclude result files from backups/log collection.
- Browser-generated password/JWT/hash results are not stored on the server, including the corresponding direct API responses. Other generated Python outputs may contain submitted text and therefore use the same private temporary-result policy.
- No advertising trackers or behavioral analytics are included. Third-party static libraries are vendored locally with source URLs, checksums and license texts.

For large-scale public hosting, run file processing in resource-limited workers/containers with enforced memory/CPU/request-time limits and a reverse-proxy upload limit. The current synchronous deployment is intended for small installations. File-format parsing is not malware scanning or document sanitization; PDF downloads retain page content from the supplied documents.

## Production and free hosting

Start with [the PythonAnywhere free deployment guide](docs/PYTHONANYWHERE_FREE_DEPLOY.md) for this account, and [Google Search Console setup](docs/GOOGLE_SEO_SETUP.md) after the site is live. See [deployment notes](docs/DEPLOYMENT.md) for other WSGI installations. The free deployment caps temporary results at 32 MiB and keeps APKs separately. Free hosting has resource, storage, bandwidth and availability limits.

Production settings require `DJANGO_DEBUG=false`, a strong `DJANGO_SECRET_KEY`, explicit `DJANGO_ALLOWED_HOSTS`, and an HTTPS `SITE_URL`. They enable secure cookies, HTTPS redirection and HSTS. `TRUST_PROXY_HTTPS=true` is only appropriate behind a proxy that strips/replaces the incoming forwarded-protocol header. Do not expose Django's development server publicly.

```powershell
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy --fail-level WARNING
```

Keep SQLite on persistent private storage for a small single-instance installation. Set `DATABASE_URL` to PostgreSQL when desired; the code/migrations are compatible, but no PostgreSQL server was available for integration testing here. Result files need a shared filesystem with working locks and a consistent secret/session database if multiple workers/instances handle the same users.

## Android and real APK downloads

Read [ANDROID.md](docs/ANDROID.md) for the complete commands, security model and device acceptance tests. The wrapper JAR and distribution checksum are genuine and verified. JDK 17 and Android SDK 36/build tools are required.

```powershell
cd android
$env:TOOLSATHI_SITE = 'https://anandtrip22.pythonanywhere.com/'
.\gradlew.bat "-PTOOLSATHI_URL=$env:TOOLSATHI_SITE" testDebugUnitTest lintDebug assembleDebug
```

A successful debug build creates `android/app/build/outputs/apk/debug/app-debug.apk`. This location does **not** exist as a built APK in this delivery. For a release, set the four signing environment variables documented in ANDROID.md and run `assembleRelease`. Never commit signing secrets or private keys.

Publish a tested release from the project root:

```powershell
python manage.py publish_apk .\android\app\build\outputs\apk\release\app-release.apk --version 1.0.0 --apksigner "$env:ANDROID_HOME\build-tools\35.0.0\apksigner.bat"
```

The command checks the APK archive, release signature, actual package/version and debuggable flag using `apksigner` and sibling `aapt`. It writes `artifacts/toolsathi-latest.apk` and `artifacts/release.json` (or your configured `APK_DIR`). Deploy both together. `/download-app/` will then show its actual version, size and SHA-256, and `/downloads/toolsathi-latest.apk` will anonymously return the APK MIME type plus `Content-Disposition: attachment; filename="ToolSathi.apk"`.

## Verification

```powershell
python manage.py test tests
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
python -m compileall -q apps config tools_logic tests
python android/verify_source.py
```

Browser checks require Node.js and the optional Playwright package **only for testing**, not to run/build the website. Install Playwright in a separate development environment, install its Chromium browser, start Django, then run `node tests/browser.cjs`. `BASE_URL`, `BROWSER_CHANNEL`, `PLAYWRIGHT_MODULE` and `QA_OUTPUT` can override the local server/browser/module/output directory.

See [VERIFICATION.md](docs/VERIFICATION.md) for executed checks and outstanding acceptance work. Android compilation and device behavior are explicitly unverified until the SDK build is run. HTTPS hosting and production load/backup monitoring remain deployment responsibilities.
