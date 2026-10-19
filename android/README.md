# ToolSathi for Android

Kotlin WebView source for Android 10 (API 29) and later, configured for `https://anandtrip22.pythonanywhere.com/`. No APK is included. The current machine has no JDK/Android SDK or release signing key. The target domain must serve the deployed ToolSathi application before a release is distributed.

See [the Android build and publication guide](../docs/ANDROID.md) for prerequisites, signed release commands, the web bridge contract, APK verification, publication and device checks.

The official Gradle 8.13 wrapper is included and its JAR SHA-256 has been checked. `python android/verify_source.py` can validate the resources and wrapper without Java, from the repository root. This does not compile the app.

Run `python android/build_release.py --check` for build prerequisite checks. With the toolchain and private signing variables configured, `python android/build_release.py` runs JVM tests, release lint, release assembly and APK verification. Device acceptance and publication are separate steps in the guide.
