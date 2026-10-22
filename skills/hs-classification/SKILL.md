---
name: hs-classification
description: Guides product classification into Harmonized System (HS) 6-digit codes, HS edition crosswalking (2012/2017/2022), and handling classification ambiguity.
license: Apache-2.0
metadata:
  version: 1.0.0
---

# Harmonized System (HS) Classification Guide

This skill guides the identification and verification of HS codes for international trade research.

## Classification Hierarchy
- **Chapter (2 digits):** Broad commodity group (e.g., `09` = Coffee, tea, maté and spices).
- **Heading (4 digits):** Specific product family (e.g., `0901` = Coffee, whether or not roasted or decaffeinated).
- **Subheading (6 digits):** Universal international classification standard (e.g., `0901.21` = Coffee, roasted: Not decaffeinated).
- **National Tariff Line (8-10 digits):** Country-specific statistical suffixes (e.g., US HTS `0901.21.00.00`, India ITC-HS `0901.21.10`).

## WCO General Rules for the Interpretation (GRI)
1. **GRI 1:** Classification is determined according to the terms of the headings and relative Section/Chapter notes.
2. **GRI 2:** Incomplete, unfinished, or unassembled articles are classified with the finished article if they exhibit its essential character.
3. **GRI 3:** When goods are prima facie classifiable under two or more headings:
   - **3(a):** The heading providing the most specific description takes precedence over general headings.
   - **3(b):** Mixtures and composite goods are classified according to the material or component that gives them their *essential character*.
   - **3(c):** If neither 3(a) nor 3(b) resolves classification, classify under the heading that occurs last in numerical order.

## HS Nomenclature Revisions & Historical Alignment
- The World Customs Organization updates the HS nomenclature every 5 years (HS 2012 -> HS 2017 -> HS 2022).
- When querying historical time-series data across years, check whether the reporter country updated its reporting schedule.
- When an HS code changed between revisions, apply the official WCO correlation tables to reconcile historical trade values.

## Ambiguity Directive
- If a product query could belong to multiple subheadings (e.g., green coffee `0901.11` vs. roasted coffee `0901.21`), do NOT guess.
- Retrieve data for both candidate subheadings, document the distinction in the report findings, or prompt the user for clarification.
