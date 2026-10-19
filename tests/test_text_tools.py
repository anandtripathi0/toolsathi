import base64
import hashlib
import io
import json
import re
import unittest
import uuid

from apps.tools.registry import REGISTRY, search_tools
from tools_logic.text_tools import process


class TextToolTests(unittest.TestCase):
    def run_tool(self, slug, **values):
        return process(slug, values)["text"]

    def test_all_published_text_tools_have_working_examples(self):
        tools = [tool for tool in REGISTRY.values() if tool["handler"] == "text"]
        self.assertEqual(len(tools), 63)
        for tool in tools:
            with self.subTest(tool=tool["slug"]):
                values = {field["name"]: field["default"] for field in tool["fields"]}
                values.update(tool["example"])
                output = process(tool["slug"], values)
                self.assertTrue(output["text"])
                self.assertTrue(output["filename"])
                self.assertTrue(output["mime"])
                self.assertTrue(tool["instructions"])
                self.assertTrue(tool["related_tools"])
                self.assertEqual(set(values), {field["name"] for field in tool["fields"]})

    def test_json_formatter_and_minifier_preserve_values(self):
        source = '{"emoji":"☀","array":[1,true,null],"number":2.5}'
        for slug in ("json-formatter", "json-minifier"):
            self.assertEqual(json.loads(self.run_tool(slug, text=source)), json.loads(source))
        self.assertNotIn("\n", self.run_tool("json-minifier", text=source))

    def test_json_rejects_invalid_syntax_and_nonfinite_numbers(self):
        for source in ('{"a":}', "NaN", "Infinity", "[1,]", '{"x": -Infinity}'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.run_tool("json-validator", text=source)

    def test_json_diff_ignores_key_order(self):
        self.assertEqual(self.run_tool("json-diff", text='{"a":1,"b":2}', second='{"b":2,"a":1}'), "Inputs are identical.")
        self.assertIn("+", self.run_tool("json-diff", text='{"a":1}', second='{"a":2}'))

    def test_text_diff_separates_last_lines_and_reports_newline_changes(self):
        diff = self.run_tool("text-diff-checker", text="Hello", second="Bye")
        self.assertIn("-Hello\n+Bye", diff)
        self.assertIn("newline differ", self.run_tool("text-diff-checker", text="Hello", second="Hello\n"))

    def test_csv_conversion_preserves_quotes_and_newlines(self):
        rows = [{"name": 'A, "B"', "note": "line one\nline two"}, {"name": "C", "note": "03"}]
        csv_result = self.run_tool("json-to-csv", text=json.dumps(rows))
        self.assertEqual(json.loads(self.run_tool("csv-to-json", text=csv_result)), rows)

    def test_csv_formula_injection_is_neutralized_in_headers_and_cells(self):
        output = self.run_tool("json-to-csv", text='[{"=bad":"=SUM(A1)","name":"@unsafe"}]')
        self.assertIn("'=bad", output)
        self.assertIn("'=SUM(A1)", output)
        self.assertIn("'@unsafe", output)

    def test_csv_rejects_duplicate_headers_and_irregular_rows(self):
        for source in ("a,a\n1,2", "a,b\n1", "a,b\n1,2,3", ",b\n1,2"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.run_tool("csv-to-json", text=source)

    def test_yaml_round_trip(self):
        obj = {"name": "ToolSathi", "free": True, "values": [1, 2, None]}
        yaml_text = self.run_tool("json-to-yaml", text=json.dumps(obj))
        self.assertEqual(json.loads(self.run_tool("yaml-to-json", text=yaml_text)), obj)

    def test_yaml_rejects_objects_aliases_and_non_json_values(self):
        for source in ("!!python/object/apply:os.system ['echo unsafe']", "a: &a [*a]", "a: &a [1,2]\nb: *a", "a: .inf", "date: 2026-01-01"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.run_tool("yaml-to-json", text=source)

    def test_xml_rejects_external_entities(self):
        with self.assertRaises(ValueError):
            self.run_tool("xml-formatter", text='<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>')
        self.assertIn("<child/>", self.run_tool("xml-formatter", text="<root><child/></root>"))

    def test_encoding_round_trips_unicode(self):
        text = 'नमस्ते ☀ <a title="hello">&+?'
        for slug in ("base64-encoder-decoder", "url-encoder-decoder", "html-entity-encoder-decoder"):
            with self.subTest(slug=slug):
                encoded = self.run_tool(slug, text=text, operation="encode")
                self.assertEqual(self.run_tool(slug, text=encoded, operation="decode"), text)

    def test_encoding_invalid_utf8_reports_validation_error(self):
        for slug, source in (("base64-encoder-decoder", "/w=="), ("url-encoder-decoder", "%ff"), ("url-encoder-decoder", "%ZZ")):
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                self.run_tool(slug, text=source, operation="decode")

    def test_jwt_decoding_has_unverified_warning(self):
        encode = lambda value: base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
        token = encode({"alg": "HS256"}) + "." + encode({"sub": "123"}) + ".c2ln"
        output = json.loads(self.run_tool("jwt-decoder", text=token))
        self.assertEqual(output["payload"]["sub"], "123")
        self.assertIn("NOT verified", output["warning"])
        with self.assertRaises(ValueError):
            self.run_tool("jwt-decoder", text="@@@@.e30.sig")

    def test_regex_returns_positions_and_stops_pathological_matches(self):
        output = json.loads(self.run_tool("regex-tester", text="A1 b2", pattern=r"([a-z])(\d)", ignore_case=True))
        self.assertEqual(output["count"], 2)
        self.assertEqual(output["matches"][1]["start"], 3)
        with self.assertRaises(ValueError):
            self.run_tool("regex-tester", text="a" * 10000 + "!", pattern=r"(a+)+$")

    def test_uuid_generator_and_validator(self):
        generated = self.run_tool("uuid-generator", count=20).splitlines()
        self.assertEqual(len(set(generated)), 20)
        self.assertTrue(all(uuid.UUID(value).version == 4 for value in generated))
        self.assertTrue(json.loads(self.run_tool("uuid-validator", text=generated[0]))["valid"])

    def test_timestamp_roundtrip_utc_and_milliseconds(self):
        self.assertEqual(self.run_tool("unix-timestamp-converter", text="0"), "1970-01-01T00:00:00Z")
        self.assertEqual(self.run_tool("unix-timestamp-converter", text="1970-01-01T05:30:00+05:30", operation="to-timestamp"), "0")
        self.assertEqual(self.run_tool("unix-timestamp-converter", text="1500", unit="milliseconds"), "1970-01-01T00:00:01.500000Z")
        with self.assertRaises(ValueError):
            self.run_tool("unix-timestamp-converter", text="nan")

    def test_cron_schedule_is_explicit_utc(self):
        output = self.run_tool("cron-expression-parser", text="0 9 * * 1-5", start="2026-01-01T00:00:00Z")
        self.assertIn("2026-01-01T09:00:00Z", output)
        self.assertNotIn("2026-01-03T09:00:00Z", output)
        with self.assertRaises(ValueError):
            self.run_tool("cron-expression-parser", text="* * * * * *")

    def test_hashes_match_standard_library(self):
        self.assertEqual(self.run_tool("hash-generator", text="hello"), hashlib.sha256(b"hello").hexdigest())
        self.assertEqual(self.run_tool("hash-generator", text="hello", algorithm="sha512"), hashlib.sha512(b"hello").hexdigest())

    def test_secure_passwords_have_selected_groups(self):
        passwords = self.run_tool("secure-password-generator", length=24, count=30, alphabet="symbols").splitlines()
        self.assertEqual(len(set(passwords)), 30)
        for password in passwords:
            self.assertEqual(len(password), 24)
            self.assertRegex(password, r"[a-z]")
            self.assertRegex(password, r"[A-Z]")
            self.assertRegex(password, r"[0-9]")
            self.assertRegex(password, r"[^A-Za-z0-9]")
        with self.assertRaises(ValueError):
            self.run_tool("secure-password-generator", length=3)

    def test_markdown_strips_unsafe_markup(self):
        output = process("markdown-editor", {"text": '# Hello\n<script>alert(1)</script><img src=x onerror=alert(1)><a href="javascript:alert(1)">link</a>'})
        self.assertIn("<h1>Hello</h1>", output["text"])
        self.assertNotIn("<script", output["text"])
        self.assertNotIn("onerror", output["text"])
        self.assertNotIn("javascript:", output["text"])
        self.assertEqual(output["preview_html"], output["text"])

    def test_word_counts_empty_and_unicode(self):
        self.assertEqual(json.loads(self.run_tool("word-counter", text=""))["words"], 0)
        output = json.loads(self.run_tool("word-counter", text="Hello café\nWorld"))
        self.assertEqual(output["words"], 3)
        self.assertEqual(output["lines"], 2)
        self.assertEqual(json.loads(self.run_tool("word-counter", text="नमस्ते दुनिया"))["words"], 2)

    def test_reverse_keeps_unicode_graphemes_intact(self):
        self.assertEqual(self.run_tool("text-reverser", text="a👩‍💻e\u0301"), "e\u0301👩‍💻a")

    def test_text_transformations(self):
        self.assertEqual(self.run_tool("case-converter", text="every tool", operation="camel"), "everyTool")
        self.assertEqual(self.run_tool("duplicate-line-remover", text="A\na\nB", ignore_case=True), "A\nB")
        self.assertEqual(self.run_tool("text-sorter", text="10\n2\n-1", operation="numeric"), "-1\n2\n10")
        self.assertEqual(self.run_tool("find-and-replace", text="Aa A", find="a", replacement="$1", ignore_case=True), "$1$1 $1")
        self.assertEqual(self.run_tool("whitespace-remover", text=" a \n  b ", operation="collapse"), "a b")
        self.assertEqual(self.run_tool("text-to-slug", text="  Café & Crème! "), "cafe-creme")

    def test_meta_tags_escape_attribute_injection(self):
        output = self.run_tool("open-graph-generator", text='Title" onload="alert(1)', description="<script>bad</script>")
        self.assertIn("&quot;", output)
        self.assertIn("&lt;script&gt;", output)
        self.assertNotIn('<script>', output)
        with self.assertRaises(ValueError):
            self.run_tool("meta-tag-generator", text="Test", url="javascript:alert(1)")

    def test_sitemap_escapes_queries_and_removes_duplicates(self):
        output = self.run_tool("xml-sitemap-generator", text="https://example.com/?a=1&b=2\nhttps://example.com/?a=1&b=2")
        self.assertEqual(output.count("<url>"), 1)
        self.assertIn("&amp;", output)
        with self.assertRaises(ValueError):
            self.run_tool("xml-sitemap-generator", text="/relative")

    def test_robots_defaults_allow_crawling_and_rejects_newline_agent(self):
        self.assertEqual(self.run_tool("robots-txt-generator", text=""), "User-agent: *\nDisallow:\n")
        with self.assertRaises(ValueError):
            self.run_tool("robots-txt-generator", agent="*\nDisallow: /")

    def test_keyword_density_and_heading_structure(self):
        keywords = json.loads(self.run_tool("keyword-density-analyzer", text="cat cat dog"))["keywords"]
        self.assertEqual(keywords[0], {"keyword": "cat", "count": 2, "density_percent": 66.667})
        output = json.loads(self.run_tool("heading-structure-analyzer", text="<h1>Title</h1><h3>Skip</h3>"))
        self.assertIn("skips a level", output["suggestions"][0])

    def test_color_conversion_and_contrast_known_values(self):
        self.assertEqual(self.run_tool("hex-to-rgb", text="#f00"), "rgb(255, 0, 0)")
        self.assertEqual(self.run_tool("rgb-to-hex", red=255, green=0, blue=0), "#ff0000")
        self.assertEqual(self.run_tool("hex-to-hsl", text="#ff0000"), "hsl(0.0, 100.0%, 50.0%)")
        output = json.loads(self.run_tool("contrast-checker", text="#000", second="#fff"))
        self.assertEqual(output["contrast_ratio"], 21)
        self.assertTrue(output["WCAG_AAA_normal_text"])
        self.assertEqual(json.loads(self.run_tool("contrast-checker", text="#fff", second="#fff"))["contrast_ratio"], 1)

    def test_css_generators_validate_ranges(self):
        with self.assertRaises(ValueError):
            self.run_tool("css-clamp-generator", min_width=1000, max_width=320)
        with self.assertRaises(ValueError):
            self.run_tool("css-box-shadow-generator", opacity=2)
        self.assertIn("clamp(16px", self.run_tool("css-clamp-generator"))

    def test_qr_is_a_valid_png(self):
        from PIL import Image
        output = process("qr-code-generator", {"text": "https://example.com"})
        self.assertEqual(output["mime"], "image/png")
        image = Image.open(io.BytesIO(output["data"]))
        image.verify()
        self.assertEqual(image.format, "PNG")

    def test_random_numbers_are_bounded_and_unique_when_requested(self):
        numbers = [int(n) for n in self.run_tool("random-number-generator", minimum=-2, maximum=2, count=5, unique=True).splitlines()]
        self.assertEqual(set(numbers), {-2, -1, 0, 1, 2})
        with self.assertRaises(ValueError):
            self.run_tool("random-number-generator", minimum=1, maximum=2, count=3, unique=True)

    def test_calendar_date_difference_handles_leap_days(self):
        output = json.loads(self.run_tool("date-difference-calculator", text="2024-02-28", second="2024-03-01"))
        self.assertEqual(output["total_days"], 2)
        self.assertEqual(output["calendar_days"], 2)
        output = json.loads(self.run_tool("age-calculator", text="2000-01-15", second="2026-10-19"))
        self.assertEqual((output["calendar_years"], output["calendar_months"], output["calendar_days"]), (26, 9, 4))
        with self.assertRaises(ValueError):
            self.run_tool("age-calculator", text="2030-01-01", second="2026-01-01")

    def test_unit_conversions_and_absolute_zero(self):
        self.assertEqual(self.run_tool("unit-converter", text=1, kind="length", from_unit="m", to_unit="cm"), "1 m = 100 cm")
        self.assertEqual(self.run_tool("unit-converter", text=32, kind="temperature", from_unit="F", to_unit="C"), "32 F = 0 C")
        self.assertEqual(self.run_tool("unit-converter", text=1, kind="data", from_unit="MiB", to_unit="KiB"), "1 MiB = 1024 KiB")
        with self.assertRaises(ValueError):
            self.run_tool("unit-converter", text=-1, kind="temperature", from_unit="K", to_unit="C")
        with self.assertRaises(ValueError):
            self.run_tool("unit-converter", text=1, kind="mass", from_unit="m", to_unit="kg")

    def test_percentage_operations_and_zero_validation(self):
        self.assertEqual(self.run_tool("percentage-calculator", text=20, second=100), "20% of 100 = 20")
        self.assertEqual(self.run_tool("percentage-calculator", text=100, second=120, operation="change"), "Change from 100 to 120: 20%")
        with self.assertRaises(ValueError):
            self.run_tool("percentage-calculator", text=1, second=0, operation="what-percent")

    def test_limits_and_invalid_operations(self):
        with self.assertRaises(ValueError):
            self.run_tool("word-counter", text="a" * 200001)
        with self.assertRaises(ValueError):
            self.run_tool("uuid-generator", count=1001)
        with self.assertRaises(ValueError):
            self.run_tool("random-number-generator", minimum="NaN")
        with self.assertRaises(ValueError):
            self.run_tool("case-converter", operation="unknown")
        with self.assertRaises(ValueError):
            self.run_tool("missing-tool")

    def test_search_aliases_typo_tolerance_and_category_filter(self):
        for query, expected in (("json beautify", "json-formatter"), ("decode token", "jwt-decoder"), ("json formater", "json-formatter"), ("join pdf", "pdf-merger"), ("compress photo", "image-compressor"), ("photo 50kb", "image-compressor")):
            with self.subTest(query=query):
                self.assertEqual(search_tools(query)[0]["slug"], expected)
        self.assertTrue(all(tool["category"] == "text" for tool in search_tools("", "text")))
        self.assertEqual(search_tools("zzzzqqqqqqzzzz"), [])


if __name__ == "__main__":
    unittest.main()
