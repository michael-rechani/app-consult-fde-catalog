---
name: Azure AI Observatory
category: Operate
maturity: Prototype
maintainer_name: Michael Rechani
maintainer_alias: michael-rechani
repo_url: https://github.com/michael-rechani/azure-ai-observability
last_reviewed: 2026-11-06
---

# Azure AI Observatory

## What it does

Provides Azure Managed Grafana dashboards for Microsoft Foundry agents and Azure OpenAI deployments using provisioned throughput units (PTUs), with optional cost visibility. Terraform or Bicep deploys the monitoring resources and dashboards.

## When to use it

- **Scenario:** A team wants to monitor Foundry agents or Azure OpenAI provisioned deployments.
- **What you get:** Grafana dashboards, metric alerts and an optional cost dashboard.

## Prerequisites

- **Access:** Permission to create Azure resources and assign roles, a Microsoft Entra object ID for a Grafana administrator, and an alert email address.
- **Tooling:** Azure command-line interface (CLI) with Bicep and PowerShell 7, or Terraform and Azure CLI. The optional Terraform cost collector also needs PowerShell 7.
- **Azure services:** Existing Foundry or Azure OpenAI accounts; PTU alerts need existing provisioned deployments. The deployment creates Azure Managed Grafana, Application Insights and Log Analytics resources.

## Limits

- A sample, not an official Microsoft product. Azure resources and telemetry can incur charges.
- Agent dashboards need instrumented telemetry. The repository's screenshots use simulated data.
- The optional cost dashboard shows account-attributed costs, not deployment-level spend. Billing data can lag, and the collector has not been validated against live Azure billing data.
- The dashboards do not cover Azure API Management.
