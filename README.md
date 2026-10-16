<div align="center">

# 🧭 App Consult / FDE Resource Catalog

**Every App Consult / Forward Deployed Engineering resource, one page each, same layout.**

![Azure](https://img.shields.io/badge/Microsoft-Azure-0078D4?logo=microsoftazure&logoColor=white)
![Catalog](https://img.shields.io/badge/type-catalog%20only-5C2D91)
![Links](https://img.shields.io/badge/content-links%20only-107C10)
![Entries](https://img.shields.io/badge/entries-3-FFB900)

[Browse](#-how-to-browse) · [Find the right resource](#-find-the-right-resource) · [All resources](#-all-resources) · [Maturity levels](#-maturity-levels) · [Contribute](#-contribute)

</div>

## 🚀 About the program

App Consult / FDE pairs Microsoft engineers with customer teams to assess, build and operate solutions on Azure. Alongside that hands-on work, the program maintains a set of reusable resources: health checks and WARA-style assessment scripts, FinOps tooling, AI accelerators, and monitoring and cost governance guidance.

Each resource lives in its own repository. This repository is a catalog. It has no code of its own. It describes each resource in the same way and links to where it lives, so you can see what is available and pick what fits.

```mermaid
flowchart LR
    A["🔍 Assess<br/>Where do we stand?"] --> B["🛠️ Build<br/>Start the solution"] --> C["📈 Operate<br/>Run it well"]
    style A fill:#0078D4,color:#fff,stroke:#005A9E
    style B fill:#5C2D91,color:#fff,stroke:#3B1D5E
    style C fill:#107C10,color:#fff,stroke:#0B5A0B
```

## 🗂️ How to browse

Resources are grouped by what you are trying to do:

| | Category | You want to | Examples |
|---|---|---|---|
| 🔍 | [**Assess**](catalog/assess/README.md) | Understand where a workload stands today | Health check, WARA-style scripts, FinOps |
| 🛠️ | [**Build**](catalog/build/README.md) | Start building a solution | AI accelerators |
| 📈 | [**Operate**](catalog/operate/README.md) | Run a solution that is already live | Monitoring, cost governance |

Every entry uses the same headings: what it does, when to use it, prerequisites and limits. Its details (maturity, maintainer, link, last reviewed date) are at the top of the page.

## 🎯 Find the right resource

| If your situation is... | Start with |
|---|---|
| "We have a workload running and want to know how healthy it is." | 🔍 Assess |
| "We want to check a workload against a well-architected style review." | 🔍 Assess |
| "Our Azure bill is growing and we don't know why." | 🔍 Assess (FinOps) |
| "We're starting a new AI project on Azure and want a working base." | 🛠️ Build |
| "We need dashboards and alerts for a live solution." | 📈 Operate |
| "We need budgets, tagging or other cost controls on an ongoing basis." | 📈 Operate |

Not sure where you fit? Open an issue and describe your situation.

## 📚 All resources

<!-- catalog-table:start -->
| Name | Category | Maturity | Maintainer | Link |
|---|---|---|---|---|
| [FinOps tooling](catalog/assess/finops.md) | Assess | [TODO: confirm] | [TODO: confirm] | [TODO: confirm] |
| [Health check](catalog/assess/health-check.md) | Assess | [TODO: confirm] | [TODO: confirm] | [TODO: confirm] |
| [Foundry Agent Accelerator](catalog/build/foundry-agent-accelerator.md) | Build | Prototype | Michael Rechani (@michael-rechani) | [Repository](https://github.com/michael-rechani/foundry-agent-accelerator) |
<!-- catalog-table:end -->

Details for maturity, maintainer and link are added as each entry is confirmed.

## 🌱 Maturity levels

Maturity describes how much real-world use a resource has had. It's not a support commitment.

| Level | What it means |
|---|---|
| Prototype | Early work that shows an approach. Expect gaps and changes. It hasn't been used on a customer engagement. |
| Field-tested | Used on at least one real engagement. Known limits are written down. You may need to adapt it to your environment. |
| Production-ready | Used on several engagements and documented. The maintainer reviews it on a regular schedule. |

## 🚫 What this catalog doesn't do

- It doesn't promise outcomes, service levels or support. Each resource is described as it is. Check the resource repository for its own terms.
- It doesn't hold code, scripts or customer data. Follow the links for those.

## 🤝 Contribute

To add a resource, update an entry or suggest something new, see [CONTRIBUTING.md](CONTRIBUTING.md). The short version: copy [the template](templates/entry-template.md), fill it in, add yourself to [CODEOWNERS](.github/CODEOWNERS) and open a pull request. A GitHub Actions check confirms the entry is complete, the links work and this table is up to date.
