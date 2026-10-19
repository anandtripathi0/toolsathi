package com.toolsathi.app

import android.annotation.SuppressLint
import android.app.DownloadManager
import android.content.ActivityNotFoundException
import android.content.ContentValues
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Color
import android.net.Uri
import android.net.http.SslError
import android.os.Bundle
import android.os.Environment
import android.provider.MediaStore
import android.util.Base64
import android.view.Gravity
import android.view.View
import android.webkit.CookieManager
import android.webkit.PermissionRequest
import android.webkit.SslErrorHandler
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import androidx.webkit.WebMessageCompat
import java.io.ByteArrayInputStream
import java.io.InputStream
import java.net.URL
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import javax.net.ssl.HttpsURLConnection
import org.json.JSONObject

class MainActivity : ComponentActivity() {
    private lateinit var webView: WebView
    private lateinit var offline: LinearLayout
    private lateinit var progress: ProgressBar
    private val policy = NavigationPolicy(BuildConfig.SITE_URL)
    private val fileExecutor = Executors.newSingleThreadExecutor()
    private val saving = AtomicBoolean(false)
    private var fileCallback: ValueCallback<Array<Uri>>? = null
    private var lastTrustedUrl = BuildConfig.SITE_URL
    private var pageFailed = false

    private val fileChooser = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val callback = fileCallback
        fileCallback = null
        val selected = if (result.resultCode == RESULT_OK) {
            val data = result.data
            val clip = data?.clipData
            val uris = if (clip != null) (0 until minOf(clip.itemCount, 30)).map { clip.getItemAt(it).uri }
                else listOfNotNull(data?.data)
            // Never let a returned file:// or arbitrary scheme become a WebView upload source.
            uris.filter { it.scheme == "content" }.toTypedArray().takeIf { it.isNotEmpty() }
        } else null
        callback?.onReceiveValue(selected)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        createInterface()
        configureWebView()
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else finish()
            }
        })
        // Deliberately do not persist WebView form data into the activity saved-state bundle.
        webView.loadUrl(BuildConfig.SITE_URL)
    }

    private fun createInterface() {
        val root = FrameLayout(this).apply { setBackgroundColor(Color.WHITE) }
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }
        webView = WebView(this).apply {
            setBackgroundColor(Color.WHITE)
            importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS
        }
        root.addView(webView, FrameLayout.LayoutParams(-1, -1))
        progress = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply { max = 100 }
        root.addView(progress, FrameLayout.LayoutParams(-1, dp(3), Gravity.TOP))
        offline = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(dp(28), dp(28), dp(28), dp(28))
            setBackgroundColor(Color.WHITE)
            visibility = View.GONE
        }
        offline.addView(TextView(this).apply {
            text = getString(R.string.app_name); textSize = 28f; setTextColor(Color.BLACK)
            gravity = Gravity.CENTER
        })
        offline.addView(TextView(this).apply {
            text = getString(R.string.offline_title); textSize = 20f; setTextColor(Color.BLACK)
            gravity = Gravity.CENTER; setPadding(0, dp(24), 0, dp(12))
        })
        offline.addView(TextView(this).apply {
            text = getString(R.string.offline_body); textSize = 16f; setTextColor(Color.DKGRAY)
            gravity = Gravity.CENTER; setPadding(0, 0, 0, dp(24))
        })
        offline.addView(Button(this).apply {
            text = getString(R.string.retry)
            setOnClickListener { webView.loadUrl(lastTrustedUrl) }
        })
        root.addView(offline, FrameLayout.LayoutParams(-1, -1))
        setContentView(root)
    }

    @SuppressLint("SetJavaScriptEnabled")
    @Suppress("DEPRECATION")
    private fun configureWebView() {
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            allowFileAccessFromFileURLs = false
            allowUniversalAccessFromFileURLs = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            safeBrowsingEnabled = true
            javaScriptCanOpenWindowsAutomatically = false
            setSupportMultipleWindows(false)
            setGeolocationEnabled(false)
            setSaveFormData(false)
            cacheMode = WebSettings.LOAD_DEFAULT
            userAgentString = "$userAgentString ToolSathiAndroid/${BuildConfig.VERSION_NAME}"
        }
        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            setAcceptThirdPartyCookies(webView, false)
        }
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val url = request.url.toString()
                if (policy.isTrusted(url)) return false
                if (request.isForMainFrame && request.hasGesture() && policy.isExternalHttps(url)) {
                    openExternal(request.url)
                }
                return true
            }

            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
                val scheme = request.url.scheme?.lowercase()
                if (scheme !in setOf("https", "data", "blob", "about")) {
                    return WebResourceResponse("text/plain", "UTF-8", 403, "Blocked", emptyMap(), ByteArrayInputStream(ByteArray(0)))
                }
                return null
            }

            override fun onPageStarted(view: WebView, url: String, favicon: Bitmap?) {
                if (!policy.isTrusted(url)) { view.stopLoading(); showOffline(); return }
                lastTrustedUrl = url
                pageFailed = false
                offline.visibility = View.GONE
                progress.visibility = View.VISIBLE
            }

            override fun onPageFinished(view: WebView, url: String) {
                progress.visibility = View.GONE
                if (!pageFailed && policy.isTrusted(url)) offline.visibility = View.GONE
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (request.isForMainFrame) showOffline()
            }

            override fun onReceivedHttpError(view: WebView, request: WebResourceRequest, errorResponse: WebResourceResponse) {
                if (request.isForMainFrame && errorResponse.statusCode >= 500) showOffline()
            }

            override fun onReceivedSslError(view: WebView, handler: SslErrorHandler, error: SslError) {
                handler.cancel()
                showOffline()
            }
        }
        webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView, newProgress: Int) { progress.progress = newProgress }
            override fun onPermissionRequest(request: PermissionRequest) { request.deny() }
            override fun onShowFileChooser(view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams): Boolean {
                fileCallback?.onReceiveValue(null)
                fileCallback = null
                if (!policy.isTrusted(view.url)) { callback.onReceiveValue(null); return true }
                fileCallback = callback
                val accepted = params.acceptTypes.flatMap { it.split(',') }.map { it.trim() }
                    .filter { it.matches(Regex("[A-Za-z0-9.+*-]+/[A-Za-z0-9.+*-]+")) }.distinct().toTypedArray()
                val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = if (accepted.size == 1) accepted[0] else "*/*"
                    if (accepted.size > 1) putExtra(Intent.EXTRA_MIME_TYPES, accepted)
                    putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.mode == FileChooserParams.MODE_OPEN_MULTIPLE)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
                try { fileChooser.launch(Intent.createChooser(intent, getString(R.string.file_chooser))) }
                catch (_: ActivityNotFoundException) { fileCallback?.onReceiveValue(null); fileCallback = null; toast(R.string.download_failed) }
                return true
            }
        }
        webView.setDownloadListener { url, userAgent, contentDisposition, mimeType, _ ->
            if (policy.isTrusted(url)) {
                downloadHttps(url, userAgent, contentDisposition, mimeType)
            } else if (url.startsWith("blob:")) {
                toast(R.string.unsupported_webview)
            } else if (policy.isExternalHttps(url)) openExternal(Uri.parse(url))
            else toast(R.string.unsupported_link)
        }
        installFileBridge()
    }

    private fun installFileBridge() {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) return
        WebViewCompat.addWebMessageListener(webView, "ToolSathiAndroid", setOf(policy.origin)) {
                view, message, sourceOrigin, isMainFrame, reply ->
            if (!isMainFrame || !policy.isTrusted(sourceOrigin.toString()) || !policy.isTrusted(view.url)) return@addWebMessageListener
            if (message.type != WebMessageCompat.TYPE_STRING) return@addWebMessageListener
            val raw = message.data ?: return@addWebMessageListener
            if (raw.length > MAX_MESSAGE_CHARS) return@addWebMessageListener
            var id = ""
            var claimedSave = false
            try {
                val payload = JSONObject(raw)
                id = payload.optString("id").take(100)
                require(payload.getString("type") == "saveFile")
                val encoded = payload.getString("base64")
                require(encoded.length <= MAX_BASE64_CHARS)
                val name = NavigationPolicy.safeFilename(payload.getString("filename"))
                val mime = safeMime(payload.optString("mime"))
                if (!saving.compareAndSet(false, true)) throw IllegalStateException("busy")
                claimedSave = true
                fileExecutor.execute {
                    val result = JSONObject().put("id", id)
                    try {
                        val bytes = Base64.decode(encoded, Base64.DEFAULT)
                        require(bytes.size <= MAX_BLOB_BYTES)
                        saveToDownloads(name, mime, ByteArrayInputStream(bytes), MAX_BLOB_BYTES.toLong())
                        result.put("ok", true).put("filename", name)
                    } catch (_: Exception) {
                        result.put("ok", false).put("error", "The file could not be saved. Try again.")
                    } finally { saving.set(false) }
                    runOnUiThread { if (!isDestroyed) reply.postMessage(result.toString()) }
                }
            } catch (_: Exception) {
                if (claimedSave) saving.set(false)
                reply.postMessage(JSONObject().put("id", id).put("ok", false)
                    .put("error", "File must be at most 8 MiB. Wait for any current download to finish.").toString())
            }
        }
    }

    private fun downloadHttps(url: String, userAgent: String?, disposition: String?, mimeType: String?) {
        if (!policy.isTrusted(url)) return
        val name = NavigationPolicy.safeFilename(URLUtil.guessFileName(url, disposition, mimeType))
        if (Uri.parse(url).path == "/downloads/toolsathi-latest.apk") {
            // This public endpoint needs no credentials. DownloadManager may follow redirects;
            // do not attach Cookie, Authorization or Referer headers to its requests.
            try {
                val request = DownloadManager.Request(Uri.parse(url))
                    .setTitle(name)
                    .setMimeType("application/vnd.android.package-archive")
                    .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                    .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name)
                (getSystemService(DOWNLOAD_SERVICE) as DownloadManager).enqueue(request)
                toast(R.string.download_started)
            } catch (_: Exception) { toast(R.string.download_failed) }
            return
        }
        if (!saving.compareAndSet(false, true)) { toast(R.string.download_failed); return }
        // Session-bound result downloads never follow redirects, so cookies cannot cross origins.
        val cookies = CookieManager.getInstance().getCookie(url)
        fileExecutor.execute {
            var connection: HttpsURLConnection? = null
            var success = false
            try {
                val activeConnection = URL(url).openConnection() as HttpsURLConnection
                connection = activeConnection
                activeConnection.instanceFollowRedirects = false
                activeConnection.connectTimeout = 15_000
                activeConnection.readTimeout = 60_000
                activeConnection.requestMethod = "GET"
                if (!cookies.isNullOrBlank()) activeConnection.setRequestProperty("Cookie", cookies)
                if (!userAgent.isNullOrBlank()) activeConnection.setRequestProperty("User-Agent", userAgent)
                require(activeConnection.responseCode == 200)
                require(activeConnection.contentLengthLong <= MAX_REMOTE_BYTES)
                val resolvedName = NavigationPolicy.safeFilename(URLUtil.guessFileName(url,
                    activeConnection.getHeaderField("Content-Disposition") ?: disposition, activeConnection.contentType ?: mimeType))
                activeConnection.inputStream.use { input ->
                    saveToDownloads(resolvedName, safeMime(activeConnection.contentType ?: mimeType), input, MAX_REMOTE_BYTES)
                }
                success = true
            } catch (_: Exception) {
                // Never log response bodies, file content or the session cookie.
            } finally { connection?.disconnect(); saving.set(false) }
            runOnUiThread { if (!isDestroyed) toast(if (success) R.string.download_saved else R.string.download_failed) }
        }
    }

    private fun saveToDownloads(name: String, mime: String, input: InputStream, maxBytes: Long) {
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, name)
            put(MediaStore.Downloads.MIME_TYPE, mime)
            put(MediaStore.Downloads.RELATIVE_PATH, "${Environment.DIRECTORY_DOWNLOADS}/ToolSathi")
            put(MediaStore.Downloads.IS_PENDING, 1)
        }
        val uri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: throw IllegalStateException("Cannot create download")
        try {
            contentResolver.openOutputStream(uri)?.use { output ->
                val buffer = ByteArray(16 * 1024)
                var total = 0L
                while (true) {
                    val count = input.read(buffer)
                    if (count == -1) break
                    total += count
                    require(total <= maxBytes)
                    output.write(buffer, 0, count)
                }
            } ?: throw IllegalStateException("Cannot open download")
            contentResolver.update(uri, ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) }, null, null)
        } catch (error: Exception) {
            contentResolver.delete(uri, null, null)
            throw error
        }
    }

    private fun safeMime(value: String?): String = value?.substringBefore(';')?.trim()
        ?.takeIf { it.matches(Regex("[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+")) } ?: "application/octet-stream"

    private fun openExternal(uri: Uri) {
        if (!policy.isExternalHttps(uri.toString())) return
        try { startActivity(Intent(Intent.ACTION_VIEW, uri).addCategory(Intent.CATEGORY_BROWSABLE)) }
        catch (_: ActivityNotFoundException) { toast(R.string.unsupported_link) }
    }

    private fun showOffline() {
        pageFailed = true
        offline.visibility = View.VISIBLE
        progress.visibility = View.GONE
    }

    private fun toast(message: Int) = Toast.makeText(this, message, Toast.LENGTH_LONG).show()
    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()

    override fun onPause() { webView.onPause(); CookieManager.getInstance().flush(); super.onPause() }
    override fun onResume() { super.onResume(); if (::webView.isInitialized) webView.onResume() }
    override fun onDestroy() {
        fileCallback?.onReceiveValue(null)
        fileCallback = null
        webView.stopLoading()
        webView.destroy()
        fileExecutor.shutdown()
        super.onDestroy()
    }

    companion object {
        private const val MAX_BLOB_BYTES = 8 * 1024 * 1024
        private const val MAX_BASE64_CHARS = ((MAX_BLOB_BYTES + 2) / 3) * 4
        private const val MAX_MESSAGE_CHARS = MAX_BASE64_CHARS + 2048
        private const val MAX_REMOTE_BYTES = 64L * 1024 * 1024
    }
}
