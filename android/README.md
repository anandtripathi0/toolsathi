# ToolSathi for Android

Kotlin WebView source for Android 10 (API 29) and later. No APK is included in this source delivery. The development machine did not have Java or the Android SDK, and a deployed ToolSathi URL and release signing key have not been supplied.

See [the Android build and publication guide](../docs/ANDROID.md) for prerequisites, signed release commands, the web bridge contract, APK verification, publication and device checks.

The official Gradle 8.13 wrapper is included and its JAR SHA-256 has been checked. `python android/verify_source.py` can validate the resources and wrapper without Java, from the repository root. This does not compile the app.
