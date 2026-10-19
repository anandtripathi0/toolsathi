import java.net.URI

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val siteUrl = providers.gradleProperty("TOOLSATHI_URL").orNull
    ?: throw GradleException("Pass -PTOOLSATHI_URL=https://your-deployed-domain/ (a real HTTPS origin).")
val siteUri = runCatching { URI(siteUrl) }.getOrNull()
val siteHost = siteUri?.host?.lowercase().orEmpty()
val reservedHosts = listOf("localhost", "example.com", "example.org", "example.net")
require(siteUri != null && siteUri.scheme == "https" && siteHost.contains('.') && !siteHost.endsWith('.') &&
    siteUri.userInfo == null && siteUri.rawQuery == null && siteUri.rawFragment == null &&
    siteUri.path in listOf("", "/") && siteUri.port in listOf(-1, 443) &&
    reservedHosts.none { siteHost == it || siteHost.endsWith(".$it") } &&
    listOf(".invalid", ".example", ".test", ".localhost").none { siteHost.endsWith(it) } &&
    !siteHost.startsWith("127.") && siteHost != "[::1]"
) { "TOOLSATHI_URL must be your deployed HTTPS origin at port 443, without credentials, path, query or fragment." }
val normalizedSiteUrl = "https://$siteHost/"

val signingValues = listOf("TOOLSATHI_KEYSTORE", "TOOLSATHI_STORE_PASSWORD", "TOOLSATHI_KEY_ALIAS", "TOOLSATHI_KEY_PASSWORD")
    .associateWith { providers.environmentVariable(it).orNull }
val hasReleaseSigning = signingValues.values.all { !it.isNullOrBlank() }

android {
    namespace = "com.toolsathi.app"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.toolsathi.app"
        minSdk = 29
        targetSdk = 36
        versionCode = 1
        versionName = "1.0.0"
        buildConfigField("String", "SITE_URL", "\"$normalizedSiteUrl\"")
    }
    buildFeatures { buildConfig = true }
    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                storeFile = file(signingValues.getValue("TOOLSATHI_KEYSTORE")!!)
                storePassword = signingValues.getValue("TOOLSATHI_STORE_PASSWORD")
                keyAlias = signingValues.getValue("TOOLSATHI_KEY_ALIAS")
                keyPassword = signingValues.getValue("TOOLSATHI_KEY_PASSWORD")
            }
        }
    }
    buildTypes {
        debug { applicationIdSuffix = ".debug"; versionNameSuffix = "-debug" }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            if (hasReleaseSigning) signingConfig = signingConfigs.getByName("release")
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    testOptions { unitTests.isReturnDefaultValues = true }
}
kotlin { jvmToolchain(17) }

// Do not silently produce an unsigned public release or sign it with debug keys.
tasks.configureEach {
    if (name.startsWith("packageRelease") || name.startsWith("bundleRelease")) {
        doFirst {
            check(hasReleaseSigning) {
                "Release signing requires TOOLSATHI_KEYSTORE, TOOLSATHI_STORE_PASSWORD, TOOLSATHI_KEY_ALIAS and TOOLSATHI_KEY_PASSWORD environment variables."
            }
        }
    }
}

dependencies {
    implementation("androidx.activity:activity-ktx:1.10.1")
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.core:core-splashscreen:1.0.1")
    implementation("androidx.webkit:webkit:1.12.1")
    testImplementation("junit:junit:4.13.2")
}
