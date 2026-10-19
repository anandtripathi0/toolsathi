# Verification report

Verified locally on October 19, 2026 with Python 3.12.14, Django 6.1.2 and the pinned dependencies. The website uses Django, not a Node framework. Node/Playwright were used only for browser QA.

## Passed

- **59 Python/Django tests** (`python manage.py test tests`). Tests include every one of the 63 non-file tool examples, targeted JSON/CSV/YAML/XML/encoding/date/crypto/Unicode/SEO/design checks, malformed inputs, regex timeout, CSV formula neutralization, all image transformations and all PDF operations.
- Public anonymous page/access checks for all 83 tool URLs and all category/static pages. Optional signup, dashboard, preferences, opt-in history, logout and continued anonymous access.
- Image upload and generated download headers, session isolation, expired result cleanup, quota rejection, CSRF enforcement, rate limits, no password/hash result persistence, preserved restrictive download CSP, API validation, search aliases/typos, sitemap and robots.
- APK-unavailable state and HTTP transport header tests. The APK transport test uses an explicitly synthetic temporary fixture with the artifact-validation function mocked; **it does not build or validate a real APK** and is not distributed as an artifact.
- Django system checks: no issues. Migration drift check: no changes detected.
- `collectstatic` succeeds both with development settings and production compressed/manifest storage. JavaScript syntax checks pass for the three application scripts. Python compileall passes.
- `check --deploy --fail-level WARNING` succeeds with secure production environment variables and a temporary random test secret.
- Production-mode smoke test: HTTPS home, canonical URL, secure CSRF cookie, HSTS and all four manifest-versioned page assets return correctly.
- Android source-only verification: seven XML files, resource references, INTERNET-only permission, HTTPS/backup policy and genuine Gradle wrapper/distribution checksum pass.

## Browser checks

The final `tests/browser.cjs` run passed in headless Microsoft Edge through Playwright:

1. Homepage and eight working popular-tool cards.
2. Alias autocomplete, arrow-key selection and Enter navigation.
3. Ctrl+K palette and typo search.
4. Browser-only JSON formatting, preserved large integer lexemes and real JSON download.
5. Favorites and recent tool IDs in localStorage.
6. HTMX directory filtering updates both results and count.
7. Ten representative local/server tools produce downloadable results.
8. Password/JWT/hash inputs are not submitted to the server from the UI.
9. HTML preview uses a script-disabled sandbox and cannot modify the parent page.
10. Image upload, resize, decoded image preview and real download.
11. **All 20 image/PDF tools process the included genuine sample files through the UI.**
12. Tool contents are absent from localStorage.
13. APK absence displays “coming soon” with no broken APK link.
14. **25 route/viewport combinations** have no horizontal overflow: home, directory, JSON tool, image tool and app page at 360, 390, 768, 1024 and 1440 pixels.
15. Mobile navigation, reduced-motion behavior and service-worker offline fallback.
16. No uncaught JavaScript errors.

Desktop/mobile screenshots were visually inspected. Browser tests are representative functional checks, not exhaustive accessibility certification. The browser-generated output bridge requires separate Android device testing.

## Fixes found during verification

- Enforced PDF/ZIP output limits during writes to prevent shared PDF resources from amplifying the result in memory before validation.
- Serialized temporary-storage quota checks/writes across processes.
- Preserved the strict result-download content security policy instead of overwriting it with the general page policy.
- Added actual APK package/version/debuggable inspection with `aapt` before publication.
- Corrected Unicode text handling and malformed-input validation, and added real file examples.
- Removed a vendored Lucide source-map directive whose target was not shipped, allowing production manifest asset processing. Vendor provenance/checksums record this local change.

## Not run / remaining acceptance

- **No APK exists.** `gradlew.bat --version` fails because the environment lacks Java; Android SDK/emulator/device tools were also unavailable. Kotlin compilation, Gradle lint/JVM tests, APK signing/install and real-device WebView/file-picker/download tests remain unrun. The supplied commands in ANDROID.md are the next steps on a configured build machine.
- No live domain or hosting account was configured, so no public deployment or production HTTPS end-to-end test was performed.
- PostgreSQL compatibility is configured, but tests ran against SQLite because a PostgreSQL server was not available.
- High-concurrency/load testing, adversarial file-parser fuzzing, external penetration testing, host monitoring, backup recovery and a formal accessibility audit were not performed. The synchronous file processor needs deployment-level resource isolation before high-traffic operation.
- Optional accounts intentionally do not include email verification, email password-reset delivery or OAuth; the requested Django signup/login and preference synchronization are implemented without external mail services.
- PWA installation UI depends on browser support. The service worker offers an offline fallback; it does not promise that every tool works offline.

No requested tool is a placeholder or intentionally unpublished. Android release production and public hosting are the outstanding delivery steps, with honest availability states in the application.
