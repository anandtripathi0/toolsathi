# Android build, verification and publication

## Current delivery status

The `android/` directory is a genuine Kotlin / Android Gradle project with the official Gradle wrapper JAR and scripts. **There is no generated APK in this delivery.** The build prerequisite check (`android/gradlew.bat --version`) failed because Java is not installed or on `PATH`; no Android SDK, emulator or connected device was found in the checked locations. The website must retain its **Android app coming soon** state until a verified signed artifact is published.

A deployed ToolSathi HTTPS origin is required. No invented production hostname is embedded in the app. You must supply `-PTOOLSATHI_URL=https://<your-real-domain>/`; the angle-bracket text is a placeholder to replace. The property accepts an HTTPS origin at port 443 with no username, password, query, fragment or subpath, and rejects localhost and reserved example/test hostnames. The build validates the URL format; the operator must verify deployment and domain ownership.

The source includes launcher and splash assets, Android back navigation, native offline/retry UI, single and multiple document/image picking, native downloads and the browser-file bridge. Runtime behavior has **not** been verified on an Android device in this environment.

## Build prerequisites

Install Android Studio or the Android command-line SDK on your build machine. Use JDK 17, Android SDK platform 36, SDK build tools 35.0.0 and platform-tools. Set `JAVA_HOME` to JDK 17 and `ANDROID_HOME` to your SDK, or use an ignored `android/local.properties` file containing `sdk.dir=...`. Accept the SDK licenses using your SDK manager. Internet access is required for the initial Gradle/plugin/library downloads.

Pinned build components are Gradle 8.13, Android Gradle Plugin 8.13.2 and Kotlin 2.3.10. The project compiles/targets API 36 and supports API 29+. Android's [AGP compatibility documentation](https://developer.android.com/build/releases/agp-8-13-0-release-notes) and Kotlin's [compatibility table](https://kotlinlang.org/docs/gradle-configure-project.html) describe these requirements. The wrapper JAR and distribution hashes can be checked against [Gradle's checksum list](https://gradle.org/release-checksums/).

The wrapper JAR SHA-256 is:

```text
81a82aaea5abcc8ff68b3dfcb58b3c3c429378efd98e7433460610fecd7ae45f
```

The wrapper also verifies the Gradle 8.13 binary distribution SHA-256 on download. Dependency versions are pinned, but a byte-for-byte reproducibility guarantee has not been established; repeat builds still need the same JDK/SDK/toolchain and signing inputs.

## Debug checks and APK

In PowerShell, set the real deployed origin in the current terminal, then run from `android/`:

```powershell
$env:TOOLSATHI_SITE = 'https://REPLACE-WITH-YOUR-DEPLOYED-DOMAIN/'
.\gradlew.bat --version
.\gradlew.bat "-PTOOLSATHI_URL=$env:TOOLSATHI_SITE" testDebugUnitTest lintDebug assembleDebug
```

On macOS/Linux:

```sh
cd android
export TOOLSATHI_SITE='https://REPLACE-WITH-YOUR-DEPLOYED-DOMAIN/'
chmod +x gradlew
./gradlew "-PTOOLSATHI_URL=$TOOLSATHI_SITE" testDebugUnitTest lintDebug assembleDebug
```

After a successful build, the debug artifact is `android/app/build/outputs/apk/debug/app-debug.apk` with package `com.toolsathi.app.debug`. Install it for testing with `adb install -r <path-to-app-debug.apk>`. **Do not publish a debug APK as the public release.** JVM tests exercise HTTPS origin, credential, scheme and filename validation. Lint and JVM tests were supplied but could not run here without Java/SDK.

## Sign a release

Create a release keystore once on your secure build machine, outside this repository. Preserve it and its passwords in a secure backup: future app updates must retain the same signing identity. `keytool` prompts for passwords so they do not need to appear in shell history:

```sh
keytool -genkeypair -v -keystore /secure/path/toolsathi-release.jks -alias toolsathi -keyalg RSA -keysize 3072 -validity 10000
```

Set these environment variables through your CI secret store or a secure local session:

| Variable | Meaning |
| --- | --- |
| `TOOLSATHI_KEYSTORE` | Absolute keystore path |
| `TOOLSATHI_STORE_PASSWORD` | Keystore password |
| `TOOLSATHI_KEY_ALIAS` | Signing key alias |
| `TOOLSATHI_KEY_PASSWORD` | Private-key password |

Never commit signing keys, passwords, `local.properties`, secret environment files or CI logs containing secrets. The Android `.gitignore` excludes common signing files. Release packaging refuses to proceed unless all signing variables are present. It never silently substitutes a debug key.

Increment `versionCode` and `versionName` in `android/app/build.gradle.kts` for updates. Then run:

```powershell
cd android
.\gradlew.bat "-PTOOLSATHI_URL=$env:TOOLSATHI_SITE" testDebugUnitTest lintRelease assembleRelease
```

Expected output **after successful completion**: `android/app/build/outputs/apk/release/app-release.apk`, package `com.toolsathi.app`. This path is a build destination, not an artifact currently present.

Verify with the Android SDK tools before distribution:

```powershell
& "$env:ANDROID_HOME\build-tools\35.0.0\apksigner.bat" verify --verbose --print-certs .\app\build\outputs\apk\release\app-release.apk
& "$env:ANDROID_HOME\build-tools\35.0.0\aapt.exe" dump badging .\app\build\outputs\apk\release\app-release.apk
Get-FileHash .\app\build\outputs\apk\release\app-release.apk -Algorithm SHA256
adb install -r .\app\build\outputs\apk\release\app-release.apk
```

Confirm the certificate is your release certificate, the package/version are correct, and the APK opens your actual HTTPS website. A valid signature alone does not establish app quality or successful runtime testing.

## Publish through Django

From the repository root, after verifying and testing the signed release, run:

```powershell
python manage.py publish_apk .\android\app\build\outputs\apk\release\app-release.apk --version 1.0.0 --apksigner "$env:ANDROID_HOME\build-tools\35.0.0\apksigner.bat"
```

The publisher verifies the signature using `apksigner`, rejects a debug signer, checks APK archive contents, reads the actual package/version with the SDK's sibling `aapt` executable, rejects debuggable builds and version mismatches, computes SHA-256 and installs `toolsathi-latest.apk` plus release metadata in `APK_DIR` (default `artifacts/`). Publish the exact file you tested. Set `APK_DIR` to a durable storage path on your server if the deployment filesystem is ephemeral. Run the publisher on a controlled machine with the Android SDK; deploy both generated artifact and metadata together.

The anonymous URL `/downloads/toolsathi-latest.apk` uses `application/vnd.android.package-archive` and attachment filename `ToolSathi.apk`. `/download-app/` displays version, size, checksum and installation instructions only when the artifact and verified metadata pass validation. Verify this on your real HTTPS deployment using an Android browser, not only a desktop request. The app does not request permission to install packages; installation is the device/browser's normal explicit flow.

## File transfer and origin boundaries

Only the configured HTTPS origin stays inside the WebView. User-initiated external HTTPS navigation opens the system browser. Plain HTTP, `file:`, `content:`, `javascript:`, `intent:` and custom-scheme navigation are blocked; the native system picker separately grants read access to the files the user chooses. Camera, location, contacts, broad storage access and package-install permissions are not requested. The only manifest permission is `INTERNET`.

SSL errors are always cancelled. Mixed content and arbitrary file access are disabled. Third-party cookies are disabled; first-party Django session/CSRF cookies work. Backups and activity form-state persistence are disabled. Updating Android System WebView is important for browser features and security fixes. The app does not implement a custom certificate exception or a JavaScript interface with broad native access.

The public APK download uses Android `DownloadManager` without cookies or authorization headers. Session-bound tool results use an HTTPS GET to the exact trusted origin, with the first-party session cookie, **redirects disabled**, bounded timeouts and a 64 MiB output cap. They stream into `Downloads/ToolSathi` through Android's scoped `MediaStore`. This avoids forwarding session cookies through `DownloadManager` redirects. Failed partial files are removed. Large native downloads require the app process to remain alive; retry a failed download when needed. The backend's result links must return the file directly rather than redirect elsewhere.

For browser-generated files, the frontend detects `window.ToolSathiAndroid.postMessage` and sends:

```javascript
ToolSathiAndroid.postMessage(JSON.stringify({
  type: 'saveFile',
  id: 'a-unique-request-id',
  filename: 'result.json',
  mime: 'application/json',
  base64: 'base64-encoded-bytes-without-a-data-url-prefix'
}));
ToolSathiAndroid.onmessage = (event) => {
  const result = JSON.parse(event.data);
  // Match result.id to the request. Success is only result.ok === true.
};
```

Register the response handler before posting. Responses contain `{id, ok, filename}` or `{id, ok:false, error}`. The bridge uses AndroidX `WebViewCompat.addWebMessageListener` restricted to the exact configured origin; native code also checks the main frame and current page origin. It accepts string messages, caps browser-generated output at 8 MiB, sanitizes filenames, writes via `MediaStore` and permits one active save. Unsupported older WebView engines do not receive this bridge; the site retains ordinary browser downloads and the native app asks users to update WebView if a raw blob URL reaches its download handler. See the [AndroidX API contract](https://developer.android.com/reference/androidx/webkit/WebViewCompat#addWebMessageListener(android.webkit.WebView,java.lang.String,java.util.Set%3Cjava.lang.String%3E,androidx.webkit.WebViewCompat.WebMessageListener)).

## Device acceptance checks before release

- Test API 29 and a current Android release, narrow portrait and landscape screens, keyboard/insets, back navigation, launcher and cold-start splash.
- Open tools without signing in. Select one image, multiple PDF documents, cancel a chooser, submit uploads, copy output, and save browser-generated JSON/text plus server-generated image/PDF files.
- Verify filenames/content and visible Downloads entries. Check denied/expired result links and a file above the configured size limit.
- Enable airplane mode and reload, use retry after reconnecting, and test a server error. Inspect that a bad certificate never proceeds.
- Open a trusted tool, external HTTPS link and blocked custom/HTTP link. Test that an external or embedded frame cannot invoke the download bridge or obtain the Django cookie.
- Optionally sign in/out, confirm CSRF-protected flows work, clear app data and verify no tool inputs return. Favorites/tool IDs may persist in localStorage; sensitive inputs must not be persisted by the website.
- Run `apksigner`, verify the release certificate and SHA-256, install the release and test the deployed public APK endpoint anonymously.

For source-only validation without SDK, run `python android/verify_source.py`. It validates XML/resource references, minimal permissions, HTTPS/backup policy and official wrapper integrity. It intentionally reports compilation/device tests as not run.
