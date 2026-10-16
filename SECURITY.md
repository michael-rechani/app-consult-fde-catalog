# Security

## Report a problem with this catalog

This repository holds links and descriptions only. It has no code that runs in your environment. If you find a security problem in it, such as a link that points somewhere unsafe, or a secret, credential, customer name, tenant ID or internal-only link in any file, report it privately:

1. Go to the **Security** tab of this repository.
2. Select **Report a vulnerability**.

Please don't open a public issue for these reports.

## Report a problem with a listed resource

Each resource lives in its own repository and has its own owner. Report problems with a resource to that repository, using the link in its entry.

## Report a problem with a Microsoft product

For a vulnerability in a Microsoft product or service, use the [Microsoft Security Response Center](https://msrc.microsoft.com/create-report).

## What this repository checks

- A GitHub Actions workflow with read-only permissions checks every pull request.
- The check looks for common secret patterns and internal-only links in entries.
- Actions are pinned to a commit and kept current by Dependabot.
