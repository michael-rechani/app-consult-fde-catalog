#!/usr/bin/env python3
"""Check the catalog.

Run from anywhere:  python .github/scripts/validate_catalog.py [--links] [--write]

Checks:
  * every entry has all required fields and headings
  * no code blocks, GUIDs, secrets or internal-only hostnames in the content
  * relative links and Markdown heading anchors resolve (external URLs with --links)
  * the README and category indexes match the entries (--write regenerates them)

Standard library only.
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import ssl
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATEGORIES = {"assess": "Assess", "build": "Build", "operate": "Operate"}
MATURITY = ["Prototype", "Field-tested", "Production-ready"]
CATEGORY_ICONS = {"Assess": "🔍", "Build": "🛠️", "Operate": "📈"}
KEYS = ["name", "category", "maturity", "maintainer_name", "maintainer_alias", "repo_url", "last_reviewed"]
OPTIONAL_KEYS = ["group"]
GROUPS_FILE = ROOT / ".github" / "catalog-groups.json"
HEADINGS = ["What it does", "When to use it", "Prerequisites", "Limits"]
SUBFIELDS = {
    "When to use it": ["Scenario", "What you get"],
    "Prerequisites": ["Access", "Tooling", "Azure services"],
}
PLACEHOLDER = re.compile(r"\[TODO[^\]]*\]", re.I)
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\.md$")
ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$")
TABLE_START, TABLE_END = "<!-- catalog-table:start -->", "<!-- catalog-table:end -->"
STALE_DAYS = 365

FORBIDDEN = [
    ("code block (links only, no code)", re.compile(r"^\s*(```|~~~)", re.M)),
    ("GUID (possible tenant or subscription ID)", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)),
    ("possible secret", re.compile(
        r"(AccountKey=|SharedAccessSignature|sig=[A-Za-z0-9%+/]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
        r"\b(ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{20,}|\bAKIA[0-9A-Z]{16}\b|"
        r"(password|secret|api[_-]?key|token)\s*[:=]\s*['\"]?[A-Za-z0-9/+_\-]{12,})", re.I)),
    ("internal-only host", re.compile(
        r"https?://[^\s)>\"]*(\.corp\.microsoft\.com|\.sharepoint\.com|eng\.ms|\.visualstudio\.com|"
        r"\.azurewebsites\.net/internal|microsoft\.sharepoint)", re.I)),
]

PROMISES = re.compile(
    r"\b(guarantee[sd]?|SLAs?|service[- ]levels?|fully supported|officially supported|supported by|we support|"
    r"enterprise[- ]grade|production[- ]ready|ready for production|safe for production|"
    r"recommended for production|battle[- ]tested)\b", re.I)

errors, warnings = [], []
def rel(p):
    return Path(p).resolve().relative_to(ROOT).as_posix()


def report(kind, path, msg):
    bucket = errors if kind == "error" else warnings
    bucket.append((path, msg))
    if os.environ.get("GITHUB_ACTIONS"):
        def escape(value):
            return str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::{kind} file={escape(path).replace(',', '%2C').replace(':', '%3A')}::{escape(msg)}")
    else:
        print(f"{kind.upper():7} {path}: {msg}")


def parse_front_matter(text):
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None, text
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ValueError("front matter needs a closing --- on its own line") from None
    data = {}
    for number, line in enumerate(lines[1:end], 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([a-z][a-z0-9_]*):[ \t]*(.*)", line)
        if not match:
            raise ValueError(f"front matter line {number}: expected an unindented key: value")
        key, value = match.groups()
        if key in data:
            raise ValueError(f"front matter line {number}: duplicate key '{key}'")
        if value.startswith(("'", '"')):
            quoted = re.fullmatch(r"""('(?:[^']|'')*'|"(?:[^"\\]|\\["\\])*")(?:[ \t]+#.*)?[ \t]*""", value)
            if not quoted:
                raise ValueError(f"front matter line {number}: malformed quoted scalar")
            scalar = quoted.group(1)
            value = scalar[1:-1]
            value = value.replace("''", "'") if scalar[0] == "'" else re.sub(r'\\(["\\])', r"\1", value)
        else:
            value = re.sub(r"\s+#.*$", "", value).strip()
            if value and not PLACEHOLDER.fullmatch(value):
                if value[0] in "[]{}>|&*!%@`" or ": " in value or value.startswith("- "):
                    raise ValueError(f"front matter line {number}: only single-line string scalars are supported")
        data[key] = value.strip()
    return data, "\n".join(lines[end + 1:])


def sections(body):
    out, current = {}, None
    for line in body.splitlines():
        m = re.match(r"^ {0,3}##[ \t]+(.*?)[ \t]*$", line)
        if m:
            current = m.group(1)
            if current in out:
                raise ValueError(f"duplicate heading: ## {current}")
            out[current] = []
        elif current:
            out[current].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def strip_comments(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def is_placeholder(v):
    return bool(PLACEHOLDER.search(v))


def codeowners_rules():
    f = ROOT / ".github" / "CODEOWNERS"
    if not f.exists():
        report("error", rel(f), "CODEOWNERS is missing")
        return []
    rules = []
    for number, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        fields = line.partition("#")[0].split()
        if not fields:
            continue
        pattern, *owners = fields
        if not pattern.startswith("/") or re.search(r"[*?!\[\]\\]", pattern):
            report("error", rel(f), f"line {number}: use a rooted exact file or directory path, not a wildcard")
            continue
        if any(not re.fullmatch(r"@[A-Za-z0-9][A-Za-z0-9-]{0,38}(?:/[A-Za-z0-9_-]+)?", owner) for owner in owners):
            report("error", rel(f), f"line {number}: owner must be a GitHub @handle or @org/team")
        rules.append((pattern, owners))
    return rules


def check_owner(path, alias, rules):
    target = "/" + rel(path)
    exact = any(pattern == target for pattern, _ in rules)
    effective = []
    for pattern, owners in rules:
        if target == pattern or (pattern.endswith("/") and target.startswith(pattern)):
            effective = owners
    if not exact or f"@{alias}".lower() not in {owner.lower() for owner in effective}:
        report("error", rel(path), f"CODEOWNERS needs an exact rule for {target} with @{alias}, not overridden by a later rule")


def load_groups():
    if not GROUPS_FILE.exists():
        return {}
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        data = json.loads(GROUPS_FILE.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except ValueError as e:
        report("error", rel(GROUPS_FILE), f"not valid JSON: {e}")
        return {}
    if not isinstance(data, dict):
        report("error", rel(GROUPS_FILE), "groups must be a JSON object")
        return {}
    valid = {}
    for name, g in data.items():
        if not name.strip() or name != name.strip() or "\n" in name or not isinstance(g, dict):
            report("error", rel(GROUPS_FILE), f"invalid group: {name!r}")
            continue
        if set(g) != {"category", "description"}:
            report("error", rel(GROUPS_FILE), f"group '{name}' needs only category and description")
        if g.get("category") not in CATEGORIES.values():
            report("error", rel(GROUPS_FILE), f"group '{name}' needs a category of: {', '.join(CATEGORIES.values())}")
        if not isinstance(g.get("description"), str) or not g["description"].strip() or "\n" in g["description"]:
            report("error", rel(GROUPS_FILE), f"group '{name}' needs a one-line description")
        valid[name] = g
    return valid


def check_sections(body, path, template=False):
    body = strip_comments(body)
    headings = [(level, title or "") for level, title in
                re.findall(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$", body, re.M)]
    titles = [title for level, title in headings if level == "#"]
    if len(titles) != 1 or not headings or headings[0][0] != "#":
        report("error", path, "needs exactly one '# <name>' title before the sections")
    actual = [title for level, title in headings if level != "#"]
    if actual != HEADINGS or any(level != "##" for level, _ in headings[1:]):
        report("error", path, "use exactly these ## headings, in order: " + ", ".join(HEADINGS))
    try:
        secs = sections(body)
    except ValueError as e:
        report("error", path, str(e))
        return titles, {}
    if template:
        return titles, secs
    for heading in HEADINGS:
        content = secs.get(heading, "")
        if not re.sub(r"[\s*_\-`]+", "", content):
            report("error", path, f"section is empty: {heading}")
        if re.search(r"^\s*[-*+]\s*(?:\*\*[^*]+:\*\*)?\s*$", content, re.M):
            report("error", path, f"section has an empty bullet: {heading}")
    for heading, required in SUBFIELDS.items():
        content = secs.get(heading, "")
        labels = re.findall(r"^\s*[-*]\s+\*\*([^*]+):\*\*", content, re.M)
        bullets = re.findall(r"^[ \t]*[-*+][ \t]+", content, re.M)
        if labels != required or len(bullets) != len(required):
            report("error", path, f"'{heading}' needs exactly these bullets, in order: " + ", ".join(required))
        for label in required:
            match = re.search(rf"^[ \t]*[-*][ \t]+\*\*{re.escape(label)}:\*\*[ \t]*([^\n]+)", content, re.M)
            if not match or not re.sub(r"[\s*_\-`]+", "", match.group(1)):
                report("error", path, f"'{heading}' needs a filled-in '**{label}:**' bullet")
    if not re.search(r"^\s*[-*]\s+\S", secs.get("Limits", ""), re.M):
        report("error", path, "'Limits' needs at least one filled-in bullet")
    return titles, secs


def valid_web_url(url):
    try:
        parts = urllib.parse.urlsplit(url)
        return (parts.scheme in {"http", "https"} and bool(parts.hostname)
                and parts.username is None and parts.password is None
                and not re.search(r'[\s<>"\\]', url) and parts.port != 0)
    except ValueError:
        return False


def check_entry(path, owners, groups):
    r = rel(path)
    text = path.read_text(encoding="utf-8")
    try:
        fm, body = parse_front_matter(text)
    except ValueError as e:
        report("error", r, str(e))
        return None
    if fm is None:
        report("error", r, "missing front matter block (--- ... ---) at top of file")
        return None
    if not SLUG.fullmatch(path.name):
        report("error", r, "file name must be lowercase kebab-case, for example my-resource.md")
    for k in KEYS:
        if not fm.get(k):
            report("error", r, f"missing or empty field: {k}")
    if any(k not in KEYS + OPTIONAL_KEYS for k in fm):
        report("error", r, "unknown field(s): " + ", ".join(k for k in fm if k not in KEYS + OPTIONAL_KEYS))

    group = fm.get("group", "")
    if group and not is_placeholder(group):
        if group not in groups:
            report("error", r, f"unknown group '{group}'. Add it to .github/catalog-groups.json or use one of: {', '.join(groups) or 'none defined'}")
        elif fm.get("category") and groups[group].get("category") != fm["category"]:
            report("error", r, f"group '{group}' belongs to {groups[group].get('category')}, but this entry's category is {fm['category']}")

    folder = path.parent.name
    if fm.get("category") and fm["category"] != CATEGORIES.get(folder):
        report("error", r, f"category '{fm['category']}' doesn't match folder '{folder}' (expected {CATEGORIES.get(folder)})")

    mat = fm.get("maturity", "")
    if mat and not is_placeholder(mat) and mat not in MATURITY:
        report("error", r, f"maturity must be one of: {', '.join(MATURITY)}")

    alias = fm.get("maintainer_alias", "")
    if alias and not is_placeholder(alias):
        if not ALIAS.fullmatch(alias) or alias.endswith("-") or "--" in alias:
            report("error", r, "maintainer_alias must be a GitHub handle without the @")
        else:
            check_owner(path, alias, owners)

    url = fm.get("repo_url", "")
    if url and not is_placeholder(url) and (not url.startswith("https://") or not valid_web_url(url)):
        report("error", r, "repo_url must be an https:// link")

    lr = fm.get("last_reviewed", "")
    if lr and not is_placeholder(lr):
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", lr):
                raise ValueError("not YYYY-MM-DD")
            d = dt.date.fromisoformat(lr)
            if d > dt.date.today():
                report("error", r, "last_reviewed is in the future")
            elif (dt.date.today() - d).days > STALE_DAYS:
                report("warning", r, f"last_reviewed is more than {STALE_DAYS} days ago")
        except ValueError:
            report("error", r, "last_reviewed must be a date in YYYY-MM-DD format")

    titles, secs = check_sections(body, r)
    if titles and fm.get("name") and titles[0] != fm["name"]:
        report("error", r, "title doesn't match the name field")
    what = secs.get("What it does", "")
    if what and not is_placeholder(what):
        if len(re.findall(r"[.!?](\s|$)", what.strip())) > 2:
            report("warning", r, "'What it does' should be one or two sentences")

    for label, rx in FORBIDDEN:
        if rx.search(text):
            report("error", r, f"found {label}")

    for m in PROMISES.finditer(body):
        report("error", r, f"wording implies support or a guarantee: \"{m.group(0)}\"")

    todos = len(PLACEHOLDER.findall(text))
    if todos:
        report("warning", r, f"{todos} placeholder(s) to confirm")
    fm["_unconfirmed"] = bool(todos)
    return fm


def check_template():
    p = ROOT / "templates" / "entry-template.md"
    r = rel(p)
    if not p.exists():
        report("error", r, "template is missing")
        return
    text = p.read_text(encoding="utf-8")
    try:
        fm, body = parse_front_matter(text)
    except ValueError as e:
        report("error", r, str(e))
        return
    if fm is None or any(k not in fm for k in KEYS):
        report("error", r, "template front matter must include every required field")
    elif set(fm) - set(KEYS + OPTIONAL_KEYS):
        report("error", r, "template has unknown front matter fields")
    titles, _ = check_sections(body, r, template=True)
    if fm and titles and titles[0] != fm.get("name"):
        report("error", r, "template title doesn't match the name field")


def escape_text(value):
    return re.sub(r"([\\`*_\[\]<>|])", r"\\\1", value)


def table_row(fm, path, base=None):
    base = ROOT if base is None else base
    page = urllib.parse.quote(Path(os.path.relpath(path, base)).as_posix(), safe="/")
    url = fm["repo_url"]
    name = escape_text(fm["name"])
    if not is_placeholder(url):
        name = f"[{name}]({urllib.parse.quote(url, safe=':/?#@!$&*+,;=-._~%')})"
    link = f"[Catalog entry]({page})"
    alias = fm["maintainer_alias"]
    who = escape_text(fm["maintainer_name"])
    if not is_placeholder(alias):
        who += f" (@{alias})"
    maturity = escape_text(fm["maturity"])
    if fm.get("_unconfirmed") or any(is_placeholder(str(value)) for value in fm.values()):
        maturity = f"**Unconfirmed** - {maturity}"
    return f"| {name} | {maturity} | {who} | {link} |"


def entry_table(rows, base=None):
    head = ["| Resource repository | Maturity | Maintainer | Catalog entry |", "|---|---|---|---|"]
    rows = sorted(rows, key=lambda e: e[0]["name"].lower())
    return "\n".join(head + [table_row(fm, p, base) for fm, p in rows])


def entry_group(fm, groups):
    g = fm.get("group", "")
    return g if g in groups else ""


def build_table(entries, groups, category=None):
    """Category sections, each with its ungrouped entries first, then one subsection per group."""
    out = []
    base = ROOT / "catalog" / category if category else ROOT
    for cat in CATEGORIES.values():
        if category and cat != CATEGORIES[category]:
            continue
        in_cat = [e for e in entries if e[0]["category"] == cat]
        if not in_cat:
            continue
        if not category:
            out.append(f"### {CATEGORY_ICONS[cat]} {cat}\n")
        loose = [e for e in in_cat if not entry_group(e[0], groups)]
        if loose:
            out.append(entry_table(loose, base) + "\n")
        for name in sorted(groups, key=str.lower):
            members = [e for e in in_cat if entry_group(e[0], groups) == name]
            if members:
                level = "##" if category else "####"
                out.append(f"{level} {escape_text(name)}\n\n{escape_text(groups[name]['description'])}\n\n{entry_table(members, base)}\n")
    if category and not out:
        return "No entries yet."
    return "\n".join(out).rstrip("\n")


def generated_outputs(entries, groups):
    outputs = {}
    for category in (None, *CATEGORIES):
        p = ROOT / "catalog" / category / "README.md" if category else ROOT / "README.md"
        if not p.exists():
            report("error", rel(p), "generated index page is missing")
            continue
        text = p.read_text(encoding="utf-8")
        if text.count(TABLE_START) != 1 or text.count(TABLE_END) != 1 or text.index(TABLE_START) > text.index(TABLE_END):
            report("error", rel(p), f"needs exactly one ordered pair of {TABLE_START} and {TABLE_END}")
            continue
        pre, rest = text.split(TABLE_START)
        _, post = rest.split(TABLE_END)
        expected = "\n" + build_table(entries, groups, category) + "\n"
        outputs[p] = pre + TABLE_START + expected + TABLE_END + post
    return outputs


def markdown_body(text):
    _, body = parse_front_matter(text)
    body = strip_comments(body)
    out, fence = [], None
    for line in body.splitlines():
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence) and not match.group(2).strip():
                fence = None
            out.append("")
        elif match:
            fence = match.group(1)
            out.append("")
        elif line.startswith(("    ", "\t")):
            out.append("")
        else:
            out.append(line)
    return "\n".join(out)


def heading_slug(title):
    def inline_text(text):
        text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
        text = re.sub(r"!?\[([^\]]*)\]\[[^\]]*\]", r"\1", text)
        text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
        text = re.sub(r"<[^>]*>", "", text)
        text = re.sub(r"(?<![\w\\])(_+)(.+?)(?<!\\)\1(?!\w)", r"\2", text)
        return html.unescape(text)

    out, start = [], 0
    for match in re.finditer(r"(`+)(.*?)\1", title):
        out.extend((inline_text(title[start:match.start()]), match.group(2)))
        start = match.end()
    out.append(inline_text(title[start:]))
    title = "".join(out).lower()
    # Emoji and their invisible variation selectors disappear; their following
    # space still becomes a hyphen, as in GitHub's "#-how-to-browse" anchors.
    title = "".join(char for char in title
                    if char in " -_" or (unicodedata.category(char)[0] in "LNM"
                                         and not "\ufe00" <= char <= "\ufe0f"))
    return title.replace(" ", "-")


def markdown_anchors(text):
    body = markdown_body(text)
    anchors, counts = set(), {}
    lines = body.splitlines()
    for number, line in enumerate(lines):
        match = re.match(r"^ {0,3}#{1,6}(?:[ \t]+(.*)|[ \t]*)$", line)
        if match:
            title = re.sub(r"[ \t]+#+[ \t]*$", "", match.group(1) or "").strip()
        elif (number and re.fullmatch(r" {0,3}(?:=+|-+)[ \t]*", line)
              and lines[number - 1].strip()
              and not re.match(r"^ {0,3}(?:#{1,6}(?:[ \t]|$)|[-*+][ \t]|>)", lines[number - 1])):
            title = lines[number - 1].strip()
        else:
            continue
        base = heading_slug(title)
        slug = base
        while slug in anchors:
            counts[base] = counts.get(base, 0) + 1
            slug = f"{base}-{counts[base]}"
        anchors.add(slug)
    for match in re.finditer(r"""<(?:a|[a-z][a-z0-9]*)\b[^>]*?\b(?:id|name)=["']([^"']+)["']""", body, re.I):
        anchors.add(html.unescape(match.group(1)))
    return anchors


def markdown_links(body):
    body = re.sub(r"(`+).*?\1", "", body, flags=re.S)
    references = {}
    consumed = []
    for match in re.finditer(r"^ {0,3}\[([^\]]+)\]:[ \t]*(?:<([^>]+)>|(\S+))", body, re.M):
        references.setdefault(" ".join(match.group(1).lower().split()), match.group(2) or match.group(3))
        consumed.append(match.span())
    yield from references.values()
    for match in re.finditer(r"\]\(", body):
        start = match.end()
        depth, escaped, quote = 1, False, None
        for end in range(start, len(body)):
            char = body[end]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif quote:
                if char == quote:
                    quote = None
            elif char in "\"'" and end > start and body[end - 1].isspace():
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if not depth:
                    consumed.append((match.start(), end + 1))
                    inner = body[start:end].strip()
                    target = re.match(r"<([^>]*)>|((?:\\.|[^\s])+)", inner)
                    if target:
                        yield re.sub(r"\\([\\()])", r"\1", target.group(1) if target.group(1) is not None else target.group(2))
                    elif not inner:
                        yield ""
                    break
    for match in re.finditer(r"!?\[([^\]\n]+)\](?:\[([^\]\n]*)\])?", body):
        key = " ".join((match.group(2) or match.group(1)).lower().split())
        if key in references and body[match.end():match.end() + 1] not in {"(", ":"}:
            yield references[key]
    raw = list(body)
    for start, end in consumed:
        raw[start:end] = " " * (end - start)
    for match in re.finditer(r"""https?://[^\s<>"\[\]]+""", "".join(raw)):
        target = match.group().rstrip(".,;!")
        while target.endswith(")") and target.count(")") > target.count("("):
            target = target[:-1]
        yield target


def md_files():
    files = list(ROOT.glob("*.md"))
    for folder in ("catalog", "templates", ".github"):
        files += list((ROOT / folder).rglob("*.md"))
    return sorted(set(files))


def collect_links(overrides=None):
    overrides = overrides or {}
    for f in md_files():
        text = overrides[f] if f in overrides else f.read_text(encoding="utf-8")
        try:
            fm, _ = parse_front_matter(text)
        except ValueError as e:
            report("error", rel(f), str(e))
            continue
        if fm and fm.get("repo_url", "").startswith("http"):
            yield f, fm["repo_url"]
        for target in sorted(set(markdown_links(markdown_body(text)))):
            yield f, html.unescape(target)


def check_relative_links(overrides=None):
    overrides = overrides or {}
    anchor_cache = {}
    for f, target in collect_links(overrides):
        if is_placeholder(target):
            continue
        try:
            parts = urllib.parse.urlsplit(target)
        except ValueError:
            report("error", rel(f), f"malformed link: {target}")
            continue
        if parts.scheme in {"http", "https"}:
            if not valid_web_url(target):
                report("error", rel(f), f"malformed web link: {target}")
            continue
        if parts.scheme == "mailto":
            continue
        if parts.scheme or parts.netloc:
            report("error", rel(f), f"unsupported link scheme: {target}")
            continue
        decoded = urllib.parse.unquote(parts.path)
        dest = (ROOT / decoded.lstrip("/") if decoded.startswith("/") else f.parent / decoded).resolve() if decoded else f
        if not dest.is_relative_to(ROOT.resolve()):
            report("error", rel(f), f"relative link escapes repository: {target}")
        elif not dest.exists():
            report("error", rel(f), f"broken relative link: {target}")
        elif parts.fragment and dest.suffix.lower() == ".md":
            if dest not in anchor_cache:
                text = overrides[dest] if dest in overrides else dest.read_text(encoding="utf-8")
                try:
                    anchor_cache[dest] = markdown_anchors(text)
                except ValueError as e:
                    report("error", rel(dest), str(e))
                    anchor_cache[dest] = set()
            if urllib.parse.unquote(parts.fragment) not in anchor_cache[dest]:
                report("error", rel(f), f"broken Markdown anchor: {target}")


def check_external_links(overrides=None):
    seen = {}
    for f, url in collect_links(overrides):
        if not url.startswith(("http://", "https://")) or is_placeholder(url) or not valid_web_url(url):
            continue
        url = url.split("#", 1)[0]
        seen.setdefault(url, set()).add(rel(f))
    for url, locations in sorted(seen.items()):
        where = sorted(locations)[0]
        references = ", ".join(sorted(locations))
        status = None
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "catalog-link-check"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    status = resp.status
                break
            except urllib.error.HTTPError as e:
                status = e.code
                e.close()
                if e.code < 500 and e.code != 429:
                    break
            except (urllib.error.URLError, TimeoutError, ConnectionError, ssl.SSLError) as e:
                status = str(e)
            if attempt == 0:
                time.sleep(1)
        if status == 200 or (isinstance(status, int) and 200 <= status < 400):
            continue
        if status in (404, 410):
            report("error", where, f"broken external link ({status}): {url} [referenced in {references}]")
        else:
            report("warning", where, f"external link not confirmed ({status}): {url} [referenced in {references}]")


def check_stray_files():
    for f in (ROOT / "catalog").rglob("*"):
        if f.is_file() and f.suffix != ".md":
            report("error", rel(f), "only Markdown files belong in /catalog (links only, no code)")
        if f.is_file() and f.suffix == ".md" and f.parent not in {ROOT / "catalog" / folder for folder in CATEGORIES}:
            report("error", rel(f), "entries must live in /catalog/assess, /catalog/build or /catalog/operate")


def main(argv=None):
    errors.clear()
    warnings.clear()
    ap = argparse.ArgumentParser()
    ap.add_argument("--links", action="store_true", help="also check external links over the network")
    ap.add_argument("--write", action="store_true", help="regenerate README and category indexes only after validation succeeds")
    args = ap.parse_args(argv)

    owners = codeowners_rules()
    groups = load_groups()
    entries = []
    for folder in CATEGORIES:
        d = ROOT / "catalog" / folder
        if not d.is_dir():
            report("error", f"catalog/{folder}", "category folder is missing")
            continue
        for f in sorted(d.glob("*.md")):
            if f.name == "README.md":
                continue
            fm = check_entry(f, owners, groups)
            if fm and all(fm.get(k) for k in KEYS):
                entries.append((fm, f))
    names = [e[0]["name"].lower() for e in entries]
    for n in {n for n in names if names.count(n) > 1}:
        report("error", "catalog", f"duplicate entry name: {n}")

    check_template()
    check_stray_files()
    outputs = generated_outputs(entries, groups) if not errors else {}
    if not args.write:
        for path, expected in outputs.items():
            if path.read_text(encoding="utf-8") != expected:
                report("error", rel(path), "generated index is out of date. Run: python .github/scripts/validate_catalog.py --write")
    prospective = outputs if args.write else None
    check_relative_links(prospective)
    if args.links:
        check_external_links(prospective)
    if args.write:
        if errors:
            print("No generated indexes written: fix the errors first.")
        else:
            for path, expected in outputs.items():
                if path.read_text(encoding="utf-8") != expected:
                    path.write_text(expected, encoding="utf-8", newline="\n")
                    print(f"updated generated index in {rel(path)}")

    print(f"\n{len(entries)} entries, {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
