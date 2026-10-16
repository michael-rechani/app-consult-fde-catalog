---
name: FinOps Multitool TUI
category: Assess
maturity: Prototype
maintainer_name: Zac Larsen
maintainer_alias: z-larsen
repo_url: https://github.com/z-larsen/FinOps-Multitool-TUI
last_reviewed: 2026-10-16
---

# FinOps Multitool TUI

## What it does

A terminal-based tool that runs read-only FinOps scans against Azure subscriptions. It brings cost drivers, resource inventory and optimization findings into a local report.

## When to use it

- **Scenario:** A team wants a scoped review of where Azure cost comes from and where it might be reduced, on a workload or subscription that is already running.
- **What you get:** A local report of cost drivers, resource inventory and optimization findings that the team can review and share.

## Prerequisites

- **Access:** Azure sign-in with access to the scope being scanned. Reader is a starting point. Billing, cost, storage export and hub data can need more permissions.
- **Tooling:** PowerShell 7 with the Az.Accounts, Az.ResourceGraph and Az.Storage modules.
- **Azure services:** Azure Cost Management and Azure Resource Graph. FinOps hubs and Fabric can be used as data sources.

## Limits

- An unofficial preview, not an official Microsoft release.
- Windows is the documented platform. Linux and macOS haven't been verified.
- It runs on demand. It doesn't replace Cost Management, Power BI or FinOps hubs, and it doesn't monitor between runs.
