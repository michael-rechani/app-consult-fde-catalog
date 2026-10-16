---
name: Foundry Agent Accelerator
category: Build
group: AI Accelerators
maturity: Prototype
maintainer_name: Michael Rechani
maintainer_alias: michael-rechani
repo_url: https://github.com/michael-rechani/foundry-agent-accelerator
last_reviewed: 2026-10-16
---

# Foundry Agent Accelerator

## What it does

Provides Microsoft Foundry hosted-agent samples: a private web app (the Lab) for browsing and trying sample agents, prebuilt review agents, and Terraform for a private-network deployment in your own Azure subscription.

## When to use it

- **Scenario:** A team wants to see how hosted agents on Microsoft Foundry work, try sample agents against sample data, or build its own agent from a template.
- **What you get:** A deployed Lab, a library of sample agents with their test results, and a base to adapt for your own agent.

## Prerequisites

- **Access:** Permission to create resources in an Azure subscription, model quota, private network access and cost approval.
- **Tooling:** Terraform and Python. The resource repository lists the versions.
- **Azure services:** Microsoft Foundry. The resource repository lists the rest.

## Limits

- A sample, not an official Microsoft product.
- Trying an agent makes model calls and costs money. Local preview makes none.
- Agent drafts for other scenarios are documentation only and aren't deployed.
