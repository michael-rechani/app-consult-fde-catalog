## What this changes

<!-- One or two sentences. Name the entry. -->

- [ ] New entry
- [ ] Update to an existing entry
- [ ] Other (template, docs, automation)

## Checklist

- [ ] Used the [entry template](../templates/entry-template.md) and filled in every field and section
- [ ] Updated `last_reviewed` only if the entry was actually reviewed (or marked not applicable for a docs/automation change)
- [ ] Added or updated the entry's exact line in `.github/CODEOWNERS` with its maintainer's handle (or not applicable)
- [ ] Ran `python .github/scripts/validate_catalog.py --write` and included any generated README/category index changes
- [ ] Ran `python -m unittest discover -s .github/scripts -p "test_*.py" -v` and `python .github/scripts/validate_catalog.py`, with results below
- [ ] Resource content is links and descriptions only; code/configuration changes here are catalog automation only
- [ ] No secrets, customer names, tenant or subscription IDs, or internal-only links
- [ ] Describes what the resource does today, without promising outcomes or support

## Anything the reviewer should know

<!-- Include exact validation commands and results. External checks are optional:
     python .github/scripts/validate_catalog.py --links
     Say whether it ran and list broken-link errors or unreachable-site warnings.
     Note placeholders left as [TODO: confirm], who can confirm them, or open questions. -->
