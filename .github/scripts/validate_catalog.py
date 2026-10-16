#!/usr/bin/env python3
"""Check the catalog.

Run from anywhere:  python .github/scripts/validate_catalog.py [--links] [--write]

Checks:
  * every entry has all required fields and headings
  * no code blocks, GUIDs, secrets or internal-only hostnames in the content
  * relative links resolve (and external links with --links)
  * the README summary table matches the entries (--write regenerates it)

Standard library only.
"""
import argparse
import datetime as dt
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATEGORIES = {"assess": "Assess", "build": "Build", "operate": "Operate"}
MATURITY = ["Prototype", "Field-tested", "Production-ready"]
KEYS = ["name", "category", "maturity", "maintainer_name", "maintainer_alias", "repo_url", "last_reviewed"]
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

errors, warnings = [], []


def rel(p):
    return Path(p).resolve().relative_to(ROOT).as_posix()


def report(kind, path, msg):
    bucket = errors if kind == "error" else warnings
    bucket.append((path, msg))
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::{kind} file={path}::{msg}")
    else:
        print(f"{kind.upper():7} {path}: {msg}")


def parse_front_matter(text):
    if not text.startswith("---"):
        return None, text
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n?(.*)", text, re.S)
    if not m:
        return None, text
    data = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        k, sep, v = line.partition(":")
        if not sep:
            continue
        v = v.strip()
        if v[:1] in "\"'":
            q = v[0]
            end = v.find(q, 1)
            v = v[1:end] if end > 0 else v[1:]
        else:
            v = re.sub(r"\s+#.*$", "", v)
        data[k.strip()] = v.strip()
    return data, m.group(2)


def sections(body):
    out, current = {}, None
    for line in body.splitlines():
        m = re.match(r"##\s+(.*?)\s*$", line)
        if m:
            current = m.group(1)
            out[current] = []
        elif current:
            out[current].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def strip_comments(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def is_placeholder(v):
    return bool(PLACEHOLDER.search(v))


def codeowners_patterns():
    f = ROOT / ".github" / "CODEOWNERS"
    pats = set()
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                pats.add(line.split()[0])
    return pats


def check_entry(path, owners):
    r = rel(path)
    text = path.read_text(encoding="utf-8")
    fm, body = parse_front_matter(text)
    if fm is None:
        report("error", r, "missing front matter block (--- ... ---) at top of file")
        return None
    if not SLUG.match(path.name):
        report("error", r, "file name must be lowercase kebab-case, for example my-resource.md")
    for k in KEYS:
        if not fm.get(k):
            report("error", r, f"missing or empty field: {k}")
    if any(k not in KEYS for k in fm):
        report("error", r, "unknown field(s): " + ", ".join(k for k in fm if k not in KEYS))

    folder = path.parent.name
    if fm.get("category") and fm["category"] != CATEGORIES.get(folder):
        report("error", r, f"category '{fm['category']}' doesn't match folder '{folder}' (expected {CATEGORIES.get(folder)})")

    mat = fm.get("maturity", "")
    if mat and not is_placeholder(mat) and mat not in MATURITY:
        report("error", r, f"maturity must be one of: {', '.join(MATURITY)}")

    alias = fm.get("maintainer_alias", "")
    if alias and not is_placeholder(alias):
        if not ALIAS.match(alias):
            report("error", r, "maintainer_alias must be a GitHub handle without the @")
        elif f"/catalog/{folder}/{path.name}" not in owners:
            report("warning", r, "no matching rule in .github/CODEOWNERS")

    url = fm.get("repo_url", "")
    if url and not is_placeholder(url) and not re.match(r"https://\S+$", url):
        report("error", r, "repo_url must be an https:// link")

    lr = fm.get("last_reviewed", "")
    if lr and not is_placeholder(lr):
        try:
            d = dt.date.fromisoformat(lr)
            if d > dt.date.today():
                report("error", r, "last_reviewed is in the future")
            elif (dt.date.today() - d).days > STALE_DAYS:
                report("warning", r, f"last_reviewed is more than {STALE_DAYS} days ago")
        except ValueError:
            report("error", r, "last_reviewed must be a date in YYYY-MM-DD format")

    h1 = re.search(r"^#\s+(.+?)\s*$", body, re.M)
    if not h1:
        report("error", r, "missing '# <name>' title")
    elif fm.get("name") and h1.group(1) != fm["name"]:
        report("error", r, "title doesn't match the name field")

    secs = sections(strip_comments(body))
    for h in HEADINGS:
        if h not in secs:
            report("error", r, f"missing heading: ## {h}")
        elif not secs[h].strip() or secs[h].strip() == "-":
            report("error", r, f"section is empty: {h}")
    for h, subs in SUBFIELDS.items():
        for s in subs:
            if h in secs and not re.search(rf"^\s*[-*]\s+\*\*{re.escape(s)}:\*\*\s*\S", secs[h], re.M):
                report("error", r, f"'{h}' needs a filled-in '**{s}:**' bullet")
    what = secs.get("What it does", "")
    if what and not is_placeholder(what):
        if len(re.findall(r"[.!?](\s|$)", what.strip())) > 2:
            report("warning", r, "'What it does' should be one or two sentences")

    for label, rx in FORBIDDEN:
        if rx.search(text):
            report("error", r, f"found {label}")

    todos = len(PLACEHOLDER.findall(text))
    if todos:
        report("warning", r, f"{todos} placeholder(s) to confirm")
    return fm


def check_template():
    p = ROOT / "templates" / "entry-template.md"
    r = rel(p)
    if not p.exists():
        report("error", r, "template is missing")
        return
    text = p.read_text(encoding="utf-8")
    fm, body = parse_front_matter(text)
    if fm is None or any(k not in fm for k in KEYS):
        report("error", r, "template front matter must include every required field")
    secs = sections(strip_comments(body))
    for h in HEADINGS:
        if h not in secs:
            report("error", r, f"template missing heading: ## {h}")


def table_row(fm, path):
    name = f"[{fm['name']}]({path.relative_to(ROOT).as_posix()})"
    url = fm["repo_url"]
    link = url if is_placeholder(url) else f"[Repository]({url})"
    alias = fm["maintainer_alias"]
    who = fm["maintainer_name"] if is_placeholder(alias) else f"{fm['maintainer_name']} (@{alias})"
    return f"| {name} | {fm['category']} | {fm['maturity']} | {who} | {link} |"


def build_table(entries):
    order = list(CATEGORIES.values())
    rows = sorted(entries, key=lambda e: (order.index(e[0]["category"]) if e[0]["category"] in order else 99, e[0]["name"].lower()))
    head = ["| Name | Category | Maturity | Maintainer | Link |", "|---|---|---|---|---|"]
    return "\n".join(head + [table_row(fm, p) for fm, p in rows])


def check_readme(entries, write):
    p = ROOT / "README.md"
    r = rel(p)
    text = p.read_text(encoding="utf-8")
    if TABLE_START not in text or TABLE_END not in text:
        report("error", r, f"missing table markers {TABLE_START} and {TABLE_END}")
        return
    pre, rest = text.split(TABLE_START, 1)
    current, post = rest.split(TABLE_END, 1)
    expected = "\n" + build_table(entries) + "\n"
    if current.replace("\r\n", "\n") == expected:
        return
    if write:
        p.write_text(pre + TABLE_START + expected + TABLE_END + post, encoding="utf-8", newline="\n")
        print(f"updated summary table in {r}")
    else:
        report("error", r, "summary table is out of date. Run: python .github/scripts/validate_catalog.py --write")


LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|<(https?://[^>\s]+)>")


def md_files():
    files = [ROOT / "README.md", ROOT / "CONTRIBUTING.md"]
    files += sorted((ROOT / "catalog").rglob("*.md"))
    return [f for f in files if f.exists()]


def collect_links():
    for f in md_files():
        text = strip_comments(f.read_text(encoding="utf-8"))
        fm, body = parse_front_matter(text)
        if fm and fm.get("repo_url", "").startswith("http"):
            yield f, fm["repo_url"]
        for m in LINK.finditer(body):
            yield f, (m.group(1) or m.group(2))


def check_relative_links():
    for f, target in collect_links():
        if re.match(r"(https?:|mailto:|#)", target) or is_placeholder(target):
            continue
        path = target.split("#", 1)[0].split("?", 1)[0]
        if path and not (f.parent / path).resolve().exists():
            report("error", rel(f), f"broken relative link: {target}")


def check_external_links():
    seen = {}
    for f, url in collect_links():
        if not url.startswith("http") or is_placeholder(url):
            continue
        url = url.split("#", 1)[0]
        seen.setdefault(url, rel(f))
    for url, where in seen.items():
        status = None
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "catalog-link-check"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    status = resp.status
                break
            except urllib.error.HTTPError as e:
                status = e.code
                if e.code < 500:
                    break
            except Exception as e:
                status = str(e)
            time.sleep(2)
        if status == 200 or (isinstance(status, int) and 200 <= status < 400):
            continue
        if status in (404, 410):
            report("error", where, f"link doesn't resolve ({status}): {url}")
        else:
            report("warning", where, f"couldn't confirm link ({status}): {url}")


def check_stray_files():
    for f in (ROOT / "catalog").rglob("*"):
        if f.is_file() and f.suffix != ".md":
            report("error", rel(f), "only Markdown files belong in /catalog (links only, no code)")
        if f.is_file() and f.suffix == ".md" and f.parent.name not in CATEGORIES:
            report("error", rel(f), "entries must live in /catalog/assess, /catalog/build or /catalog/operate")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--links", action="store_true", help="also check external links over the network")
    ap.add_argument("--write", action="store_true", help="regenerate the README summary table")
    args = ap.parse_args()

    owners = codeowners_patterns()
    entries = []
    for folder in CATEGORIES:
        d = ROOT / "catalog" / folder
        if not d.is_dir():
            report("error", f"catalog/{folder}", "category folder is missing")
            continue
        for f in sorted(d.glob("*.md")):
            if f.name.lower() == "readme.md":
                continue
            fm = check_entry(f, owners)
            if fm and all(fm.get(k) for k in KEYS):
                entries.append((fm, f))
    names = [e[0]["name"].lower() for e in entries]
    for n in {n for n in names if names.count(n) > 1}:
        report("error", "catalog", f"duplicate entry name: {n}")

    check_template()
    check_stray_files()
    check_readme(entries, args.write)
    check_relative_links()
    if args.links:
        check_external_links()

    print(f"\n{len(entries)} entries, {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
