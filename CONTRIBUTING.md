# Contributing

Thanks for helping keep the catalog accurate. Entries are short Markdown files, so changes are quick to make and easy to review.

## What does not go in this repo

Resource content is links and descriptions only. The exception is this repository's own catalog validator, tests, templates and maintenance automation, which belong under `.github/` or `templates/`, not in `catalog/`.

Never add any of the following to resource entries, issues or pull requests:

- Resource code, scripts or deployment configuration. Put them in the resource repository and link to it.
- Customer data or customer names.
- Secrets, credentials, keys, tokens or connection strings.
- Tenant IDs, subscription IDs or other identifiers from a real environment.
- Internal-only links or references, such as internal sites, file shares, tools or team names.

Sensitive data and internal-only references are prohibited in **all** repository files, including automation. If you committed something by mistake, tell a maintainer straight away, and don't count on deleting it in a later commit.

## Add an entry

1. Make sure the resource repository is ready to be linked and is accessible to the audience that will read this catalog.
2. Copy [`templates/entry-template.md`](templates/entry-template.md) to `catalog/<category>/<entry-name>.md`.
   - `<category>` is `assess`, `build` or `operate`.
   - `<entry-name>` is lowercase with hyphens, for example `finops-multitool-tui.md`.
3. Fill in every field and section. Delete the guidance comments when you are done.
4. Add an exact `/catalog/<category>/<entry-name>.md @<handle>` line to [`.github/CODEOWNERS`](.github/CODEOWNERS), with the handle from `maintainer_alias`.
5. Regenerate the indexes and run the offline checks from the repository root, using Python 3.12 or later:
   ```
   python .github/scripts/validate_catalog.py --write
   python -m unittest discover -s .github/scripts -p "test_*.py" -v
   python .github/scripts/validate_catalog.py
   ```
   `--write` updates the marked tables in the root README and all three category READMEs, keeping the surrounding prose. Include these generated changes in your commit; don't edit their tables by hand. If validation finds an error, it writes none of the indexes. Without `--write`, stale indexes are errors.
6. Open a pull request and include the commands and their results. Offline checks run automatically.

Don't have every detail yet? Use `[TODO: confirm]` for anything you don't know and explain who can confirm it in the pull request. Placeholders produce warnings and mark the entry **Unconfirmed** in every generated table, including when a placeholder is in its body. They do not excuse a missing field, mismatched category or empty section. Reviewers decide whether an unconfirmed entry belongs in the catalog; never guess a URL, owner, maturity or review date.

## Update an entry

Edit the file and update `last_reviewed` to the date the maintainer actually reviewed the resource, not just the date a formatting change was made. Run the offline commands above and open a pull request. Changes to maturity, maintainer, group or link need regenerated indexes.

Maintainers should review their entries at least once a year. The check warns when `last_reviewed` is more than 365 days old.

## Add a group

A group is a heading in the README under a category, also shown in that category's index. To add one, add a block to [`.github/catalog-groups.json`](.github/catalog-groups.json) with only its `category` and a one-line `description`, then set `group` in the entries that belong to it. Names must be unique and belong to the same category as their entries. Groups with no entries aren't shown.

## Suggest a resource

If you don't own the resource, open a [suggestion](https://github.com/michael-rechani/app-consult-fde-catalog/issues/new?template=suggest-resource.yml). A maintainer will help find an owner and get the entry written. To flag an existing entry, [report a problem](https://github.com/michael-rechani/app-consult-fde-catalog/issues/new?template=report-entry-problem.yml).

## Required fields

Every entry has the same fields. The details go in the block at the top of the file. The rest go in four sections.

| Field | Where | Notes |
|---|---|---|
| Name | `name` | Also the page title. |
| What it does | `## What it does` | One or two plain sentences. |
| Category | `category` | Assess, Build or Operate. Must match the folder. |
| Group (optional) | `group` | Lists the entry under a group, such as AI Accelerators. Must be a name in [`.github/catalog-groups.json`](.github/catalog-groups.json) and belong to the same category. |
| When to use it | `## When to use it` | A typical scenario and what the team gets. |
| Prerequisites | `## Prerequisites` | Access, tooling and Azure services. |
| Maturity | `maturity` | Prototype, Field-tested or Production-ready. |
| Maintainer | `maintainer_name`, `maintainer_alias` | Name and GitHub handle. |
| Repository link | `repo_url` | Link to the resource repository. In generated indexes, the resource name links to that repository; **Catalog entry** links to its catalog page. If the repository URL is unconfirmed, the name is not linked. |
| Last reviewed | `last_reviewed` | A date, YYYY-MM-DD. |

Every entry also has a `## Limits` section that says what the resource doesn't cover.

## Front matter and sections

The validator uses a deliberately small YAML-compatible string format, **not a general YAML parser**:

- Start and end the front matter with `---` on its own line. Use unindented `key: value` lines; blank lines and `#` comment lines are allowed.
- Each key occurs once. Only the required keys above and optional `group` are accepted. Values are single-line strings; nothing is converted to a Boolean, number or date.
- Plain values may contain spaces and URL colons. A space followed by `#` begins an inline comment. Quote a value containing that sequence, YAML-like leading punctuation, or `: `.
- Single quotes use doubled quotes for a literal apostrophe (`'Team''s tool'`). Double quotes allow only `\"` and `\\` escapes. After a closing quote, only whitespace and an optional `#` comment are allowed.
- Lists, nested mappings, multiline scalars, anchors, aliases, tags and general YAML escape sequences are not supported. `[TODO: confirm]` is the explicit plain-value exception; quoting it is also allowed.

Use exactly one `# <name>` title matching `name`, then exactly the four `##` headings in the template's order. No extra, duplicate or nested headings. Keep the Scenario / What you get and Access / Tooling / Azure services bullets in order, each filled in once. Write `None` when a prerequisite doesn't apply. Limits needs at least one filled-in bullet. Guidance comments don't count as content.

## Maturity definitions

Pick the level that matches the evidence, not the level you hope to reach.

- **Prototype**: early work that shows an approach. Expect gaps and changes. Not yet used on a customer engagement.
- **Field-tested**: used on at least one real engagement. Known limits are written down. Users may need to adapt it.
- **Production-ready**: used on several engagements and documented. The maintainer reviews it on a regular schedule.

None of these levels is a support commitment, a warranty or a statement that the resource is suitable for production use.

## Content standards

- Describe only what the resource does today. Don't promise outcomes, service levels or support.
- Don't write that a resource is supported, guaranteed, enterprise-grade or safe or ready for production. The automated check rejects wording like this.
- Use plain language. Write for someone who has never heard of the program. Avoid marketing wording, filler and internal jargon. Spell out an acronym the first time you use it.
- Keep it short. Use the same headings as the template and don't add new ones.
- Use present tense and active voice, and write sentences that stand on their own.
- Link to public pages only.
- Use plain Markdown and the front-matter format above. No HTML, images of text or embedded content in entries. Repository documentation can use diagrams and badges.

## What the automated check does

On every pull request and push to `main`, the **Validate catalog** workflow runs the standard-library regression tests and offline validator. It checks that:

- each entry has the required fields, exact headings and filled bullets, a valid date and URL, and a matching effective maintainer rule;
- entries contain no fenced code blocks or matches for selected globally unique identifier (GUID), secret and internal-host patterns;
- entries don't use wording that implies support or a guarantee;
- local links resolve across root documentation, category pages, entries, templates and `.github/` Markdown; Markdown heading anchors are checked, including emoji headings, duplicate heading suffixes and percent-encoded paths/fragments;
- the root summary and category indexes match the same entries, grouping and sort order.

These checks are not a complete secret scanner and cannot identify every customer name, sensitive identifier or misleading claim. Manually review all changed content. Maturity and review dates remain maintainer assertions, not independently verified facts.

The local link checker supports inline links/images, reference links, public HTTP(S) autolinks, standard ATX (`#`) and single-line setext headings, and explicit HTML `id`/`name` anchors in repository docs. It ignores comments and code examples. It is not a complete Markdown renderer: avoid complex embedded HTML, extension-generated anchors or unusual nested formatting. It doesn't validate fragments on non-Markdown files or external pages. Relative paths must stay within the repository; `mailto:` links are skipped.

## External links

External sites are **not contacted in pull-request checks or tests**. The separate **Check external links** workflow runs weekly and can be started manually. To run it locally:

```
python .github/scripts/validate_catalog.py --links
```

The check requests each distinct public URL with a 10-second timeout and at most two attempts for transient failures. HTTP 404 and 410 responses are broken-link **errors**; authentication/rate limits, other HTTP failures, DNS, TLS and connection failures are **warnings** that the URL could not be confirmed. Reports name the URL and referring files. Redirects are followed, but reachability does not establish safety, correctness or public access for everyone, and remote anchors are not checked.

## Ownership

[`.github/CODEOWNERS`](.github/CODEOWNERS) requests review from the listed owners when GitHub recognizes them and they have access. The validator requires an exact rule for each confirmed maintainer and checks the **last matching rule**, including directory rules, for their `@handle`. For this lean catalog, use rooted exact file and directory paths only; wildcard rules are intentionally rejected by the validator. Shared docs, templates and automation are owned separately from resource entries.

CODEOWNERS alone does **not** make approval mandatory. That needs a branch protection rule or ruleset, and the validator cannot verify account existence, repository access or required-review settings. If you take over an entry, update the maintainer fields and its CODEOWNERS line in the same pull request. Don't require a solo maintainer to approve their own changes: GitHub doesn't allow self-approval.
