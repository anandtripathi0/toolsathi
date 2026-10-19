package com.toolsathi.app

import java.net.URI

/** Shared with JVM tests so origin, credential and filename rules stay reviewable. */
internal class NavigationPolicy(siteUrl: String) {
    private val site = URI(siteUrl)
    val origin: String = "https://${site.host.lowercase()}"

    fun isTrusted(url: String?): Boolean = parseHttps(url)?.let {
        it.host.equals(site.host, ignoreCase = true) && effectivePort(it) == effectivePort(site)
    } ?: false

    fun isExternalHttps(url: String?): Boolean = parseHttps(url) != null && !isTrusted(url)

    private fun parseHttps(url: String?): URI? = runCatching {
        URI(url ?: "").takeIf {
            it.scheme.equals("https", ignoreCase = true) && !it.host.isNullOrBlank() && it.userInfo == null
        }
    }.getOrNull()

    private fun effectivePort(uri: URI) = if (uri.port == -1) 443 else uri.port

    companion object {
        fun safeFilename(name: String): String = name
            .substringAfterLast('/').substringAfterLast('\\')
            .replace(Regex("[^A-Za-z0-9._() -]"), "_")
            .trim(' ', '.').take(120).ifBlank { "toolsathi-result.txt" }
    }
}
