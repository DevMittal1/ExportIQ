---
name: buyer-qualification
description: Defines evidence standards for qualifying potential commercial buyers, evaluating corporate registry filings, and assessing international import activity.
license: Apache-2.0
metadata:
  version: 1.0.0
---

# Buyer Qualification & Discovery Guide

This skill standardizes the evidence requirements and risk controls when identifying and vetting potential importers.

## 1. Three-Tier Lead Qualification Standard
To protect exporters from bogus leads and broker spam, categorize every candidate buyer:

- **Tier 1 — Verified Importer:**
  - Entity appears as Consignee on physical customs shipping manifests / Bills of Lading matching the product HS code within the last 18 months.
  - Active corporate registry standing in destination country.
  - Verifiable corporate domain and physical office/warehouse footprint.

- **Tier 2 — Active Industry Distributor / Wholesaler:**
  - Active corporate registry standing with relevant industrial classification (NACE / SIC wholesale or manufacturing).
  - Verifiable public product catalogue distributing competing or complementary goods.
  - Established corporate history (>2 years in business).

- **Tier 3 — Unverified Web Lead:**
  - Company directory or trade-fair exhibitor mention without verified registry data or confirmed customs activity.
  - Must include explicit cautionary disclaimer in reporting.

## 2. Red Flags & Automatic Disqualification
Immediately discard any company matching the following conditions:
1. Corporate registry status is `Dissolved`, `In Liquidation`, `Bankrupt`, or `Inactive`.
2. Registered address is a known virtual forwarding box / shell company domicile with no commercial operations.
3. Domain registered less than 90 days ago with hidden WHOIS ownership.
4. Entity listed on multilateral sanctions lists (OFAC, EU Consolidated Sanctions, UN Sanctions).
