# Google Search Console for ToolSathi

Target property: **https://anandtrip22.pythonanywhere.com/**. First confirm that the live deployment opens anonymously over HTTPS. The configuration described here does not mean the account is verified or that Google has indexed the site.

## Existing SEO implementation

The app already serves `/sitemap.xml` and `/robots.txt`; no duplicate routes are needed. With `SITE_URL=https://anandtrip22.pythonanywhere.com`, the sitemap contains the homepage, tool directory, seven categories, About, Privacy, Android download page and all 83 available tools. Unavailable tools and private result/account/API paths are excluded. Each tool has its own title, description and canonical URL; query parameters are omitted from canonicals. Public pages contain structured data and internal links.

Check these public URLs after deployment:

- [Sitemap](https://anandtrip22.pythonanywhere.com/sitemap.xml)
- [Robots rules](https://anandtrip22.pythonanywhere.com/robots.txt)
- [JSON Formatter](https://anandtrip22.pythonanywhere.com/tools/json-formatter/)
- [Image Compressor](https://anandtrip22.pythonanywhere.com/tools/image-compressor/)
- [PDF Merger](https://anandtrip22.pythonanywhere.com/tools/pdf-merger/)

Robots rules guide crawlers; they are not access controls. Temporary downloads separately require the originating session and an unexpired signed link, and send `X-Robots-Tag: noindex, nofollow, noarchive`.

## Verify the URL-prefix property

1. Open [Google Search Console](https://search.google.com/search-console/) using your Google account. In the property selector, choose **Add property**.
2. Choose **URL prefix**, enter `https://anandtrip22.pythonanywhere.com/`, and continue. Choose **HTML tag** under the available verification methods. HTML-tag verification supports a URL-prefix property; a Domain property requires DNS verification. [Google ownership verification](https://support.google.com/webmasters/answer/9008080).
3. Copy only the exact value inside the issued tag's `content="..."` attribute. Keep the Google verification dialog open. Do not use an invented value or paste the whole tag.
4. In PythonAnywhere **Files**, open `/home/anandtrip22/.toolsathi.env`. Set its single `GOOGLE_SITE_VERIFICATION=` line to the issued content value and save. Preserve every other setting and secret. This file is outside Git. If editing in a Bash console, use `nano /home/anandtrip22/.toolsathi.env`; do not print the file into shared logs. Keep permissions private:

   ```bash
   chmod 600 /home/anandtrip22/.toolsathi.env
   ```

5. Open [PythonAnywhere Web](https://www.pythonanywhere.com/user/anandtrip22/webapps/), select `anandtrip22.pythonanywhere.com`, and click **Reload**. The platform WSGI configuration must load the private environment file as described in [deployment instructions](PYTHONANYWHERE_FREE_DEPLOY.md).
6. Open the [live homepage](https://anandtrip22.pythonanywhere.com/) in a private browser window, view its page source, and find `google-site-verification` inside `<head>`. The value must match Google's issued value. A blank setting produces no tag; the template HTML-escapes configured content.
7. Return to Search Console and click **Verify**. Leave the setting in place after success because Google rechecks ownership. [HTML-tag verification requirements](https://support.google.com/webmasters/answer/9008080).

The ownership token is designed to appear in public HTML. Account passwords, the Django secret key and any deployment API token must remain private. Search Console authentication and the issued ownership value require the account owner's action unless an authenticated session is already available.

## Submit and inspect

After ownership verification, select the correct property, open **Sitemaps**, enter `sitemap.xml` in **Add a new sitemap**, and click **Submit**. Check that its resolved URL is `https://anandtrip22.pythonanywhere.com/sitemap.xml`; investigate any fetch or parsing errors. Google uses sitemap submission as a discovery hint, not a guarantee of crawling or indexing. [Google sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap).

Use the top **URL inspection** field for the homepage and the three real tool URLs above. Review the reported status, choose **Test live URL** when checking a new deployment, then **Request indexing** if the page is eligible. Requests are limited; repeatedly requesting the same page does not accelerate crawling. Indexing may take days or weeks and is not guaranteed. [Google recrawl guidance](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl).

After deployment changes, inspect the exact HTTPS URL and confirm its canonical points to the same production origin. Keep public pages available without login or a site-wide `noindex`. Monitor Search Console's indexing and sitemap reports; resolve actual errors before requesting another crawl. Never report verification, sitemap submission or indexing as complete until the corresponding account state has been checked.
