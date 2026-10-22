---
name: market-scoring
description: Defines mathematical metric normalization, multi-criteria weighting matrices, missing data treatment, and ranking rules for export market suitability.
license: Apache-2.0
metadata:
  version: 1.0.0
---

# Export Market Scoring & Multi-Criteria Ranking Guide

This skill governs the deterministic mathematical ranking of candidate destination markets.

## 1. Multi-Criteria Dimension Weights
The default composite suitability model allocates weights across 5 key dimensions:
- **Market Size (USD Import Value):** 25% ($w_1 = 0.25$)
- **Demand Growth (3-Year CAGR %):** 25% ($w_2 = 0.25$)
- **Tariff Friction / Advantage (% Duty):** 20% ($w_3 = 0.20$, inverted)
- **Supplier Competition (HHI Dispersion):** 15% ($w_4 = 0.15$, inverted)
- **Macroeconomic Stability (GDP Growth & Low Inflation):** 15% ($w_5 = 0.15$)

$$\sum_{k=1}^5 w_k = 1.00$$

## 2. Min-Max Normalization
Normalize each metric across candidate destinations $i = 1, \dots, n$:
- **For Positive Drivers (Size, Growth, Stability):**
  $$Z_{ik} = \frac{X_{ik} - \min(X_k)}{\max(X_k) - \min(X_k) + \epsilon}$$
- **For Friction Drivers (Tariff Rate, High Concentration):**
  $$Z_{ik} = 1.0 - \frac{X_{ik} - \min(X_k)}{\max(X_k) - \min(X_k) + \epsilon}$$

## 3. Penalty Functions for Missing Data
- If an empirical metric cannot be obtained after all retries and mirror statistics, apply a missing data penalty $P_{\text{missing}} = 15.0$ points per missing core indicator.
- Mark the destination with status `PROVISIONAL_EVALUATION` so that decision makers know the rank has missing variables.
