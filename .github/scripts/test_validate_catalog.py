"""Offline regression coverage; fixtures never contact external sites."""
import contextlib
import datetime as dt
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import validate_catalog as catalog


class FixedDate(dt.date):
    @classmethod
    def today(cls):
        return cls(2026, 11, 6)


ENTRY = """---
name: Example tool
category: Assess
maturity: Prototype
maintainer_name: Example Maintainer
maintainer_alias: example-owner
repo_url: https://example.com/tool
last_reviewed: 2026-11-06
---

# Example tool

## What it does

Describes a reusable tool.

## When to use it

- **Scenario:** A team needs a starting point.
- **What you get:** A report to review.

## Prerequisites

- **Access:** None
- **Tooling:** Python
- **Azure services:** None

## Limits

- Does not monitor workloads.
"""


class CatalogTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        for folder in ("assess", "build", "operate"):
            (self.root / "catalog" / folder).mkdir(parents=True)
        (self.root / ".github").mkdir()
        (self.root / "templates").mkdir()
        for name, value in (("ROOT", self.root), ("GROUPS_FILE", self.root / ".github" / "catalog-groups.json")):
            mock = patch.object(catalog, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        clock = patch.object(catalog.dt, "date", FixedDate)
        clock.start()
        self.addCleanup(clock.stop)
        network = patch.object(catalog.urllib.request, "urlopen", side_effect=AssertionError("tests must not use the network"))
        self.urlopen = network.start()
        self.addCleanup(network.stop)
        catalog.errors.clear()
        catalog.warnings.clear()
        self.path = self.root / "catalog" / "assess" / "example-tool.md"
        self.path.write_text(ENTRY, encoding="utf-8")
        (self.root / "templates" / "entry-template.md").write_text(ENTRY, encoding="utf-8")
        (self.root / ".github" / "CODEOWNERS").write_text(
            "/catalog/assess/example-tool.md @example-owner\n", encoding="utf-8")
        catalog.GROUPS_FILE.write_text("{}", encoding="utf-8")
        self.indexes = [self.root / "README.md"] + [
            self.root / "catalog" / folder / "README.md" for folder in catalog.CATEGORIES]
        for path in self.indexes:
            path.write_text(f"# Index\n\n{catalog.TABLE_START}\n{catalog.TABLE_END}\n\nKeep this prose.\n", encoding="utf-8")
        fm = catalog.parse_front_matter(ENTRY)[0]
        for path, text in catalog.generated_outputs([(fm, self.path)], {}).items():
            path.write_text(text, encoding="utf-8")

    def entry(self, text=ENTRY):
        self.path.write_text(text, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            return catalog.check_entry(self.path, catalog.codeowners_rules(), {})

    def run_main(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = catalog.main(list(args))
        return code, output.getvalue()

    def messages(self):
        return "\n".join(message for _, message in catalog.errors)

    def test_valid_entry(self):
        self.assertEqual(self.entry()["name"], "Example tool")
        self.assertEqual(catalog.errors, [])
        self.assertEqual(catalog.warnings, [])

    def test_missing_front_matter(self):
        self.assertIsNone(self.entry("# Example tool\n"))
        self.assertIn("missing front matter", self.messages())

    def test_supported_scalars_and_comments(self):
        text = """---
# comment
name: 'Team''s tool' # comment
category: "Assess"
repo_url: https://example.com/path#anchor
maintainer_name: "Team # one"
group: "[TODO: confirm]"
extra: "quote: \\" and slash \\\\"
---
# Body
"""
        fields, body = catalog.parse_front_matter(text.replace("\n", "\r\n"))
        self.assertEqual(fields["name"], "Team's tool")
        self.assertEqual(fields["repo_url"], "https://example.com/path#anchor")
        self.assertEqual(fields["maintainer_name"], "Team # one")
        self.assertEqual(fields["extra"], 'quote: " and slash \\')
        self.assertEqual(body, "# Body")

    def test_plain_placeholder(self):
        self.assertEqual(catalog.parse_front_matter("---\nname: [TODO: confirm]\n---")[0]["name"], "[TODO: confirm]")

    def test_malformed_front_matter(self):
        for lines in (
            "name Example", " name: Example", "name: Example\nname: Other",
            'name: "unterminated', 'name: "Example" garbage', "name: 'Example'junk",
            r'name: "bad\nescape"', "name: [one, two]", "name: {nested: value}",
            "name: |\n  body", "name: >\nbody", "name: &anchor", "name: *anchor",
            "name: !!str Example", "name: a: b",
        ):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                catalog.parse_front_matter(f"---\n{lines}\n---\nBody")
        with self.assertRaises(ValueError):
            catalog.parse_front_matter("---\nname: Example")
        self.assertIsNone(catalog.parse_front_matter("---invalid\nname: Example\n---")[0])

    def test_parse_error_is_reported(self):
        self.assertIsNone(self.entry(ENTRY.replace("name: Example tool", "name Example tool")))
        self.assertIn("line 2", self.messages())

    def test_unknown_and_missing_fields(self):
        self.entry(ENTRY.replace("maturity: Prototype", "extra: value"))
        self.assertIn("missing or empty field: maturity", self.messages())
        self.assertIn("unknown field(s): extra", self.messages())

    def test_invalid_category_maturity_alias_and_url(self):
        self.entry(ENTRY.replace("category: Assess", "category: Build")
                   .replace("maturity: Prototype", "maturity: Guess")
                   .replace("maintainer_alias: example-owner", "maintainer_alias: bad-")
                   .replace("https://example.com/tool", "https://"))
        for expected in ("doesn't match folder", "maturity must", "GitHub handle", "https:// link"):
            self.assertIn(expected, self.messages())

    def test_web_url_validation(self):
        for url in ("https://", "https://user:password@example.com", "https://example.com:bad",
                    "https://example.com:0", "https://example.com/space here", "https://[bad"):
            with self.subTest(url=url):
                self.assertFalse(catalog.valid_web_url(url))
        self.assertTrue(catalog.valid_web_url("https://example.com/tool?q=one#two"))

    def test_exact_title_required(self):
        self.entry(ENTRY.replace("# Example tool", "# Wrong tool"))
        self.assertIn("title doesn't match", self.messages())

    def test_missing_duplicate_extra_and_nested_headings(self):
        for text in (
            ENTRY.replace("# Example tool\n", ""),
            ENTRY + "\n# Another title\n",
            ENTRY.replace("## Limits", "## What it does"),
            ENTRY + "\n## Extra\nFilled\n",
            ENTRY + "\n### Nested\nFilled\n",
            ENTRY + "\n  ### Indented nested\nFilled\n",
            ENTRY + "\n   # Another title\n",
            ENTRY + "\n##\n",
            ENTRY + "\n# \n",
            ENTRY.replace("## Limits", "## limits"),
            ENTRY.replace("## What it does", "## Limits").replace("## Limits\n\n- Does", "## What it does\n\n- Does"),
        ):
            with self.subTest(text=text):
                catalog.errors.clear()
                self.entry(text)
                self.assertTrue(catalog.errors)

    def test_sections_reject_duplicate_headings(self):
        with self.assertRaisesRegex(ValueError, "duplicate heading"):
            catalog.sections("## Limits\nOne\n## Limits\nTwo")

    def test_empty_sections_and_bullets(self):
        for text in (
            ENTRY.replace("Describes a reusable tool.", "<!-- guidance only -->"),
            ENTRY.replace("- **Access:** None", "- **Access:**"),
            ENTRY.replace("- **Scenario:** A team needs a starting point.", "- **Scenario:** **"),
            ENTRY.replace("- Does not monitor workloads.", "-"),
            ENTRY + "\n-\n",
        ):
            with self.subTest(text=text):
                catalog.errors.clear()
                self.entry(text)
                self.assertTrue(catalog.errors)

    def test_duplicate_or_extra_subfield_bullets(self):
        for replacement in ("- **Access:** None\n- **Access:** More", "- **Extra:** None\n- **Access:** None",
                            "- **Access:** None\n- Unlabeled extra bullet"):
            with self.subTest(replacement=replacement):
                catalog.errors.clear()
                self.entry(ENTRY.replace("- **Access:** None", replacement))
                self.assertIn("exactly these bullets", self.messages())

    def test_future_stale_invalid_and_noncanonical_dates(self):
        for date, error, warning in (
            ("2026-11-07", "in the future", ""),
            ("2025-11-05", "", "more than 365"),
            ("2025-11-06", "", ""),
            ("2026-02-30", "YYYY-MM-DD", ""),
            ("20261106", "YYYY-MM-DD", ""),
            ("2026-W45-5", "YYYY-MM-DD", ""),
        ):
            with self.subTest(date=date):
                catalog.errors.clear()
                catalog.warnings.clear()
                self.entry(ENTRY.replace("2026-11-06", date))
                if error:
                    self.assertIn(error, self.messages())
                else:
                    self.assertEqual(catalog.errors, [])
                if warning:
                    self.assertIn(warning, str(catalog.warnings))
                else:
                    self.assertEqual(catalog.warnings, [])

    def test_placeholder_is_warning_and_visible_in_generated_output(self):
        fm = self.entry(ENTRY.replace("Describes a reusable tool.", "[TODO: confirm behavior]"))
        self.assertEqual(catalog.errors, [])
        self.assertTrue(catalog.warnings)
        self.assertIn("**Unconfirmed**", catalog.table_row(fm, self.path))
        fm["repo_url"] = "[TODO: confirm]"
        row = catalog.table_row(fm, self.path)
        self.assertNotIn("]([TODO", row)

    def test_content_guards(self):
        for forbidden in ("```python\nprint('no')\n```", "~~~\ncode\n~~~",
                          "00000000-0000-0000-0000-000000000000", "AccountKey=not-a-real-key",
                          "https://example.sharepoint.com/resource", "Guaranteed outcomes."):
            with self.subTest(forbidden=forbidden):
                catalog.errors.clear()
                self.entry(ENTRY + "\n" + forbidden + "\n")
                self.assertTrue(catalog.errors)

    def test_correct_path_with_wrong_owner_fails(self):
        (self.root / ".github" / "CODEOWNERS").write_text(
            "/catalog/assess/example-tool.md @someone-else\n", encoding="utf-8")
        self.entry()
        self.assertIn("with @example-owner", self.messages())

    def test_owner_case_comments_and_multiple_owners(self):
        (self.root / ".github" / "CODEOWNERS").write_text(
            "# comment\n/catalog/assess/example-tool.md @someone-else @Example-Owner # comment\n", encoding="utf-8")
        self.entry()
        self.assertEqual(catalog.errors, [])

    def test_later_directory_rule_can_override_entry_owner(self):
        (self.root / ".github" / "CODEOWNERS").write_text(
            "/catalog/assess/example-tool.md @example-owner\n/catalog/ @someone-else\n", encoding="utf-8")
        self.entry()
        self.assertIn("overridden", self.messages())

    def test_directory_rule_alone_does_not_replace_exact_entry_rule(self):
        (self.root / ".github" / "CODEOWNERS").write_text("/catalog/ @example-owner\n", encoding="utf-8")
        self.entry()
        self.assertIn("exact rule", self.messages())

    def test_missing_or_unsupported_codeowners_rules(self):
        owners = self.root / ".github" / "CODEOWNERS"
        owners.write_text("/catalog/*.md @example-owner\n/catalog/assess/example-tool.md not-a-handle\n", encoding="utf-8")
        self.entry()
        self.assertIn("not a wildcard", self.messages())
        self.assertIn("GitHub @handle", self.messages())
        catalog.errors.clear()
        owners.unlink()
        self.entry()
        self.assertIn("CODEOWNERS is missing", self.messages())

    def test_groups_validate_json_shape_keys_and_duplicates(self):
        for data in ('[]', '{"AI": null}', '{"AI": {"category": "Build"}}',
                     '{"AI": {"category": "Wrong", "description": "Text"}}',
                     '{"AI": {"category": "Build", "description": []}}',
                     '{"AI": {}, "AI": {}}', '{"AI": {"category": "Build", "category": "Assess"}}',
                     '{bad json'):
            with self.subTest(data=data):
                catalog.errors.clear()
                catalog.GROUPS_FILE.write_text(data, encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()):
                    catalog.load_groups()
                self.assertTrue(catalog.errors)

    def test_entry_group_category_must_match(self):
        self.path.write_text(ENTRY.replace("maturity:", "group: AI Accelerators\nmaturity:"), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            catalog.check_entry(self.path, catalog.codeowners_rules(),
                                {"AI Accelerators": {"category": "Build", "description": "Starting points."}})
        self.assertIn("belongs to Build", self.messages())

    def test_unknown_group_is_error(self):
        self.entry(ENTRY.replace("maturity:", "group: Missing group\nmaturity:"))
        self.assertIn("unknown group", self.messages())

    def test_generated_category_preserves_groups_sort_and_relative_links(self):
        groups = {"AI Accelerators": {"category": "Build", "description": "Starting points."},
                  "Empty": {"category": "Build", "description": "Not shown."}}
        fm = catalog.parse_front_matter(ENTRY)[0]
        first = dict(fm, name="Zulu tool", category="Build", group="AI Accelerators")
        second = dict(first, name="Alpha tool")
        paths = [self.root / "catalog" / "build" / name for name in ("zulu-tool.md", "alpha-tool.md")]
        entries = [(first, paths[0]), (second, paths[1])]
        table = catalog.build_table(entries, groups, "build")
        self.assertIn("## AI Accelerators", table)
        self.assertIn("[Details](alpha-tool.md)", table)
        self.assertLess(table.index("Alpha tool"), table.index("Zulu tool"))
        self.assertNotIn("Empty", table)
        self.assertNotIn("###", table)
        self.assertIn("[Details](catalog/build/alpha-tool.md)", catalog.build_table(entries, groups))

    def test_generated_text_escapes_table_and_link_characters(self):
        fm = catalog.parse_front_matter(ENTRY)[0]
        fm["name"] = "A | [tool]"
        fm["repo_url"] = "https://example.com/tool(v1)"
        table = catalog.table_row(fm, self.path)
        self.assertIn(r"A \| \[tool\]", table)
        self.assertIn("tool%28v1%29", table)

    def test_main_passes_without_network_and_resets_diagnostics(self):
        catalog.errors.append(("old", "old error"))
        code, _ = self.run_main()
        self.assertEqual(code, 0, self.messages())
        self.urlopen.assert_not_called()

    def test_main_rejects_duplicate_entry_names(self):
        duplicate = self.path.with_name("duplicate-tool.md")
        duplicate.write_text(ENTRY, encoding="utf-8")
        owners = self.root / ".github" / "CODEOWNERS"
        owners.write_text(owners.read_text(encoding="utf-8") +
                          "/catalog/assess/duplicate-tool.md @example-owner\n", encoding="utf-8")
        code, _ = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("duplicate entry name", self.messages())

    def test_write_updates_all_indexes_and_keeps_prose(self):
        self.path.write_text(ENTRY.replace("Prototype", "Field-tested"), encoding="utf-8")
        code, _ = self.run_main()
        self.assertEqual(code, 1)
        code, _ = self.run_main("--write")
        self.assertEqual(code, 0, self.messages())
        for path in self.indexes:
            self.assertIn("Keep this prose.", path.read_text(encoding="utf-8"))
        self.assertIn("Field-tested", self.indexes[0].read_text(encoding="utf-8"))
        self.assertIn("[Details](example-tool.md)", self.indexes[1].read_text(encoding="utf-8"))
        self.assertIn("No entries yet.", self.indexes[2].read_text(encoding="utf-8"))
        before = {path: path.read_bytes() for path in self.indexes}
        self.assertEqual(self.run_main("--write")[0], 0)
        self.assertEqual(before, {path: path.read_bytes() for path in self.indexes})
        self.assertEqual(self.run_main()[0], 0)

    def test_write_does_not_change_any_index_after_invalid_entry(self):
        before = {path: path.read_bytes() for path in self.indexes}
        self.path.write_text(ENTRY.replace("Prototype", "Invalid"), encoding="utf-8")
        code, output = self.run_main("--write")
        self.assertEqual(code, 1)
        self.assertIn("No generated indexes written", output)
        self.assertEqual(before, {path: path.read_bytes() for path in self.indexes})

    def test_write_is_failure_safe_for_invalid_markers_and_links(self):
        for problem in ("marker", "link"):
            with self.subTest(problem=problem):
                root = self.indexes[0]
                original = root.read_text(encoding="utf-8")
                if problem == "marker":
                    root.write_text(original + catalog.TABLE_START, encoding="utf-8")
                else:
                    root.write_text(original + "\n[Broken](missing.md)\n", encoding="utf-8")
                before = {path: path.read_bytes() for path in self.indexes}
                self.path.write_text(ENTRY.replace("Prototype", "Field-tested"), encoding="utf-8")
                self.assertEqual(self.run_main("--write")[0], 1)
                self.assertEqual(before, {path: path.read_bytes() for path in self.indexes})
                root.write_text(original, encoding="utf-8")

    def test_write_validates_prospective_generated_anchors(self):
        groups = {"AI Accelerators": {"category": "Build", "description": "Starting points."}}
        catalog.GROUPS_FILE.write_text(json.dumps(groups), encoding="utf-8")
        build = self.root / "catalog" / "build" / "build-tool.md"
        build.write_text(ENTRY.replace("category: Assess", "category: Build\ngroup: AI Accelerators"), encoding="utf-8")
        self.path.unlink()
        (self.root / ".github" / "CODEOWNERS").write_text("/catalog/build/build-tool.md @example-owner\n", encoding="utf-8")
        readme = self.indexes[0]
        readme.write_text(readme.read_text(encoding="utf-8") +
                          "\n[Group](catalog/build/README.md#ai-accelerators)\n", encoding="utf-8")
        self.assertEqual(self.run_main("--write")[0], 0, self.messages())

    def test_markdown_anchors_match_emoji_unicode_formatting_and_collisions(self):
        text = """# 🗂️ How to browse
## 🛠️ Build
## 📈 Operate
## Café & **costs**: `foo_bar`!
## *Same*
## Same
## Same-1
## Same
## [Linked title](https://example.com)
## _Emphasized_
## <span>HTML &amp; text</span>
Setext title
============
<!-- ## Not a heading -->
```markdown
## Example only
```
<a id="custom"></a>
"""
        self.assertEqual(catalog.markdown_anchors(text), {
            "-how-to-browse", "-build", "-operate", "café--costs-foo_bar",
            "same", "same-1", "same-1-1", "same-2", "linked-title", "emphasized",
            "html--text", "setext-title", "custom",
        })

    def test_heading_code_and_escaped_underscores_are_literal(self):
        self.assertEqual(catalog.heading_slug(r"`_code_` and \_literal\_"), "_code_-and-_literal_")
        self.assertEqual(catalog.heading_slug("`&amp;`"), "amp")

    def test_horizontal_rule_after_heading_does_not_add_a_duplicate_anchor(self):
        self.assertEqual(catalog.markdown_anchors("# Title\n---\n"), {"title"})

    def test_relative_links_check_fragments_encoded_paths_and_root_paths(self):
        target = self.root / "Space file.md"
        target.write_text("# 🛠️ Build\n## Café\n## Café\n", encoding="utf-8")
        readme = self.indexes[0]
        readme.write_text(readme.read_text(encoding="utf-8") + """
[Encoded](Space%20file.md#caf%C3%A9-1)
[Root](/Space%20file.md#-build)
[Self](#index)
[Query](Space%20file.md?plain=1#caf%C3%A9)
""", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            catalog.check_relative_links()
        self.assertEqual(catalog.errors, [])

    def test_missing_file_anchor_escape_and_scheme_are_errors(self):
        readme = self.indexes[0]
        readme.write_text(readme.read_text(encoding="utf-8") + """
[Missing](missing.md)
[Anchor](#absent)
[Escapes](../outside.md)
[Encoded escape](%2e%2e/outside.md)
[Unsupported](javascript:alert)
""", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            catalog.check_relative_links()
        for expected in ("broken relative link", "broken Markdown anchor", "escapes repository", "unsupported link scheme"):
            self.assertIn(expected, self.messages())

    def test_links_cover_security_template_and_github_markdown(self):
        (self.root / "SECURITY.md").write_text("[Bad](missing-security.md)", encoding="utf-8")
        (self.root / ".github" / "pull_request_template.md").write_text("[Bad](missing-pr.md)", encoding="utf-8")
        template = self.root / "templates" / "entry-template.md"
        template.write_text(template.read_text(encoding="utf-8") + "\n[Bad](missing-template.md)\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            catalog.check_relative_links()
        self.assertEqual({path for path, _ in catalog.errors},
                         {"SECURITY.md", ".github/pull_request_template.md", "templates/entry-template.md"})

    def test_malformed_doc_front_matter_is_not_silently_ignored(self):
        (self.root / "SECURITY.md").write_text("---\nname broken\n---\n# Security\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            catalog.check_relative_links()
        self.assertIn("expected an unindented key", self.messages())

    def test_placeholder_template_url_is_not_requested(self):
        template = self.root / "templates" / "entry-template.md"
        template.write_text(ENTRY.replace("https://example.com/tool", '"[TODO: confirm]"'), encoding="utf-8")
        self.assertNotIn((template, "[TODO: confirm]"), set(catalog.collect_links()))

    def test_comments_code_and_reference_links(self):
        readme = self.indexes[0]
        readme.write_text("""# Index
[Inline](README.md "a title")
[Balanced](<README.md> 'a title')
[Reference][target]
[target]
[target]: README.md#Index
<!-- [Ignored](missing.md) -->
`[Ignored](missing.md)`
~~~markdown
[Ignored](missing.md)
~~~
    [Ignored](missing.md)
""".replace("#Index", "#index"), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            catalog.check_relative_links()
        self.assertEqual(catalog.errors, [])

    def test_link_destinations_with_parentheses_images_and_autolinks(self):
        targets = set(catalog.markdown_links(r"""
[**Label**](file(one).md)
[Escaped](file\(one\).md "title")
![Image](image.png)
[Space](<space file.md>)
<https://example.com/angle>
https://example.com/bare.
[External](https://example.com/tool\(one\))
"""))
        self.assertEqual(targets, {"file(one).md", "image.png", "space file.md",
                                   "https://example.com/angle", "https://example.com/bare",
                                   "https://example.com/tool(one)"})

    def test_stray_files_and_nested_entries_fail(self):
        (self.root / "catalog" / "build" / "code.py").write_text("print('no')", encoding="utf-8")
        nested = self.root / "catalog" / "assess" / "nested" / "assess"
        nested.mkdir(parents=True)
        (nested / "entry.md").write_text(ENTRY, encoding="utf-8")
        code, _ = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("only Markdown files", self.messages())
        self.assertIn("entries must live", self.messages())

    def test_template_malformed_front_matter_and_heading_are_reported(self):
        template = self.root / "templates" / "entry-template.md"
        for text in (ENTRY.replace("name: Example tool", "name: Example tool\nname: Other"),
                     ENTRY.replace("## Limits", "## Extra")):
            with self.subTest(text=text):
                catalog.errors.clear()
                template.write_text(text, encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()):
                    catalog.check_template()
                self.assertTrue(catalog.errors)

    def test_external_success_deduplicates_and_uses_timeout(self):
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        self.urlopen.side_effect = None
        self.urlopen.return_value = response
        with contextlib.redirect_stdout(io.StringIO()):
            catalog.check_external_links()
        self.assertEqual(catalog.errors, [])
        self.assertEqual(catalog.warnings, [])
        self.assertEqual(self.urlopen.call_count, 1)
        self.assertEqual(self.urlopen.call_args.kwargs["timeout"], 10)

    def test_external_broken_links_are_errors_unreachable_sites_are_warnings(self):
        for failure, is_error, attempts in (
            (urllib.error.HTTPError("https://example.com/tool", 404, "Not found", {}, io.BytesIO()), True, 1),
            (urllib.error.HTTPError("https://example.com/tool", 410, "Gone", {}, io.BytesIO()), True, 1),
            (urllib.error.HTTPError("https://example.com/tool", 403, "Forbidden", {}, io.BytesIO()), False, 1),
            (urllib.error.HTTPError("https://example.com/tool", 503, "Unavailable", {}, io.BytesIO()), False, 2),
            (urllib.error.URLError("DNS unavailable"), False, 2),
            (TimeoutError("timed out"), False, 2),
        ):
            with self.subTest(failure=failure):
                catalog.errors.clear()
                catalog.warnings.clear()
                self.urlopen.reset_mock()
                self.urlopen.side_effect = failure
                with patch.object(catalog.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
                    catalog.check_external_links()
                self.assertEqual(bool(catalog.errors), is_error)
                self.assertEqual(bool(catalog.warnings), not is_error)
                self.assertEqual(self.urlopen.call_count, attempts)
                self.assertIn("referenced in", str(catalog.errors or catalog.warnings))

    def test_external_programming_errors_are_not_swallowed(self):
        self.urlopen.side_effect = RuntimeError("unexpected bug")
        with self.assertRaisesRegex(RuntimeError, "unexpected bug"):
            catalog.check_external_links()

    def test_write_is_failure_safe_when_external_links_fail(self):
        before = {path: path.read_bytes() for path in self.indexes}
        self.path.write_text(ENTRY.replace("Prototype", "Field-tested"), encoding="utf-8")
        self.urlopen.side_effect = urllib.error.HTTPError("https://example.com/tool", 404, "Not found", {}, io.BytesIO())
        self.assertEqual(self.run_main("--write", "--links")[0], 1)
        self.assertEqual(before, {path: path.read_bytes() for path in self.indexes})


if __name__ == "__main__":
    unittest.main()
