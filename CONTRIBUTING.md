# Contributing

Thanks for helping keep the catalog accurate. Entries are short Markdown files, so changes are quick to make and review.

## What does not go in this repo

This repo is links only. Never add any of the following, in any file, issue or pull request:

- Code, scripts or configuration. Put them in the resource repository and link to it.
- Customer data or customer names.
- Secrets, credentials, keys, tokens or connection strings.
- Tenant IDs, subscription IDs or other identifiers from a real environment.
- Internal-only links or references, such as internal sites, file shares, tools or team names.

If you committed something by mistake, tell a maintainer straight away. Don't rely on deleting it in a later commit.

## Add an entry

1. Make sure the resource repository is ready to be linked and is accessible to the audience that will read this catalog.
2. Copy [`templates/entry-template.md`](templates/entry-template.md) to `catalog/<category>/<entry-name>.md`.
   - `<category>` is `assess`, `build` or `operate`.
   - `<entry-name>` is lowercase with hyphens, for example `finops-multitool-tui.md`.
3. Fill in every field and section. Delete the guidance comments when you are done.
4. Add a line for the new file to [`.github/CODEOWNERS`](.github/CODEOWNERS), with the maintainer's GitHub handle.
5. Run the check locally (optional):
   ```
   python .github/scripts/validate_catalog.py --write
   ```
   `--write` updates the summary table in the README. Without it, the script only checks.
6. Open a pull request. The check runs automatically.

Don't have everything yet? Use `[TODO: confirm]` for unknown details. The check lists placeholders as warnings, and the PR reviewer decides whether the entry is ready to merge.

## Update an entry

Edit the file, set `last_reviewed` to today's date and open a pull request. If the maturity, maintainer or link changed, run the script with `--write` so the README table follows.

Maintainers should review their entries at least once a year. The check warns when `last_reviewed` is more than 365 days old.

## Add a group

A group is a heading in the README under a category, with its entries listed beneath it. To add one, add a block to [`.github/catalog-groups.json`](.github/catalog-groups.json) with its `category` and a one-line `description`, then set `group` in the entries that belong to it. Groups with no entries aren't shown.

## Suggest a resource

If you don't own the resource, open a "Suggest a new resource" issue. A maintainer will find an owner and help with the entry.

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
| Repository link | `repo_url` | Link to the resource repository. The README table links the name straight to it. |
| Last reviewed | `last_reviewed` | A date, YYYY-MM-DD. |

Every entry also has a `## Limits` section that says what the resource doesn't cover.

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
- Use plain Markdown and YAML. No HTML, images of text or embedded content.

## What the automated check does

On every pull request, and weekly on `main`, a GitHub Actions workflow checks that:

- each entry has all required fields and sections, and nothing that looks like a code block, a GUID, a secret or an internal host name;
- entries don't use wording that implies support or a guarantee;
- relative and external links resolve (a broken link fails the check; a site that can't be reached is a warning);
- the summary table in the README matches the entries.

## Ownership

[`.github/CODEOWNERS`](.github/CODEOWNERS) makes each entry's maintainer a required reviewer for changes to it. If you take over an entry, update the maintainer fields and the CODEOWNERS line in the same pull request.
