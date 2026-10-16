---
name: Azure Resource Tagger
category: Operate
maturity: Field-tested
maintainer_name: Zac Larsen
maintainer_alias: z-larsen
repo_url: https://github.com/z-larsen/AzureResourceTagger
last_reviewed: 2026-10-16
---

# Azure Resource Tagger

## What it does

A Windows desktop tool that scans Azure subscriptions for tagging gaps and shows tag coverage. It can apply or remove tags in bulk after you preview the changes, with dry run on by default.

## When to use it

- **Scenario:** A team has years of inconsistent tagging and wants to clean it up, for example before turning on an Azure Policy that enforces tags.
- **What you get:** A view of tag coverage by resource group and resource, and a reviewed set of tag changes applied at scale.

## Prerequisites

- **Access:** Reader on the subscription to scan. Tag Contributor on the target scope to apply or remove tags.
- **Tooling:** Windows with PowerShell 5.1 or 7, and the Az.Accounts, Az.Resources and Az.ResourceGraph modules.
- **Azure services:** Azure Resource Graph and Azure Resource Manager tags. Works with Azure Commercial and Azure Government.

## Limits

- Windows only. It doesn't run on macOS or Linux.
- It's for interactive cleanup. Ongoing tag governance belongs in Azure Policy.
- Resource locks and policy still apply to tag changes.
