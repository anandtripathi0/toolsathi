# Android build, verification and publication

## Current delivery status

The `android/` directory is a genuine Kotlin / Android Gradle project with the official Gradle wrapper JAR and scripts. **There is no generated APK in this delivery.** The build prerequisite check (`android/gradlew.bat --version`) failed because Java is not installed or on `PATH`; no Android SDK, emulator or connected device was found in the checked locations. The website must retain its **Android app coming soon** state until a verified signed artifact is published.

The app is configured in `android/gradle.properties` for **https://anandtrip22.pythonanywhere.com/**. This is the user's real target domain; setting it does not establish that ToolSathi is deployed. At deployment preparation, the public domain served PythonAnywhere's default page. Confirm the live ToolSathi homepage and anonymous tool processing before distributing an APK. The property accepts an HTTPS origin at port 443 with no username, password, query, fragment or subpath, and rejects localhost and reserved example/test hostnames.

The source includes launcher and splash assets, Android back navigation, native offline/retry UI, single and multiple document/image picking, native downloads and the browser-file bridge. Runtime behavior has **not** been verified on an Android device in this environment.

## Build prerequisites

Install Android Studio or the Android command-line SDK on your build machine. Use JDK 17, Android SDK platform 36, SDK build tools 35.0.0 and platform-tools. Set `JAVA_HOME` to JDK 17 and `ANDROID_HOME` to your SDK. Accept the SDK licenses using your SDK manager. The helper also requires Python 3.12+. Internet access is required for initial Gradle/plugin/library downloads. Build on a development machine or a suitable CI runner; do not install the Android SDK or compile the app on the free PythonAnywhere host.

Pinned build components are Gradle 8.13, Android Gradle Plugin 8.13.2 and Kotlin 2.3.10. The project compiles/targets API 36 and supports API 29+. Android's [AGP compatibility documentation](https://developer.android.com/build/releases/agp-8-13-0-release-notes) and Kotlin's [compatibility table](https://kotlinlang.org/docs/gradle-configure-project.html) describe these requirements. The wrapper JAR and distribution hashes can be checked against [Gradle's checksum list](https://gradle.org/release-checksums/).

The wrapper JAR SHA-256 is:

```text
81a82aaea5abcc8ff68b3dfcb58b3c3c429378efd98e7433460610fecd7ae45f
```

The wrapper also verifies the Gradle 8.13 binary distribution SHA-256 on download. Dependency versions are pinned, but a byte-for-byte reproducibility guarantee has not been established; repeat builds still need the same JDK/SDK/toolchain and signing inputs.

## Debug checks and APK

In PowerShell, run from `android/` (the real target origin is already configured):

```powershell
.\gradlew.bat --version
.\gradlew.bat testDebugUnitTest lintDebug assembleDebug
```

On macOS/Linux:

```sh
cd android
chmod +x gradlew
./gradlew testDebugUnitTest lintDebug assembleDebug
```

After a successful build, the debug artifact is `android/app/build/outputs/apk/debug/app-debug.apk` with package `com.toolsathi.app.debug`. From the repository root, install it for testing with `adb install -r android/app/build/outputs/apk/debug/app-debug.apk`. **Do not publish a debug APK as the public release.** JVM tests exercise HTTPS origin, credential, scheme and filename validation. Lint and JVM tests were supplied but could not run here without Java/SDK.

## Sign a release

Create a release keystore once on your secure build machine, outside this repository. Preserve it and its passwords in a secure backup: future app updates must retain the same signing identity. Losing a self-managed signing key prevents compatible updates. [Android signing guidance](https://developer.android.com/studio/publish/app-signing). On this Windows account, the following location is outside the repository; `keytool` prompts for passwords so they do not appear in shell history. Reuse an existing key instead of recreating it:

```powershell
$toolsathiSigningDir = 'C:\Users\tripa\AppData\Local\ToolSathiSigning'
New-Item -ItemType Directory -Path $toolsathiSigningDir -Force | Out-Null
$env:TOOLSATHI_KEYSTORE = Join-Path $toolsathiSigningDir 'toolsathi-release.jks'
if (-not (Test-Path -LiteralPath $env:TOOLSATHI_KEYSTORE)) {
    keytool -genkeypair -v -storetype JKS -keystore $env:TOOLSATHI_KEYSTORE -alias toolsathi -keyalg RSA -keysize 3072 -validity 10000
}
```

Set these environment variables through your CI secret store or a secure local session:

| Variable | Meaning |
| --- | --- |
| `TOOLSATHI_KEYSTORE` | Absolute keystore path |
| `TOOLSATHI_STORE_PASSWORD` | Keystore password |
| `TOOLSATHI_KEY_ALIAS` | Signing key alias |
| `TOOLSATHI_KEY_PASSWORD` | Private-key password |

Never commit signing keys, passwords, `local.properties`, secret environment files or CI logs containing secrets. The Android `.gitignore` excludes common signing files. Release packaging refuses to proceed unless all signing variables are present. It never silently substitutes a debug key. For a local PowerShell session, enter passwords privately:

```powershell
$env:TOOLSATHI_KEY_ALIAS = 'toolsathi'
$toolsathiStorePassword = Read-Host 'Keystore password' -AsSecureString
$toolsathiKeyPassword = Read-Host 'Key password' -AsSecureString
$env:TOOLSATHI_STORE_PASSWORD = [System.Net.NetworkCredential]::new('', $toolsathiStorePassword).Password
$env:TOOLSATHI_KEY_PASSWORD = [System.Net.NetworkCredential]::new('', $toolsathiKeyPassword).Password
```

Run commands in your private terminal without printing the environment. Close that terminal after building, or remove the four signing environment variables. Keep the key and passwords backed up securely; they are not uploaded to PythonAnywhere.

Increment `versionCode` and `versionName` in `android/app/build.gradle.kts` for updates. Then run from the repository root:

```powershell
python android/build_release.py --check
python android/build_release.py
```

The helper checks JDK 17, SDK platform/build tools and private signing inputs, then runs `testDebugUnitTest lintRelease assembleRelease`. It verifies the APK signature, rejects a debug certificate/debuggable package, checks the release package name and prints SHA-256. It does not generate a key, upload files or perform device tests. The same helper works on Linux/macOS with their SDK paths and signing variables. `--check` only checks prerequisites; a pass is not proof of compilation. If prerequisite checks fail, install/configure the reported requirements before building.

Expected output **after successful completion**: `android/app/build/outputs/apk/release/app-release.apk`, package `com.toolsathi.app`. This path is a build destination, not an artifact currently present.

Verify with the Android SDK tools before distribution:

```powershell
& "$env:ANDROID_HOME\build-tools\35.0.0\apksigner.bat" verify --verbose --print-certs .\android\app\build\outputs\apk\release\app-release.apk
& "$env:ANDROID_HOME\build-tools\35.0.0\aapt.exe" dump badging .\android\app\build\outputs\apk\release\app-release.apk
Get-FileHash .\android\app\build\outputs\apk\release\app-release.apk -Algorithm SHA256
adb install -r .\android\app\build\outputs\apk\release\app-release.apk
```

Confirm the certificate is your release certificate, the package/version are correct, and the APK opens your actual HTTPS website. A valid signature alone does not establish app quality or successful runtime testing.

## Publish through Django

From the repository root on the SDK-equipped build machine, after verifying and testing the signed release, create a staging pair using the existing publisher:

```powershell
$env:APK_DIR = Join-Path (Get-Location) '.runtime\apk-release'
python manage.py publish_apk .\android\app\build\outputs\apk\release\app-release.apk --version 1.0.0 --apksigner "$env:ANDROID_HOME\build-tools\35.0.0\apksigner.bat"
```

The publisher verifies the signature using `apksigner`, rejects a debug signer, checks APK archive contents, reads the actual package/version with the SDK's sibling `aapt` executable, rejects debuggable builds and version mismatches, computes SHA-256 and installs `toolsathi-latest.apk` plus `release.json` in the staging directory. Use the exact version of the APK you tested (initial version is `1.0.0`).

In [PythonAnywhere Files](https://www.pythonanywhere.com/user/anandtrip22/files/), open `/home/anandtrip22/.local/share/toolsathi/apk` and upload the verified `toolsathi-latest.apk` and `release.json` from `.runtime/apk-release/`. Upload both before checking the download page; a mismatched pair is treated as unavailable. This directory is the deployed `APK_DIR`, outside the Git checkout and separate from temporary tool results. No keystore, password, SDK, debug APK or unverified artifact is uploaded. If replacing a release, retain the previous verified pair in a private backup so the prior version can be restored. Check account disk space before retaining multiple APK copies.

Run `sha256sum /home/anandtrip22/.local/share/toolsathi/apk/toolsathi-latest.apk` in the server Bash console and compare its digest with the local build/publisher output. Open [the app page](https://anandtrip22.pythonanywhere.com/download-app/) anonymously; confirm the displayed version, size and SHA-256. Download [the APK](https://anandtrip22.pythonanywhere.com/downloads/toolsathi-latest.apk) on Android and repeat installation/launch checks. Before a verified pair is present, the site displays coming soon. Report public installation as tested only after those checks succeed; restore the prior verified pair if a replacement fails acceptance.

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
