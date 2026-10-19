"""The single source of truth for published tools, forms, SEO and search."""
from difflib import SequenceMatcher
import re


CATEGORIES = [
    {"id": "developer", "name": "Developer Tools", "icon": "code-2", "description": "Format, validate, encode and inspect your data."},
    {"id": "image", "name": "Image Tools", "icon": "image", "description": "Resize, compress and convert images with confidence."},
    {"id": "pdf", "name": "PDF Tools", "icon": "file-text", "description": "Merge, split and organize your documents."},
    {"id": "text", "name": "Text Tools", "icon": "type", "description": "Clean, count, compare and transform your words."},
    {"id": "seo", "name": "SEO Tools", "icon": "search", "description": "Create useful metadata and inspect page structure."},
    {"id": "design", "name": "CSS & Design", "icon": "palette", "description": "Explore colors and generate everyday CSS."},
    {"id": "utilities", "name": "Everyday Utilities", "icon": "grid-2x2", "description": "Small, practical tools for everyday questions."},
]


def field(name, label, kind="text", default="", **kwargs):
    return {"name": name, "label": label, "type": kind, "default": default, **kwargs}


def area(label="Input", default="", name="text", **kwargs):
    return field(name, label, "textarea", default, **kwargs)


def number(name, label, default=0, minimum=None, maximum=None, **kwargs):
    return field(name, label, "number", default, **({"min": minimum} if minimum is not None else {}), **({"max": maximum} if maximum is not None else {}), **kwargs)


def select(name, label, choices, default=None, **kwargs):
    options = [{"value": c[0], "label": c[1]} if isinstance(c, tuple) else {"value": c, "label": c.replace("-", " ").title()} for c in choices]
    return field(name, label, "select", options[0]["value"] if default is None else default, options=options, **kwargs)


def check(name, label, default=False):
    return field(name, label, "checkbox", default)


REGISTRY = {}


def add(slug, name, category, description, fields, example, keywords="", icon=None, extension="txt", instructions=""):
    REGISTRY[slug] = {
        "id": slug, "slug": slug, "name": name, "category": category,
        "description": description, "keywords": [item.strip() for item in keywords.split(",") if item.strip()],
        "icon": icon or next(c["icon"] for c in CATEGORIES if c["id"] == category),
        "status": "available", "handler": "text", "download_type": extension,
        "seo_title": f"Free {name} — ToolSathi",
        "seo_description": f"{description} Use ToolSathi's free {name.lower()} online. No signup required.",
        "related_tools": [], "fields": fields, "example": example,
        "instructions": instructions or "Enter your input or load the practical example, adjust the options, and select Process. Copy the result or download it without an account.",
        "faqs": [
            {"question": f"Is the {name.lower()} free?", "answer": "Yes. You can process, copy and download results without signing in or paying."},
            {"question": "Is my input saved?", "answer": "Tool inputs are processed for this request and are not stored in your history. Favorites and recent tools contain only tool IDs."},
        ],
    }


JSON_EXAMPLE = '{"name":"ToolSathi","free":true,"tools":["JSON","PDF","Images"]}'
JSON_ROWS = '[{"name":"Asha","city":"Pune"},{"name":"Ravi","city":"Delhi"}]'
ENCODING_FIELDS = [area("Text"), select("operation", "Operation", ["encode", "decode"])]

for slug, name, description, aliases in [
    ("json-formatter", "JSON Formatter", "Beautify JSON with readable indentation and clear syntax errors.", "json beautify,pretty json,json pretty print,format json"),
    ("json-validator", "JSON Validator", "Validate JSON syntax and locate errors by line and column.", "check json,json lint,validate json"),
    ("json-minifier", "JSON Minifier", "Remove unnecessary JSON whitespace while preserving its values.", "compact json,minify json,compress json"),
]:
    add(slug, name, "developer", description, [area("JSON", required=True)], {"text": JSON_EXAMPLE}, aliases, extension="json" if slug != "json-validator" else "txt")

add("json-diff", "JSON Diff", "developer", "Compare JSON values with a readable unified diff; ignore object key order.", [area("Original JSON", required=True), area("Changed JSON", name="second", required=True)], {"text": '{"name":"Asha","active":false}', "second": '{"active":true,"name":"Asha"}'}, "compare json,json difference,json compare", instructions="Paste two JSON documents. Objects are sorted by key before comparison; array order remains significant. The diff shows removed lines with − and added lines with +.")
add("json-to-csv", "JSON to CSV", "developer", "Convert a JSON array of objects into a downloadable CSV table.", [area("JSON array", required=True)], {"text": JSON_ROWS}, "convert json,csv converter,json table", extension="csv", instructions="Enter an array of objects. All object keys become columns; nested values are serialized as JSON. Formula-like cells are prefixed with an apostrophe to make spreadsheet opening safer.")
add("csv-to-json", "CSV to JSON", "developer", "Convert a CSV table with headers into a JSON array of objects.", [area("CSV with a header row", required=True), select("delimiter", "Delimiter", [(",", "Comma"), (";", "Semicolon"), ("\t", "Tab"), ("|", "Pipe")])], {"text": "name,city\nAsha,Pune\nRavi,Delhi", "delimiter": ","}, "convert csv,csv json,table to json", extension="json", instructions="Include a unique, non-empty header for every column. Choose the delimiter used by your data. Values are preserved as strings, including leading zeroes.")
add("yaml-to-json", "YAML to JSON", "developer", "Convert safe YAML data into formatted JSON.", [area("YAML", required=True)], {"text": "name: ToolSathi\nfree: true\ntools:\n  - JSON\n  - PDF"}, "yml json,convert yaml", extension="json", instructions="Paste YAML using ordinary mappings, lists, strings and numbers. Quote dates if you want strings. Custom tags, aliases and values that JSON cannot represent are rejected.")
add("json-to-yaml", "JSON to YAML", "developer", "Turn valid JSON into clean, readable YAML.", [area("JSON", required=True)], {"text": JSON_EXAMPLE}, "json yml,convert json yaml", extension="yaml")

for slug, name, label, example, extension, aliases in [
    ("xml-formatter", "XML Formatter", "XML", '<catalog><tool name="JSON">Free</tool></catalog>', "xml", "beautify xml,pretty xml"),
    ("html-formatter", "HTML Formatter", "HTML", '<main><h1>Every Tool. One Place.</h1><p>Hello, ToolSathi!</p></main>', "html", "beautify html,pretty html"),
    ("css-formatter", "CSS Formatter", "CSS", '.card{padding:24px;border:1px solid #eaeaea;border-radius:16px}', "css", "beautify css,pretty css"),
    ("javascript-formatter", "JavaScript Formatter", "JavaScript", 'function greet(name){return "Hello, "+name;}console.log(greet("ToolSathi"));', "js", "beautify js,format js,pretty javascript"),
    ("sql-formatter", "SQL Formatter", "SQL", 'select name,city from users where active=1 order by name;', "sql", "beautify sql,format query,pretty sql"),
]:
    add(slug, name, "developer", f"Format {label} into a more readable layout without executing it.", [area(label, required=True)], {"text": example}, aliases, extension=extension, instructions=f"Paste {label} and select Process. Formatting improves layout but does not verify program correctness. No submitted code is executed. XML document types and entities are rejected.")

add("base64-encoder-decoder", "Base64 Encoder/Decoder", "developer", "Encode UTF-8 text as Base64 or decode Base64 back to text.", ENCODING_FIELDS, {"text": "Every Tool. One Place.", "operation": "encode"}, "base64 encode,base64 decode,b64")
add("url-encoder-decoder", "URL Encoder/Decoder", "developer", "Percent-encode a URL component or decode escaped UTF-8 text.", ENCODING_FIELDS, {"text": "hello world & tools", "operation": "encode"}, "url encode,url decode,percent encoding,uri", instructions="Encode individual URL components, not a full URL that must remain navigable. Decoding uses percent escapes; literal plus signs remain plus signs.")
add("html-entity-encoder-decoder", "HTML Entity Encoder/Decoder", "developer", "Escape HTML-sensitive characters or decode HTML entities.", ENCODING_FIELDS, {"text": '<p title="Hello">Tools & ideas</p>', "operation": "encode"}, "html escape,unescape html,entities")
add("jwt-decoder", "JWT Decoder", "developer", "Inspect a JWT header and payload without verifying its signature.", [area("JWT token", required=True)], {"text": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJleGFtcGxlIiwibmFtZSI6IlRvb2xTYXRoaSJ9.ZGVtby1zaWduYXR1cmU"}, "decode token,json web token,inspect jwt", extension="json", instructions="Paste a JWT with three dot-separated sections. Decoding does not verify the signature or prove authenticity. Never use decoded values alone for authentication, and avoid submitting live secrets.")
add("regex-tester", "Regex Tester", "developer", "Find regular-expression matches, positions and capture groups.", [field("pattern", "Regular expression", default=r"\b\w+@\w+\.\w+\b", required=True), area("Test text", required=True), check("ignore_case", "Ignore case"), check("multiline", "Multiline anchors")], {"pattern": r"\b\w+@\w+\.\w+\b", "text": "Write to hello@example.com or team@toolsathi.test."}, "regular expression,regex match,regexp", extension="json", instructions="Enter a pattern without enclosing / delimiters, then the test text. Results use zero-based character positions. Processing stops after 1,000 matches or a 50 ms regex safety timeout.")
add("uuid-generator", "UUID Generator", "developer", "Generate cryptographically random version 4 UUIDs.", [number("count", "Number of UUIDs", 5, 1, 1000)], {"count": 5}, "guid generator,random uuid,uuid v4", icon="fingerprint")
add("unix-timestamp-converter", "Unix Timestamp Converter", "developer", "Convert Unix seconds or milliseconds to UTC dates and back.", [field("text", "Timestamp or ISO date/time", required=True), select("operation", "Direction", [("to-date", "Timestamp → UTC date"), ("to-timestamp", "ISO date → timestamp")]), select("unit", "Timestamp unit", ["seconds", "milliseconds"])], {"text": "1767225600", "operation": "to-date", "unit": "seconds"}, "epoch converter,unix time,timestamp,date converter", icon="clock", instructions="Choose the direction and seconds or milliseconds. Date inputs use ISO format, for example 2026-01-01T12:00:00Z. All output uses UTC; inputs without an offset are interpreted as UTC.")
add("cron-expression-parser", "Cron Expression Parser", "developer", "Preview the next ten occurrences of a five-field cron schedule in UTC.", [field("text", "Cron expression", "text", "0 9 * * 1-5", required=True), field("start", "Start date/time (UTC; optional)", help="ISO format. Leave blank to use the current UTC time.")], {"text": "0 9 * * 1-5", "start": "2026-01-01T00:00:00Z"}, "crontab parser,cron schedule,cron next run", icon="calendar-clock", instructions="Use five fields: minute, hour, day of month, month, weekday. Matches are computed after the start time in UTC. Day-of-month and weekday use standard cron OR semantics when both are restricted. The look-ahead limit is five years.")
add("text-diff-checker", "Text Diff Checker", "developer", "Compare two texts line by line with a unified difference view.", [area("Original text"), area("Changed text", name="second")], {"text": "Hello\nEvery tool\nOne place\n", "second": "Hello\nEvery free tool\nOne place\n"}, "compare text,difference checker,text comparison")
add("hash-generator", "SHA-256/SHA-512 Hash Generator", "developer", "Compute a SHA-256 or SHA-512 digest of UTF-8 text.", [area("Text to hash"), select("algorithm", "Algorithm", [("sha256", "SHA-256"), ("sha512", "SHA-512")])], {"text": "ToolSathi", "algorithm": "sha256"}, "sha256,sha512,checksum,hash text", icon="hash", instructions="Paste exact text, including any significant whitespace, and select a hash algorithm. These digests are for checksums and integrity checks; they are not password-storage algorithms.")
ALPHABETS = [("symbols", "Letters, numbers & symbols"), ("alphanumeric", "Letters & numbers"), ("letters", "Letters only"), ("digits", "Digits only"), ("hex", "Hexadecimal")]
add("secure-password-generator", "Secure Password Generator", "developer", "Create passwords using cryptographically secure randomness.", [number("length", "Password length", 24, 4, 1024), number("count", "Number of passwords", 1, 1, 100), select("alphabet", "Characters", ALPHABETS)], {"length": 24, "count": 3, "alphabet": "symbols"}, "strong password,random password,password maker", icon="key-round", instructions="Choose the length and character set. Every selected character group is represented. Passwords use Python's cryptographically secure secrets generator and are not saved; use a password manager to store them.")
add("markdown-editor", "Markdown Editor", "developer", "Convert Markdown into sanitized HTML with a live result preview.", [area("Markdown", required=True)], {"text": "# Every Tool. One Place.\n\nWrite **clearly**. Build *freely*.\n\n- Format JSON\n- Resize images\n- Organize PDFs"}, "markdown preview,md editor,markdown to html", extension="html", instructions="Write Markdown, including fenced code or tables, then select Process. The preview and exported HTML remove unsafe elements and attributes. Embedded scripts are never executed.")
add("html-playground", "HTML Playground", "developer", "Preview HTML markup in an isolated, script-disabled browser frame.", [area("HTML", required=True)], {"text": '<main style="font-family:system-ui;padding:32px"><h1>Hello, ToolSathi.</h1><p>Every Tool. One Place.</p><button style="padding:12px 20px">A sample button</button></main>'}, "html editor,html preview,sandbox", extension="html", instructions="Enter HTML and select Process to preview it inside a sandbox. Scripts, forms, downloads and top-level navigation are disabled in the preview. The downloaded file contains your original markup.")
add("css-playground", "CSS Playground", "developer", "Preview your CSS on sample HTML inside an isolated browser frame.", [area("CSS", required=True), area("HTML markup", name="second", default='<div class="card">Every Tool. One Place.</div>')], {"text": 'body { font-family: system-ui; padding: 32px; }\n.card { padding: 32px; border: 1px solid #eaeaea; border-radius: 16px; font-size: 24px; }', "second": '<div class="card">Every Tool. One Place.</div>'}, "css editor,css preview,style playground", extension="html", instructions="Enter CSS and a small HTML example. Select Process to render both in a script-disabled sandbox. The result downloads as a complete HTML document.")
add("http-status-code-reference", "HTTP Status Code Reference", "developer", "Look up standard HTTP status codes, names and descriptions.", [field("text", "Code or phrase (blank for all)")], {"text": "404"}, "http codes,404,500,status reference", extension="json")
add("user-agent-parser", "User Agent Parser", "developer", "Identify browser, operating system and device from a user-agent string.", [area("User-agent string", required=True)], {"text": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"}, "browser detector,ua parser,device parser", extension="json", instructions="Paste a user-agent string. The parser uses known patterns to identify the browser and device. Results are approximate because clients can change or spoof user-agent values.")
add("uuid-validator", "UUID Validator", "developer", "Validate a UUID and inspect its canonical form, version and variant.", [field("text", "UUID", required=True)], {"text": "550e8400-e29b-41d4-a716-446655440000"}, "guid validator,check uuid,uuid check", extension="json")

TEXT_EXAMPLE = "Every Tool. One Place.\n\nFree tools for thoughtful work."
for slug, name, description in [
    ("word-counter", "Word Counter", "Count words, characters, lines and estimated reading time."),
    ("character-counter", "Character Counter", "Count Unicode characters with and without whitespace."),
]:
    add(slug, name, "text", description, [area("Text")], {"text": TEXT_EXAMPLE}, "word count,character count,letters count,reading time", extension="json")
add("case-converter", "Case Converter", "text", "Change text to uppercase, lowercase, title case, camelCase and more.", [area("Text"), select("operation", "Case", ["title", "upper", "lower", "sentence", "swap", "camel", "snake", "kebab"])], {"text": "every tool one place", "operation": "title"}, "uppercase,lowercase,title case,snake case,camel case")
add("duplicate-line-remover", "Duplicate Line Remover", "text", "Remove repeated lines while preserving their original order.", [area("One item per line"), check("ignore_case", "Ignore case")], {"text": "apple\nbanana\napple\norange\nbanana"}, "deduplicate lines,unique lines,remove duplicates")
add("text-sorter", "Text Sorter", "text", "Sort lines alphabetically, numerically or by length.", [area("One item per line"), select("operation", "Sort order", ["ascending", "descending", "numeric", "length"])], {"text": "orange\napple\nbanana", "operation": "ascending"}, "sort lines,alphabetical order,sort text")
add("find-and-replace", "Find and Replace", "text", "Replace literal text across a document with optional case matching.", [area("Text"), field("find", "Find", required=True), field("replacement", "Replace with"), check("ignore_case", "Ignore case")], {"text": "Hello world. A world of tools.", "find": "world", "replacement": "ToolSathi"}, "replace text,search replace")
add("whitespace-remover", "Whitespace Remover", "text", "Trim lines, collapse spacing or remove blank lines and whitespace.", [area("Text"), select("operation", "Operation", [("trim", "Trim each line"), ("collapse", "Collapse all whitespace"), ("all", "Remove all whitespace"), ("blank-lines", "Remove blank lines")])], {"text": "  Every   Tool.  \n\n  One Place.  ", "operation": "trim"}, "trim text,remove spaces,clean whitespace")
add("lorem-ipsum-generator", "Lorem Ipsum Generator", "text", "Generate placeholder paragraphs for layouts and prototypes.", [number("count", "Paragraphs", 3, 1, 100)], {"count": 3}, "dummy text,placeholder text,lorem generator")
add("text-reverser", "Text Reverser", "text", "Reverse characters, word order or line order.", [area("Text"), select("operation", "Reverse", ["characters", "words", "lines"])], {"text": "Every Tool. One Place.", "operation": "words"}, "reverse text,backwards text")
add("text-to-slug", "Text to Slug", "text", "Create a lowercase, ASCII URL slug from a title or phrase.", [field("text", "Title or phrase", required=True)], {"text": "Every Tool. One Place!"}, "slugify,url slug,clean url", instructions="Enter a title. Accented Latin letters are normalized to ASCII, punctuation becomes hyphens and repeated separators are removed. Characters without an ASCII equivalent are omitted.")

SEO_FIELDS = [field("text", "Page title", required=True), area("Page description", name="description"), field("url", "Canonical page URL")]
SEO_EXAMPLE = {"text": "ToolSathi — Every Tool. One Place.", "description": "Free tools for developers, creators and everyday work.", "url": "https://example.com/tools/"}
add("meta-tag-generator", "Meta Tag Generator", "seo", "Create escaped title, description and canonical tags for your page.", SEO_FIELDS, SEO_EXAMPLE, "seo meta,meta description,title tag", extension="html")
add("open-graph-generator", "Open Graph Generator", "seo", "Create Open Graph metadata for useful social link previews.", SEO_FIELDS + [field("image_url", "Preview image URL"), select("og_type", "Page type", ["website", "article"])], {**SEO_EXAMPLE, "image_url": "https://example.com/preview.png", "og_type": "website"}, "og tags,social meta,open graph tags", extension="html")
add("robots-txt-generator", "Robots.txt Generator", "seo", "Generate crawler directives and an optional sitemap declaration.", [field("agent", "User-agent", default="*", required=True), area("Disallowed paths (one per line; blank allows crawling)"), field("sitemap", "Sitemap URL (optional)")], {"agent": "*", "text": "/private/\n/admin/", "sitemap": "https://example.com/sitemap.xml"}, "robots file,crawler rules,robots generator", instructions="Choose a user-agent and enter disallowed paths, one per line. A blank list allows crawling. Robots.txt is a crawler convention, not access control or a guarantee that a URL stays out of search results.")
add("xml-sitemap-generator", "XML Sitemap Generator", "seo", "Build a valid XML sitemap from a list of absolute page URLs.", [area("Page URLs, one per line", required=True)], {"text": "https://example.com/\nhttps://example.com/tools/\nhttps://example.com/about/"}, "sitemap builder,google sitemap,url sitemap", extension="xml", instructions="Paste up to 1,000 HTTP or HTTPS URLs. Duplicate URLs are removed and XML-sensitive characters are escaped. Download the file, publish it on your own website and reference it in robots.txt.")
add("seo-slug-generator", "SEO Slug Generator", "seo", "Turn a page title into a concise, lowercase ASCII URL slug.", [field("text", "Page title", required=True)], {"text": "10 Free Developer Tools for Everyday Work"}, "seo url,seo friendly url,slug generator")
add("keyword-density-analyzer", "Keyword Density Analyzer", "seo", "Measure the frequency of words or short phrases in your text.", [area("Page text", required=True), select("phrase_length", "Phrase length", [("1", "One word"), ("2", "Two words"), ("3", "Three words")])], {"text": "Free tools make work easier. Discover free tools for text, images and code.", "phrase_length": "1"}, "keyword frequency,word density,seo keywords", extension="json", instructions="Paste visible page text and choose a phrase length. Density is occurrences divided by all possible phrase positions. Results report the 100 most common phrases; no ranking score or ideal keyword density is implied.")
add("heading-structure-analyzer", "Heading Structure Analyzer", "seo", "Inspect H1–H6 headings in pasted HTML and find skipped levels.", [area("Page HTML", required=True)], {"text": "<h1>ToolSathi</h1><h2>Developer tools</h2><h4>JSON tools</h4><h2>Image tools</h2>"}, "heading checker,h1 checker,html outline", extension="json")

add("hex-to-rgb", "HEX to RGB", "design", "Convert a three- or six-digit HEX color into RGB values.", [field("text", "HEX color", default="#2563eb", required=True)], {"text": "#2563eb"}, "hex rgb,color converter")
add("rgb-to-hex", "RGB to HEX", "design", "Convert red, green and blue channels into a HEX color.", [number("red", "Red", 37, 0, 255), number("green", "Green", 99, 0, 255), number("blue", "Blue", 235, 0, 255)], {"red": 37, "green": 99, "blue": 235}, "rgb hex,color converter")
add("hex-to-hsl", "HEX to HSL", "design", "Convert a HEX color into hue, saturation and lightness.", [field("text", "HEX color", default="#2563eb", required=True)], {"text": "#2563eb"}, "hex hsl,color converter")
add("color-palette-generator", "Color Palette Generator", "design", "Build analogous, complementary, triadic or shaded color palettes.", [field("text", "Base HEX color", default="#2563eb", required=True), select("operation", "Palette type", ["analogous", "complementary", "triadic", "shades"])], {"text": "#2563eb", "operation": "analogous"}, "color scheme,palette,color harmony")
add("css-gradient-generator", "CSS Gradient Generator", "design", "Generate CSS for a two-color linear gradient.", [field("text", "First HEX color", default="#111111", required=True), field("second", "Second HEX color", default="#ffffff", required=True), number("angle", "Angle (degrees)", 135, -360, 360)], {"text": "#111111", "second": "#ffffff", "angle": 135}, "gradient css,linear gradient", extension="css")
add("css-box-shadow-generator", "CSS Box Shadow Generator", "design", "Create a CSS box shadow with precise position, blur and opacity.", [field("text", "Shadow HEX color", default="#000000"), number("x", "Horizontal offset (px)", 0, -500, 500), number("y", "Vertical offset (px)", 8, -500, 500), number("blur", "Blur (px)", 24, 0, 500), number("spread", "Spread (px)", 0, -500, 500), number("opacity", "Opacity (0–1)", 0.12, 0, 1, step="0.01"), check("inset", "Inset shadow")], {"text": "#000000", "x": 0, "y": 8, "blur": 24, "spread": 0, "opacity": 0.12}, "box shadow,shadow css", extension="css")
add("css-border-radius-generator", "CSS Border Radius Generator", "design", "Generate corner radii in pixels, percentages or rem units.", [number(name, label, 16, 0, 1000) for name, label in [("top_left", "Top left"), ("top_right", "Top right"), ("bottom_right", "Bottom right"), ("bottom_left", "Bottom left")]] + [select("unit", "Unit", ["px", "%", "rem"])], {"top_left": 16, "top_right": 32, "bottom_right": 16, "bottom_left": 32, "unit": "px"}, "rounded corners,border radius", extension="css")
add("css-clamp-generator", "CSS Clamp Generator", "design", "Generate fluid font sizing between two viewport widths with CSS clamp.", [number("minimum", "Minimum font size (px)", 16, 0, 1000), number("maximum", "Maximum font size (px)", 48, 0, 1000), number("min_width", "Minimum viewport (px)", 320, 1, 10000), number("max_width", "Maximum viewport (px)", 1440, 1, 10000)], {"minimum": 16, "maximum": 48, "min_width": 320, "max_width": 1440}, "fluid typography,clamp css,responsive font", extension="css")
add("contrast-checker", "Contrast Checker", "design", "Calculate WCAG contrast ratios for two opaque HEX colors.", [field("text", "Text HEX color", default="#111111", required=True), field("second", "Background HEX color", default="#ffffff", required=True)], {"text": "#666666", "second": "#ffffff"}, "accessibility contrast,wcag,color contrast", extension="json", instructions="Enter opaque text and background HEX colors. Results compare relative luminance against WCAG AA and AAA text thresholds. Large text means at least 18pt regular or 14pt bold. Color contrast alone does not establish full accessibility.")

add("qr-code-generator", "QR Code Generator", "utilities", "Create a downloadable PNG QR code from a link or short text.", [area("URL or text", required=True), number("scale", "Pixels per QR module", 8, 2, 20)], {"text": "https://example.com", "scale": 8}, "qr maker,qr png,link qr", icon="qr-code", extension="png", instructions="Enter up to 2,000 UTF-8 bytes of text. The image includes a four-module white quiet zone and medium error correction. Download the PNG and test it with your phone before printing.")
add("random-number-generator", "Random Number Generator", "utilities", "Generate secure random integers in an inclusive range.", [number("minimum", "Minimum (inclusive)", 1, -1_000_000_000_000, 1_000_000_000_000), number("maximum", "Maximum (inclusive)", 100, -1_000_000_000_000, 1_000_000_000_000), number("count", "How many numbers", 10, 1, 1000), check("unique", "Unique numbers")], {"minimum": 1, "maximum": 100, "count": 10, "unique": True}, "random integer,randomizer,number picker", icon="dice-5")
add("random-string-generator", "Random String Generator", "utilities", "Generate random strings using a selected character alphabet.", [number("length", "String length", 24, 1, 1024), number("count", "Number of strings", 1, 1, 100), select("alphabet", "Characters", ALPHABETS, default="alphanumeric")], {"length": 24, "count": 3, "alphabet": "alphanumeric"}, "random text,random token,string generator")
add("date-difference-calculator", "Date Difference Calculator", "utilities", "Find the exact day count and calendar difference between two dates.", [field("text", "Start date", "date", required=True), field("second", "End date (blank uses today in UTC)", "date")], {"text": "2026-01-01", "second": "2026-10-19"}, "days between dates,date gap,days calculator", icon="calendar-days", extension="json")

UNIT_GROUPS = {"length": ["mm", "cm", "m", "km", "in", "ft", "yd", "mi"], "mass": ["mg", "g", "kg", "oz", "lb"], "temperature": ["C", "F", "K"], "area": ["m2", "km2", "ft2", "acre", "hectare"], "volume": ["mL", "L", "m3", "US-gal", "US-cup"], "speed": ["m/s", "km/h", "mph", "knot"], "data": ["B", "kB", "MB", "GB", "KiB", "MiB", "GiB"]}
UNIT_OPTIONS = [(unit, f"{group.title()} · {unit}") for group, values in UNIT_GROUPS.items() for unit in values]
add("unit-converter", "Unit Converter", "utilities", "Convert common units of length, mass, temperature, area, volume, speed and data.", [number("text", "Value", 1, -1e100, 1e100, step="any"), select("kind", "Measurement", list(UNIT_GROUPS)), select("from_unit", "From unit", UNIT_OPTIONS, "m", help="Choose a unit belonging to the selected measurement."), select("to_unit", "To unit", UNIT_OPTIONS, "ft", help="Choose a unit belonging to the selected measurement.")], {"text": 1, "kind": "length", "from_unit": "m", "to_unit": "ft"}, "convert units,meters feet,kilograms pounds,celsius fahrenheit,unit conversion", icon="ruler", instructions="Select a measurement and two units from that same group. Data uses decimal kB/MB/GB and binary KiB/MiB/GiB. Gallons and cups are US customary. Temperature conversion rejects values below absolute zero.")
REGISTRY["unit-converter"]["unit_groups"] = UNIT_GROUPS
add("percentage-calculator", "Percentage Calculator", "utilities", "Calculate percentages, percentage changes, increases and decreases.", [number("text", "First value (A)", 20, -1e100, 1e100, step="any"), number("second", "Second value (B)", 100, -1e100, 1e100, step="any"), select("operation", "Calculation", [("percent-of", "A% of B"), ("what-percent", "A is what % of B?"), ("change", "Percentage change from A to B"), ("increase", "Increase A by B%"), ("decrease", "Decrease A by B%")])], {"text": 20, "second": 100, "operation": "percent-of"}, "percent calculator,percentage change,percent increase", icon="percent", instructions="Enter A and B, then choose the calculation. Percentage change divides the difference by the absolute starting value. A zero reference value cannot define a percentage.")
add("age-calculator", "Age Calculator", "utilities", "Calculate age in calendar years, months and days on a chosen date.", [field("text", "Date of birth", "date", required=True), field("second", "Age on date (blank uses today in UTC)", "date")], {"text": "2000-01-15", "second": "2026-10-19"}, "birthday calculator,age in days,calculate age", icon="cake", extension="json")

# File tools are maintained separately but participate in identical routing/search.
try:
    from .file_registry import FILE_TOOLS
except ModuleNotFoundError as exc:
    if exc.name != __package__ + ".file_registry":
        raise
    FILE_TOOLS = []

REGISTRY.update(FILE_TOOLS if isinstance(FILE_TOOLS, dict) else {tool["slug"]: tool for tool in FILE_TOOLS})
for _tool in REGISTRY.values():
    if not _tool.get("related_tools"):
        _tool["related_tools"] = [t["slug"] for t in REGISTRY.values() if t["category"] == _tool["category"] and t["slug"] != _tool["slug"]][:3]

TOOLS = [tool for tool in REGISTRY.values() if tool['status'] == 'available']


def search_tools(query="", category=""):
    """Return only working tools; score phrases, aliases and typo-tolerant words."""
    candidates = [tool for tool in TOOLS if tool["status"] == "available" and (not category or category == "all" or tool["category"] == category)]
    query = re.sub(r"[^\w\s]", " ", query.casefold())[:100].strip()
    if not query:
        return candidates
    tokens = query.split()
    results = []
    for tool in candidates:
        name = tool["name"].casefold()
        aliases = [name, tool["slug"].replace("-", " ")] + [str(alias).casefold() for alias in tool.get("keywords", [])]
        corpus = " ".join(aliases) + " " + tool["description"].casefold()
        exact = max((1.0 if query == alias else (0.85 if query in alias else 0.0)) for alias in aliases)
        word_scores = [max((SequenceMatcher(None, token, word).ratio() if len(token) > 2 else float(token == word) for word in corpus.split()), default=0) for token in tokens]
        average = sum(word_scores) / len(word_scores)
        phrase = max(SequenceMatcher(None, query, alias).ratio() for alias in aliases)
        score = max(exact, average * .78, phrase * .8)
        if exact or (min(word_scores) >= .66 and average >= .76) or phrase >= .73:
            results.append((score + (.02 if query in name else 0), tool))
    return [tool for _, tool in sorted(results, key=lambda item: (-item[0], item[1]["name"]))]
