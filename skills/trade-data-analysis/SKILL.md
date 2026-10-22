---
name: trade-data-analysis
description: Explains how to compare international trade flows, evaluate periods and units, calculate volume growth, and measure supplier market concentration.
license: Apache-2.0
metadata:
  version: 1.0.0
---

# Trade Data Analysis Guide

This skill standardizes the analysis of bilateral trade flows, supplier competition, and demand velocity.

## 1. Trade Value vs. Physical Volume
- **Nominal USD Values (`primaryValue`):** Distorted by global currency fluctuations, inflation, and freight rate surges.
- **Physical Quantities (`netWgt` in kg, metric tons):** The truest indicator of real consumption growth.
- **Unit Value Analysis:**
  $$\text{Unit Value} = \frac{\text{Import Value (USD)}}{\text{Net Weight (kg)}}$$
  An increase in unit value indicates premiumization or raw material inflation; a decrease may indicate price erosion or commodity dumping.

## 2. Re-Export Distortion (The Rotterdam Effect)
- Certain global trading hubs (e.g., Netherlands, Singapore, Hong Kong, UAE, Belgium) import large volumes that are subsequently re-exported without domestic consumption.
- Distinguish between Total Imports (`flowCode=M`) and Domestic Consumption by cross-referencing Re-exports (`flowCode=RX`) where available.

## 3. Mirror Statistics
- If a reporting country (importer) has delayed or unsubmitted trade data for recent calendar years, query the mirror statistics:
  - Total exports to that country reported by its primary trading partners (`flowCode=X`).
  - Annotate mirror statistics in the analysis limitations.

## 4. Supplier Market Concentration
- Calculate the Herfindahl-Hirschman Index (HHI) based on supplier market shares:
  $$HHI = \sum_{i=1}^n (s_i \times 100)^2$$
  where $s_i$ is the market share of supplying country $i$ ($0 < s_i \le 1$).
- **Benchmark Categories:**
  - $HHI < 1500$: Unconcentrated / Highly competitive market.
  - $1500 \le HHI \le 2500$: Moderately concentrated.
  - $HHI > 2500$: Highly concentrated market (dominated by 1 or 2 entrenched supplier origins).
