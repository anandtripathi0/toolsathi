"""Bounded text/developer tools. User code is never evaluated or executed."""
from __future__ import annotations

import base64
import binascii
import colorsys
import csv
import difflib
import hashlib
import html
import http
import io
import json
import math
import re
import secrets
import string
import unicodedata
import uuid
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, unquote, urlparse
from xml.sax.saxutils import escape as xml_escape

MAX_TEXT = 200_000


def _text(data, name="text", default=""):
    value = str(data.get(name, default))
    if len(value) > MAX_TEXT:
        raise ValueError(f"{name.replace('_', ' ').title()} is limited to 200,000 characters.")
    return value


def _number(data, name, default=0, minimum=None, maximum=None, integer=False):
    raw = data.get(name, default)
    try:
        number = float(raw)
        if not math.isfinite(number):
            raise ValueError
        if integer and not number.is_integer():
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        raise ValueError(f"Enter a valid {'whole ' if integer else ''}number for {name.replace('_', ' ')}.") from None
    if minimum is not None and number < minimum:
        raise ValueError(f"{name.replace('_', ' ').title()} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise ValueError(f"{name.replace('_', ' ').title()} must be at most {maximum}.")
    return int(number) if integer else number


def _choice(data, name, choices, default):
    value = data.get(name, default)
    if value not in choices:
        raise ValueError(f"Choose a supported {name.replace('_', ' ')}.")
    return value


def _flag(data, name, default=False):
    return str(data.get(name, default)).lower() in ("true", "1", "on", "yes")


def _json(text):
    try:
        return json.loads(text, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"{value} is not valid JSON.")))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}.") from None
    except RecursionError:
        raise ValueError("JSON nesting is too deep.") from None


def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)


def _slug(text):
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


def _rgb(value):
    value = value.strip().lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{3}", value):
        value = "".join(c * 2 for c in value)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise ValueError("Enter a 3- or 6-digit HEX color, such as #2563eb.")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#" + "".join(f"{round(max(0, min(255, c))):02x}" for c in rgb)


def _date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("Enter a valid date in YYYY-MM-DD format.") from None


def _iso_datetime(value):
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except ValueError:
        raise ValueError("Enter an ISO date/time, for example 2026-01-01T12:00:00Z. Times without an offset use UTC.") from None


def _http_url(value, name="URL"):
    parsed = urlparse(value)
    if parsed.scheme not in ("https", "http") or not parsed.netloc or any(c.isspace() for c in value):
        raise ValueError(f"Enter an absolute HTTP or HTTPS {name}.")
    return value


def _result(text, slug, extension="txt", mime="text/plain; charset=utf-8", **extra):
    text = str(text)
    if len(text.encode("utf-8")) > 3_000_000:
        raise ValueError("The result exceeds the 3 MB output limit. Try a smaller input.")
    return {"text": text, "filename": f"{slug}.{extension}", "mime": mime, **extra}


def process(slug, data):
    """Process a published tool, returning a download and optional safe preview."""
    for key, value in data.items():
        if len(str(value)) > MAX_TEXT:
            raise ValueError("Each input is limited to 200,000 characters.")
    try:
        return _process(slug, data)
    except (RecursionError, MemoryError):
        raise ValueError("Input is too complex. Reduce its size or nesting depth.") from None


def _process(slug, data):
    text = _text(data)
    result = lambda value, **kw: _result(value, slug, **kw)

    if slug in ("json-formatter", "json-validator", "json-minifier", "json-to-yaml"):
        obj = _json(text)
        if slug == "json-validator":
            return result("Valid JSON.\n\n" + _dump({"type": type(obj).__name__, "items": len(obj) if isinstance(obj, (dict, list)) else 1}))
        if slug == "json-to-yaml":
            import yaml
            return result(yaml.safe_dump(obj, allow_unicode=True, sort_keys=False), extension="yaml", mime="application/yaml")
        output = json.dumps(obj, ensure_ascii=False, indent=2 if slug == "json-formatter" else None, separators=None if slug == "json-formatter" else (",", ":"), allow_nan=False)
        return result(output, extension="json", mime="application/json")

    if slug in ("json-diff", "text-diff-checker"):
        second = _text(data, "second")
        if slug == "json-diff":
            text, second = (json.dumps(_json(s), ensure_ascii=False, indent=2, sort_keys=True) for s in (text, second))
        if text == second:
            return result("Inputs are identical.")
        diff = "\n".join(difflib.unified_diff(text.splitlines(), second.splitlines(), fromfile="original", tofile="changed", lineterm=""))
        return result(diff or "The text content is identical, but line-ending conventions or the final newline differ.")

    if slug == "json-to-csv":
        obj = _json(text)
        if not isinstance(obj, list) or not obj or not all(isinstance(row, dict) for row in obj):
            raise ValueError("Enter a non-empty JSON array of objects. Object keys become CSV columns.")
        keys = list(dict.fromkeys(key for row in obj for key in row))
        if len(keys) > 500:
            raise ValueError("CSV output is limited to 500 columns.")
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writerow({key: ("'" + key if key.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else key) for key in keys})
        for row in obj:
            safe_row = {}
            for key, val in row.items():
                val = json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else ("" if val is None else str(val))
                # Mitigate spreadsheet formula execution in downloaded CSVs.
                if val.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                    val = "'" + val
                safe_row[key] = val
            writer.writerow(safe_row)
        return result(stream.getvalue(), extension="csv", mime="text/csv; charset=utf-8")

    if slug == "csv-to-json":
        delimiter = _choice(data, "delimiter", [",", ";", "\t", "|"], ",")
        try:
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter, strict=True)
            if not reader.fieldnames or any(not name for name in reader.fieldnames):
                raise ValueError("CSV needs a header row with non-empty column names.")
            if len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError("CSV column names must be unique.")
            rows = list(reader)
            if any(None in row or any(v is None for v in row.values()) for row in rows):
                raise ValueError("Each CSV row must contain the same number of columns as the header.")
        except csv.Error as exc:
            raise ValueError(f"Invalid CSV: {exc}.") from None
        return result(_dump(rows), extension="json", mime="application/json")

    if slug == "yaml-to-json":
        import yaml
        try:
            # Shared aliases can expand exponentially when serialized as JSON.
            if any(isinstance(token, yaml.tokens.AliasToken) for token in yaml.scan(text)):
                raise ValueError("YAML aliases are unsupported; expand them into ordinary values first.")
            obj = yaml.safe_load(text)
            output = json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)
        except (yaml.YAMLError, TypeError, ValueError):
            raise ValueError("Enter safe YAML containing JSON-compatible values. Dates should be quoted; recursive aliases and non-finite numbers are unsupported.") from None
        return result(output, extension="json", mime="application/json")

    if slug == "xml-formatter":
        from defusedxml import minidom
        from defusedxml.common import DefusedXmlException
        from xml.parsers.expat import ExpatError
        try:
            document = minidom.parseString(text, forbid_dtd=True, forbid_entities=True, forbid_external=True)
            formatted = document.toprettyxml(indent="  ")
            document.unlink()
        except (DefusedXmlException, ExpatError) as exc:
            raise ValueError(f"Invalid or unsafe XML: {exc}.") from None
        return result(formatted, extension="xml", mime="application/xml")

    if slug == "html-formatter":
        from bs4 import BeautifulSoup
        return result(BeautifulSoup(text, "html.parser").prettify(), extension="html", mime="text/html; charset=utf-8")
    if slug in ("javascript-formatter", "css-formatter"):
        if slug == "javascript-formatter":
            import jsbeautifier
            formatted = jsbeautifier.beautify(text)
        else:
            import cssbeautifier
            formatted = cssbeautifier.beautify(text)
        return result(formatted, extension="js" if slug.startswith("javascript") else "css")
    if slug == "sql-formatter":
        import sqlparse
        return result(sqlparse.format(text, reindent=True, keyword_case="upper"), extension="sql")

    if slug in ("base64-encoder-decoder", "url-encoder-decoder", "html-entity-encoder-decoder"):
        operation = _choice(data, "operation", ["encode", "decode"], "encode")
        if slug.startswith("base64"):
            try:
                output = base64.b64encode(text.encode()).decode() if operation == "encode" else base64.b64decode(re.sub(r"\s+", "", text), validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError):
                raise ValueError("Enter valid Base64 that decodes to UTF-8 text.") from None
        elif slug.startswith("url"):
            try:
                if operation == "decode" and re.search(r"%(?![0-9a-fA-F]{2})", text):
                    raise ValueError("Every percent escape must contain two hexadecimal digits, for example %20.")
                output = quote(text, safe="") if operation == "encode" else unquote(text, errors="strict")
            except UnicodeDecodeError:
                raise ValueError("Percent-encoded bytes must decode to valid UTF-8 text.") from None
        else:
            output = html.escape(text, quote=True) if operation == "encode" else html.unescape(text)
        return result(output)

    if slug == "jwt-decoder":
        parts = text.strip().split(".")
        if len(parts) != 3:
            raise ValueError("Enter a JWT with three dot-separated sections (header.payload.signature).")
        try:
            if not all(re.fullmatch(r"[A-Za-z0-9_-]+", part) for part in parts[:2]) or not re.fullmatch(r"[A-Za-z0-9_-]*", parts[2]):
                raise ValueError
            decoded = [_json(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)).decode()) for part in parts[:2]]
            if not all(isinstance(value, dict) for value in decoded):
                raise ValueError
        except (ValueError, UnicodeDecodeError, binascii.Error):
            raise ValueError("The JWT header or payload is not valid Base64URL-encoded JSON.") from None
        return result(_dump({"warning": "Decoded only. Signature NOT verified. Do not trust this token for authentication.", "header": decoded[0], "payload": decoded[1]}), extension="json", mime="application/json")

    if slug == "regex-tester":
        import regex
        pattern = _text(data, "pattern")
        if len(pattern) > 2000:
            raise ValueError("Regex patterns are limited to 2,000 characters.")
        flags = (regex.I if _flag(data, "ignore_case") else 0) | (regex.M if _flag(data, "multiline") else 0)
        try:
            compiled = regex.compile(pattern, flags)
            matches = []
            for match in compiled.finditer(text, timeout=0.05):
                matches.append({"match": match.group(), "start": match.start(), "end": match.end(), "groups": match.groups()})
                if len(matches) >= 1000:
                    break
        except TimeoutError:
            raise ValueError("This expression exceeded the 50 ms safety limit. Simplify the expression.") from None
        except regex.error as exc:
            raise ValueError(f"Invalid regular expression: {exc}.") from None
        return result(_dump({"matches": matches, "count": len(matches), "limit": 1000}), extension="json", mime="application/json")

    if slug == "uuid-generator":
        return result("\n".join(str(uuid.uuid4()) for _ in range(_number(data, "count", 5, 1, 1000, True))))
    if slug == "uuid-validator":
        try:
            parsed = uuid.UUID(text.strip())
        except (ValueError, AttributeError):
            raise ValueError("Enter a valid UUID, such as 550e8400-e29b-41d4-a716-446655440000.") from None
        return result(_dump({"valid": True, "canonical": str(parsed), "version": parsed.version, "variant": parsed.variant}), extension="json", mime="application/json")

    if slug == "unix-timestamp-converter":
        operation = _choice(data, "operation", ["to-date", "to-timestamp"], "to-date")
        unit = _choice(data, "unit", ["seconds", "milliseconds"], "seconds")
        if operation == "to-date":
            try:
                stamp = float(text)
                dt = datetime.fromtimestamp(stamp / (1000 if unit == "milliseconds" else 1), timezone.utc)
            except (ValueError, OverflowError, OSError):
                raise ValueError("Enter a timestamp within the supported year range (1–9999).") from None
            return result(dt.isoformat().replace("+00:00", "Z"))
        dt = _iso_datetime(text)
        return result(f"{dt.timestamp() * (1000 if unit == 'milliseconds' else 1):.6f}".rstrip("0").rstrip("."))

    if slug == "cron-expression-parser":
        from croniter import croniter, CroniterBadCronError, CroniterBadDateError
        if len(text.split()) != 5:
            raise ValueError("Enter a standard five-field cron expression: minute hour day month weekday.")
        base = _iso_datetime(_text(data, "start") or datetime.now(timezone.utc).isoformat())
        try:
            iterator = croniter(text, base, max_years_between_matches=5)
            dates = [iterator.get_next(datetime).isoformat().replace("+00:00", "Z") for _ in range(10)]
        except (CroniterBadCronError, CroniterBadDateError, ValueError, OverflowError):
            raise ValueError("Invalid cron expression, or no occurrence exists within five years. Use five fields and a valid calendar schedule.") from None
        return result("Next 10 occurrences (UTC):\n" + "\n".join(dates))

    if slug == "hash-generator":
        algorithm = _choice(data, "algorithm", ["sha256", "sha512"], "sha256")
        return result(hashlib.new(algorithm, text.encode("utf-8")).hexdigest())

    if slug in ("secure-password-generator", "random-string-generator"):
        length = _number(data, "length", 24, 4 if slug.startswith("secure") else 1, 1024, True)
        count = _number(data, "count", 1, 1, 100, True)
        alphabet_mode = _choice(data, "alphabet", ["alphanumeric", "letters", "digits", "hex", "symbols"], "symbols" if slug.startswith("secure") else "alphanumeric")
        groups = {"alphanumeric": [string.ascii_lowercase, string.ascii_uppercase, string.digits], "letters": [string.ascii_lowercase, string.ascii_uppercase], "digits": [string.digits], "hex": ["0123456789abcdef"], "symbols": [string.ascii_lowercase, string.ascii_uppercase, string.digits, "!@#$%^&*()-_=+[]{}:,.?"]}[alphabet_mode]
        alphabet = "".join(groups)
        values = []
        for _ in range(count):
            chars = [secrets.choice(alphabet) for _ in range(length)]
            if slug.startswith("secure"):
                chars[:len(groups)] = [secrets.choice(group) for group in groups]
                secrets.SystemRandom().shuffle(chars)
            values.append("".join(chars))
        return result("\n".join(values))

    if slug == "markdown-editor":
        import bleach
        import markdown
        tags = set(bleach.sanitizer.ALLOWED_TAGS) | {"p", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "code", "hr", "br", "table", "thead", "tbody", "tr", "th", "td", "del"}
        rendered = bleach.clean(markdown.markdown(text, extensions=["fenced_code", "tables", "sane_lists"]), tags=tags, attributes={"a": ["href", "title"], "code": ["class"]}, strip=True)
        return result(rendered, extension="html", mime="text/html; charset=utf-8", preview_html=rendered)

    if slug in ("html-playground", "css-playground"):
        if slug == "css-playground":
            # CSS is output as inert text and rendered only by a sandboxed client iframe.
            markup = _text(data, "second", '<div class="card">Hello, ToolSathi!</div>')
            output = f"<!doctype html><html><head><meta charset=\"utf-8\"><style>{text}</style></head><body>{markup}</body></html>"
        else:
            output = text
        return result(output, extension="html", mime="text/html; charset=utf-8", preview_html=output)

    if slug == "http-status-code-reference":
        query = text.strip().lower()
        statuses = [{"code": item.value, "phrase": item.phrase, "description": item.description} for item in http.HTTPStatus if not query or query in str(item.value) or query in item.phrase.lower() or query in item.description.lower()]
        if not statuses:
            raise ValueError("No standard HTTP status matches this code or phrase.")
        return result(_dump(statuses), extension="json", mime="application/json")

    if slug == "user-agent-parser":
        from user_agents import parse
        agent = parse(text)
        return result(_dump({"browser": str(agent.browser), "operating_system": str(agent.os), "device": str(agent.device), "is_mobile": agent.is_mobile, "is_tablet": agent.is_tablet, "is_pc": agent.is_pc, "is_bot": agent.is_bot, "note": "Heuristic result; user-agent strings can be spoofed."}), extension="json", mime="application/json")

    if slug in ("word-counter", "character-counter"):
        import regex
        words = regex.findall(r"[\p{L}\p{N}_][\p{L}\p{M}\p{N}_]*(?:['’][\p{L}\p{M}\p{N}_]+)*", text)
        return result(_dump({"words": len(words), "characters": len(text), "characters_without_whitespace": sum(not c.isspace() for c in text), "lines": len(text.splitlines()) if text else 0, "paragraphs": len([p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]), "estimated_reading_seconds_at_200_wpm": math.ceil(len(words) * 0.3), "note": "Characters count Unicode code points; word counts use Unicode word boundaries."}), extension="json", mime="application/json")

    if slug == "case-converter":
        mode = _choice(data, "operation", ["upper", "lower", "title", "sentence", "swap", "camel", "snake", "kebab"], "title")
        words = re.findall(r"[^\W_]+", text, re.UNICODE)
        output = {"upper": lambda: text.upper(), "lower": lambda: text.lower(), "title": lambda: text.title(), "sentence": lambda: re.sub(r"(^|[.!?]\s+)(\w)", lambda m: m[1] + m[2].upper(), text.lower()), "swap": lambda: text.swapcase(), "camel": lambda: (words[0].lower() + "".join(w.title() for w in words[1:])) if words else "", "snake": lambda: "_".join(w.lower() for w in words), "kebab": lambda: "-".join(w.lower() for w in words)}[mode]()
        return result(output)

    if slug == "duplicate-line-remover":
        seen, lines = set(), []
        for line in text.splitlines():
            key = line.casefold() if _flag(data, "ignore_case") else line
            if key not in seen:
                seen.add(key)
                lines.append(line)
        return result("\n".join(lines))

    if slug == "text-sorter":
        mode = _choice(data, "operation", ["ascending", "descending", "numeric", "length"], "ascending")
        lines = text.splitlines()
        try:
            if mode == "numeric":
                values = [(Decimal(line.strip()), line) for line in lines]
                if any(not value.is_finite() for value, _ in values):
                    raise InvalidOperation
                lines = [line for _, line in sorted(values, key=lambda row: row[0])]
            else:
                lines.sort(key=len if mode == "length" else str.casefold, reverse=mode == "descending")
        except (ValueError, InvalidOperation):
            raise ValueError("Numeric sorting requires one finite number per line.") from None
        return result("\n".join(lines))

    if slug == "find-and-replace":
        find = _text(data, "find")
        if not find:
            raise ValueError("Enter the text to find.")
        replacement = _text(data, "replacement")
        if len(replacement) * max(1, len(text) // len(find)) > 3_000_000:
            raise ValueError("The replacement could exceed the 3 MB output limit.")
        if _flag(data, "ignore_case"):
            output = re.sub(re.escape(find), lambda match: replacement, text, flags=re.IGNORECASE)
        else:
            output = text.replace(find, replacement)
        return result(output)

    if slug == "whitespace-remover":
        mode = _choice(data, "operation", ["trim", "collapse", "all", "blank-lines"], "trim")
        output = {"trim": lambda: "\n".join(line.strip() for line in text.splitlines()), "collapse": lambda: re.sub(r"\s+", " ", text).strip(), "all": lambda: re.sub(r"\s", "", text), "blank-lines": lambda: "\n".join(line for line in text.splitlines() if line.strip())}[mode]()
        return result(output)

    if slug == "lorem-ipsum-generator":
        paragraph = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur."
        count = _number(data, "count", 3, 1, 100, True)
        return result("\n\n".join(paragraph for _ in range(count)))

    if slug == "text-reverser":
        mode = _choice(data, "operation", ["characters", "words", "lines"], "characters")
        if mode == "characters":
            import regex
            return result("".join(reversed(regex.findall(r"\X", text))))
        return result(" ".join(reversed(text.split())) if mode == "words" else "\n".join(reversed(text.splitlines())))

    if slug in ("text-to-slug", "seo-slug-generator"):
        return result(_slug(text))

    if slug in ("meta-tag-generator", "open-graph-generator"):
        title = html.escape(text, quote=True)
        description = html.escape(_text(data, "description"), quote=True)
        url = _text(data, "url").strip()
        if url:
            _http_url(url)
        if slug == "meta-tag-generator":
            output = f'<title>{title}</title>\n<meta name="description" content="{description}">\n<meta name="viewport" content="width=device-width, initial-scale=1">'
            if url:
                output += f'\n<link rel="canonical" href="{html.escape(url, quote=True)}">'
        else:
            values = {"og:title": text, "og:description": _text(data, "description"), "og:type": _choice(data, "og_type", ["website", "article"], "website")}
            if url:
                values["og:url"] = url
            image_url = _text(data, "image_url").strip()
            if image_url:
                values["og:image"] = _http_url(image_url, "image URL")
            output = "\n".join(f'<meta property="{key}" content="{html.escape(value, quote=True)}">' for key, value in values.items())
        return result(output, extension="html", mime="text/html; charset=utf-8")

    if slug == "robots-txt-generator":
        agent = _text(data, "agent", "*").strip()
        if not agent or "\n" in agent or "\r" in agent:
            raise ValueError("Enter one user-agent value without newlines.")
        paths = [line.strip() for line in text.splitlines() if line.strip()]
        if any(not path.startswith("/") or "#" in path for path in paths):
            raise ValueError("Each disallowed path must begin with / and contain no # comment.")
        lines = [f"User-agent: {agent}"] + ([f"Disallow: {path}" for path in paths] or ["Disallow:"])
        sitemap = _text(data, "sitemap").strip()
        if sitemap:
            lines += ["", "Sitemap: " + _http_url(sitemap, "sitemap URL")]
        return result("\n".join(lines) + "\n")

    if slug == "xml-sitemap-generator":
        urls = list(dict.fromkeys(line.strip() for line in text.splitlines() if line.strip()))
        if not urls or len(urls) > 1000:
            raise ValueError("Enter between 1 and 1,000 URLs, one per line.")
        entries = "\n".join("  <url><loc>" + xml_escape(_http_url(url)) + "</loc></url>" for url in urls)
        return result('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + entries + "\n</urlset>", extension="xml", mime="application/xml")

    if slug == "keyword-density-analyzer":
        import regex
        words = regex.findall(r"[\p{L}\p{N}_][\p{L}\p{M}\p{N}_]*(?:['’][\p{L}\p{M}\p{N}_]+)*", text.casefold())
        n = _number(data, "phrase_length", 1, 1, 3, True)
        phrases = [" ".join(words[i:i + n]) for i in range(max(0, len(words) - n + 1))]
        counts = Counter(phrases)
        return result(_dump({"word_count": len(words), "phrase_length": n, "phrase_positions": len(phrases), "density_definition": "Occurrences divided by all phrase positions, multiplied by 100.", "keywords": [{"keyword": key, "count": count, "density_percent": round(count / len(phrases) * 100, 3)} for key, count in counts.most_common(100)]}), extension="json", mime="application/json")

    if slug == "heading-structure-analyzer":
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, "html.parser")
        headings = [{"level": int(tag.name[1]), "text": tag.get_text(" ", strip=True)} for tag in soup.find_all(re.compile(r"^h[1-6]$"))]
        issues = []
        h1 = sum(item["level"] == 1 for item in headings)
        if h1 != 1:
            issues.append(f"Found {h1} H1 headings. One clear page heading is usually helpful.")
        for index, item in enumerate(headings):
            if not item["text"]:
                issues.append(f"Heading {index + 1} is empty.")
            if index and item["level"] > headings[index - 1]["level"] + 1:
                issues.append(f"Heading {index + 1} skips a level (H{headings[index - 1]['level']} to H{item['level']}).")
        return result(_dump({"headings": headings, "suggestions": issues}), extension="json", mime="application/json")

    if slug in ("hex-to-rgb", "hex-to-hsl", "color-palette-generator", "contrast-checker"):
        rgb = _rgb(text)
        if slug == "hex-to-rgb":
            return result(f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})")
        hue, lightness, saturation = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
        if slug == "hex-to-hsl":
            return result(f"hsl({hue * 360:.1f}, {saturation * 100:.1f}%, {lightness * 100:.1f}%)")
        if slug == "color-palette-generator":
            palette_mode = _choice(data, "operation", ["analogous", "complementary", "triadic", "shades"], "analogous")
            shifts = {"analogous": [-1/6, -1/12, 0, 1/12, 1/6], "complementary": [0, 0.5], "triadic": [0, 1/3, 2/3]}
            palette = [_hex(tuple(c * 255 for c in colorsys.hls_to_rgb(hue, level, saturation))) for level in (0.15, 0.30, 0.50, 0.70, 0.90)] if palette_mode == "shades" else [_hex(tuple(c * 255 for c in colorsys.hls_to_rgb((hue + shift) % 1, lightness, saturation))) for shift in shifts[palette_mode]]
            return result("\n".join(palette))
        second = _rgb(_text(data, "second", "#ffffff"))
        def luminance(color):
            linear = [(c / 255 / 12.92 if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4) for c in color]
            return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
        light, dark = sorted((luminance(rgb), luminance(second)), reverse=True)
        ratio = (light + 0.05) / (dark + 0.05)
        return result(_dump({"contrast_ratio": round(ratio, 2), "WCAG_AA_normal_text": ratio >= 4.5, "WCAG_AA_large_text": ratio >= 3, "WCAG_AAA_normal_text": ratio >= 7, "WCAG_AAA_large_text": ratio >= 4.5, "large_text_definition": "At least 18pt regular or 14pt bold."}), extension="json", mime="application/json")

    if slug == "rgb-to-hex":
        rgb = tuple(_number(data, name, default, 0, 255, True) for name, default in (("red", 37), ("green", 99), ("blue", 235)))
        return result(_hex(rgb))

    if slug == "css-gradient-generator":
        first, second = _hex(_rgb(text)), _hex(_rgb(_text(data, "second", "#ffffff")))
        angle = _number(data, "angle", 135, -360, 360)
        return result(f"background: linear-gradient({angle:g}deg, {first} 0%, {second} 100%);", extension="css")

    if slug == "css-box-shadow-generator":
        x, y = (_number(data, field, default, -500, 500) for field, default in (("x", 0), ("y", 8)))
        blur = _number(data, "blur", 24, 0, 500)
        spread = _number(data, "spread", 0, -500, 500)
        opacity = _number(data, "opacity", 0.12, 0, 1)
        color = _rgb(text or "#000000")
        inset = "inset " if _flag(data, "inset") else ""
        return result(f"box-shadow: {inset}{x:g}px {y:g}px {blur:g}px {spread:g}px rgba({color[0]}, {color[1]}, {color[2]}, {opacity:g});", extension="css")

    if slug == "css-border-radius-generator":
        values = [_number(data, field, 16, 0, 1000) for field in ("top_left", "top_right", "bottom_right", "bottom_left")]
        unit = _choice(data, "unit", ["px", "%", "rem"], "px")
        return result("border-radius: " + " ".join(f"{value:g}{unit}" for value in values) + ";", extension="css")

    if slug == "css-clamp-generator":
        minimum = _number(data, "minimum", 16, 0, 1000)
        maximum = _number(data, "maximum", 48, 0, 1000)
        min_width = _number(data, "min_width", 320, 1, 10000)
        max_width = _number(data, "max_width", 1440, 1, 10000)
        if maximum < minimum or max_width <= min_width:
            raise ValueError("Maximum size must be at least the minimum size, and maximum viewport must exceed minimum viewport.")
        slope = (maximum - minimum) / (max_width - min_width)
        intercept = minimum - slope * min_width
        return result(f"font-size: clamp({minimum:g}px, {intercept:.4f}px + {slope * 100:.4f}vw, {maximum:g}px);", extension="css")

    if slug == "qr-code-generator":
        import qrcode
        from qrcode.exceptions import DataOverflowError
        if not text or len(text.encode()) > 2000:
            raise ValueError("Enter between 1 and 2,000 UTF-8 bytes of text for the QR code.")
        try:
            qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=_number(data, "scale", 8, 2, 20, True), border=4)
            qr.add_data(text)
            qr.make(fit=True)
            image = qr.make_image(fill_color="black", back_color="white")
            stream = io.BytesIO()
            image.save(stream, format="PNG")
        except DataOverflowError:
            raise ValueError("The text is too large for one QR code. Use a shorter value.") from None
        return {"text": "QR code generated. Download the PNG image.", "data": stream.getvalue(), "filename": "qr-code.png", "mime": "image/png"}

    if slug == "random-number-generator":
        lower = _number(data, "minimum", 1, -1_000_000_000_000, 1_000_000_000_000, True)
        upper = _number(data, "maximum", 100, -1_000_000_000_000, 1_000_000_000_000, True)
        count = _number(data, "count", 10, 1, 1000, True)
        if lower > upper:
            raise ValueError("Maximum must be greater than or equal to minimum.")
        if _flag(data, "unique"):
            if count > upper - lower + 1:
                raise ValueError("The range contains fewer unique values than requested.")
            values = secrets.SystemRandom().sample(range(lower, upper + 1), count)
        else:
            values = [lower + secrets.randbelow(upper - lower + 1) for _ in range(count)]
        return result("\n".join(map(str, values)))

    if slug in ("date-difference-calculator", "age-calculator"):
        from dateutil.relativedelta import relativedelta
        first = _date(text)
        second = _date(_text(data, "second") or datetime.now(timezone.utc).date().isoformat())
        if slug == "age-calculator" and first > second:
            raise ValueError("Date of birth must be on or before the comparison date.")
        start, end = sorted((first, second))
        delta = relativedelta(end, start)
        days = (end - start).days
        return result(_dump({"calendar_years": delta.years, "calendar_months": delta.months, "calendar_days": delta.days, "total_days": days, "total_weeks": round(days / 7, 6), "direction": "forward" if second >= first else "backward", "note": "Date-only calculation; the final date is excluded."}), extension="json", mime="application/json")

    if slug == "unit-converter":
        value = _number(data, "text", 1, -1e100, 1e100)
        kind = _choice(data, "kind", ["length", "mass", "temperature", "area", "volume", "speed", "data"], "length")
        units = {"length": {"mm": .001, "cm": .01, "m": 1, "km": 1000, "in": .0254, "ft": .3048, "yd": .9144, "mi": 1609.344}, "mass": {"mg": .000001, "g": .001, "kg": 1, "oz": .028349523125, "lb": .45359237}, "area": {"m2": 1, "km2": 1e6, "ft2": .09290304, "acre": 4046.8564224, "hectare": 10000}, "volume": {"mL": .001, "L": 1, "m3": 1000, "US-gal": 3.785411784, "US-cup": .2365882365}, "speed": {"m/s": 1, "km/h": 1 / 3.6, "mph": .44704, "knot": .5144444444}, "data": {"B": 1, "kB": 1000, "MB": 1e6, "GB": 1e9, "KiB": 1024, "MiB": 1024 ** 2, "GiB": 1024 ** 3}}
        available = ["C", "F", "K"] if kind == "temperature" else list(units[kind])
        source = _choice(data, "from_unit", available, available[0])
        target = _choice(data, "to_unit", available, available[1])
        if kind == "temperature":
            celsius = (value - 32) * 5 / 9 if source == "F" else (value - 273.15 if source == "K" else value)
            if celsius < -273.150000001:
                raise ValueError("Temperature cannot be below absolute zero.")
            converted = celsius * 9 / 5 + 32 if target == "F" else (celsius + 273.15 if target == "K" else celsius)
        else:
            converted = value * units[kind][source] / units[kind][target]
        return result(f"{value:.12g} {source} = {converted:.12g} {target}")

    if slug == "percentage-calculator":
        a, b = _number(data, "text", 20, -1e100, 1e100), _number(data, "second", 100, -1e100, 1e100)
        mode = _choice(data, "operation", ["percent-of", "what-percent", "change", "increase", "decrease"], "percent-of")
        if mode in ("what-percent", "change") and (b == 0 if mode == "what-percent" else a == 0):
            raise ValueError("Cannot calculate a percentage with a zero reference value.")
        output = {"percent-of": lambda: f"{a:g}% of {b:g} = {a / 100 * b:.12g}", "what-percent": lambda: f"{a:g} is {a / b * 100:.12g}% of {b:g}", "change": lambda: f"Change from {a:g} to {b:g}: {(b - a) / abs(a) * 100:.12g}%", "increase": lambda: f"{a:g} increased by {b:g}% = {a * (1 + b / 100):.12g}", "decrease": lambda: f"{a:g} decreased by {b:g}% = {a * (1 - b / 100):.12g}"}[mode]()
        return result(output)

    raise ValueError("This tool is not available.")
