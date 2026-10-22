---
name: trade-evidence-verification
description: Defines the official source authority hierarchy, data freshness windows, citation rules, and conflict resolution policies for empirical trade claims.
license: Apache-2.0
metadata:
  version: 1.0.0
---

# Trade Evidence Verification Guide

This skill governs the auditing of empirical assertions, data citations, and conflict resolution across sources.

## 1. Source Authority Hierarchy
When multiple sources report conflicting data on the same metric, resolve priority as follows:

1. **Level 1 — Statutory National Authorities:**
   - National customs authorities (e.g., USITC, EU TARIC, DGFT, HMRC, Japan Customs).
   - Official national government gazettes and statutory legal instruments.
   - *Highest authority for applied customs duties, quotas, and import bans.*

2. **Level 2 — Multilateral Statistical Bodies:**
   - UN Comtrade, World Bank, WTO, IMF, OECD.
   - *Primary authority for bilateral trade flows, macroeconomics, and cross-country comparisons.*

3. **Level 3 — Verified Corporate Registries:**
   - OpenCorporates, national corporate registries (e.g., UK Companies House, German Handelsregister, SEC).
   - *Authority for corporate identity, incorporation status, and registered officers.*

4. **Level 4 — Commercial & Web Intelligence:**
   - B/L customs manifest aggregators, company websites, trade fair catalogues, business directories.
   - *Treated as indicative evidence requiring corroboration.*

## 2. Temporal Freshness Windows
- **Trade Statistics:** Must be from the most recent 3 calendar years. Flag older statistics as historical baseline only.
- **Applied Tariffs:** Must be verified against the current calendar year tariff schedule.
- **Macroeconomic Indicators:** Must not exceed a 24-month lag from current date.

## 3. Discrepancy & Contradiction Triggers
- If UN Comtrade import totals differ from destination national customs declarations by **>15%**, log an official conflict ticket.
- Privileged resolution: Default to the National Customs authority and explain the variance (e.g., CIF vs. FOB valuation differences, transshipment re-routing).
