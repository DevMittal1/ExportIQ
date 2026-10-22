# TradePilot AI — System Architecture & Comprehensive API Specification
**Document Version:** 1.0.0-PROD  
**Target Environment:** Python 3.11+ / LangGraph 0.2+ / FastAPI / Redis / PostgreSQL (TimescaleDB)  
**Classification:** Technical Architecture & Component Specification Document  

---

## Table of Contents
1. [Executive Summary & Architectural Paradigm](#1-executive-summary--architectural-paradigm)
2. [External API Integration Layer (Deep-Dive Specifications)](#2-external-api-integration-layer-deep-dive-specifications)
   - 2.1 UN Comtrade Client (`UNComtradeClient`)
   - 2.2 World Bank Indicators Client (`WorldBankClient`)
   - 2.3 WTO Timeseries & Measures Client (`WTODataClient` & `WTOTradeMeasuresClient`)
   - 2.4 EU Access2Markets & TARIC Clients (`EUAccess2MarketsClient` & `EUTaricClient`)
   - 2.5 USITC HTS Client (`USITCHtsClient`)
   - 2.6 India DGFT & Export Rules Client (`IndiaExportRulesClient`)
   - 2.7 OpenCorporates Client (`OpenCorporatesClient`)
   - 2.8 Web Discovery Client (`WebDiscoveryClient` via Exa AI)
   - 2.9 Shipment Intelligence Client (`ShipmentIntelligenceClient`)
3. [Agent-Facing Tool Registry (Exact I/O & Ergonomic Contracts)](#3-agent-facing-tool-registry-exact-io--ergonomic-contracts)
   - 3.1 Trade Statistics Tools (`trade.get_import_flows`, `trade.get_export_flows`)
   - 3.2 Macroeconomics Tool (`economics.get_country_indicators`)
   - 3.3 Tariffs & Rules of Origin Tools (`tariffs.get_applied_rate`, `tariffs.check_preferential_rate`, `tariffs.check_origin_rules`)
   - 3.4 Regulatory Compliance Tool (`compliance.search_product_requirements`)
   - 3.5 Buyer Discovery & Verification Tools (`buyers.search_importers`, `buyers.verify_company`)
   - 3.6 Quantitative Analytics Tools (`analytics.calculate_demand_growth`, `analytics.calculate_supplier_concentration`, `analytics.score_export_markets`)
   - 3.7 Evidence Auditing Tools (`evidence.verify_claim`, `evidence.find_conflicts`)
   - 3.8 Meta Tools (`skills.read_skill`, `research.delegate`)
4. [Subagent Registry & Delegation Hierarchy](#4-subagent-registry--delegation-hierarchy)
   - 4.1 Orchestrator Agent (`TradePilotOrchestrator`)
   - 4.2 Trade Research Subagent (`TradeResearchAgent`)
   - 4.3 Market Access Subagent (`MarketAccessAgent`)
   - 4.4 Buyer Discovery Subagent (`BuyerDiscoveryAgent`)
   - 4.5 Evidence Verification Subagent (`EvidenceVerificationAgent`)
   - 4.6 Strict Delegation Registry (`AGENT_REGISTRY`)
5. [Skills Registry (On-Demand Versioned Knowledge Packs)](#5-skills-registry-on-demand-versioned-knowledge-packs)
   - 5.1 `hs-classification`
   - 5.2 `trade-data-analysis`
   - 5.3 `tariff-market-access`
   - 5.4 `buyer-qualification`
   - 5.5 `trade-evidence-verification`
   - 5.6 `market-scoring`
6. [Middleware Registry (Cross-Cutting Runtime Policies)](#6-middleware-registry-cross-cutting-runtime-policies)
   - 6.1 Request Validation & Guardrails
   - 6.2 Security, Prompt Injection & Human Approval
   - 6.3 Budgets, Rate Limits, Provenance & Observability
7. [Exact LangGraph Workflow & State Management](#7-exact-langgraph-workflow--state-management)
   - 7.1 State Schema (`TradePilotState`, TypedDict definitions)
   - 7.2 Graph Topology & Visual Mermaid Workflow
   - 7.3 Conditional Edges & Interruption Semantics
8. [Standard Data Contracts & Normalization Schemas](#8-standard-data-contracts--normalization-schemas)
   - 8.1 Evidence Record Specification
   - 8.2 Subagent Structured Output Contract
   - 8.3 Final Export Intelligence Report Contract
9. [Environment Variables & Deployment Configuration](#9-environment-variables--deployment-configuration)
10. [Implementation Roadmap, Verification Matrix & Benchmarking](#10-implementation-roadmap-verification-matrix--benchmarking)

---

## 1. Executive Summary & Architectural Paradigm

TradePilot AI is an enterprise-grade agentic system designed for automated cross-border trade research, regulatory compliance auditing, export market scoring, and buyer qualification. 

### Core Architectural Principles
1. **Decoupling of External APIs from Agent-Facing Tools:** Agents never call raw external REST endpoints directly. The model interacts exclusively with high-level, business-oriented tools. The backend infrastructure handles API authentication, parameter translation, rate limiting, data cleaning, unit conversion, and schema normalization into typed **Evidence Records**.
2. **Deterministic Computation vs. Probabilistic Reasoning:** Mathematical calculations (such as compound annual growth rates, Herfindahl-Hirschman index for concentration, weighted multi-criteria scoring) are implemented as deterministic code routines in Python/NumPy, never delegated to the non-deterministic arithmetic of an LLM.
3. **On-Demand Skill Injection:** To preserve context budget and prevent tool/instruction dilution, specialized domain methodologies (e.g., Rules of Origin self-assessment, HS edition crosswalks) are packaged as versioned markdown skills loaded into the agent prompt context strictly on demand via `skills.read_skill`.
4. **Zero-Trust Verification Pipeline:** Unvetted claims, web scraping results, and unstructured buyer company descriptions are treated as untrusted text. All factual assertions must pass an independent `EvidenceVerificationAgent` check prior to synthesis into the final report.
5. **Stateful Checkpointing via LangGraph:** The execution pipeline is modeled as a cyclic directed state graph with persistent storage (PostgreSQL/TimescaleDB), providing durable session execution, time-travel debugging, and human-in-the-loop interruption hooks.

```
+---------------------------------------------------------------------------------------------+
|                                    USER INTERACTION LAYER                                   |
|                          (Web UI / REST API / Export Dossier Export)                         |
+---------------------------------------------------------------------------------------------+
                                              |
                                              v
+---------------------------------------------------------------------------------------------+
|                                  MIDDLEWARE PIPELINE                                        |
|  [RequestValidation] -> [ContextAssembly] -> [ContextBudget] -> [PromptInjectionGuard]      |
+---------------------------------------------------------------------------------------------+
                                              |
                                              v
+---------------------------------------------------------------------------------------------+
|                                  TRADEPILOT ORCHESTRATOR                                    |
|          - Plan Generation  - Skill Selection  - Task Dispatch  - Follow-up Loop            |
+---------------------------------------------------------------------------------------------+
         |                                |                               |
         v                                v                               v
+----------------------+      +----------------------+      +----------------------+
|  TradeResearchAgent  |      |   MarketAccessAgent  |      |  BuyerDiscoveryAgent |
| (Demand, Flows, HHI) |      | (Tariffs, SPS, RoO)  |      | (Importers, Registry)|
+----------------------+      +----------------------+      +----------------------+
         |                                |                               |
         \--------------------------------+-------------------------------/
                                          |
                                          v
+---------------------------------------------------------------------------------------------+
|                                EVIDENCE VERIFICATION AGENT                                  |
|         - Citation Auditing  - Freshness Verification  - Contradiction Resolution           |
+---------------------------------------------------------------------------------------------+
                                          |
                                          v
+---------------------------------------------------------------------------------------------+
|                         DETERMINISTIC ANALYTICS & MARKET SCORER                             |
|          - Metric Normalization  - Weight Vectors  - Missing Data Penalty                   |
+---------------------------------------------------------------------------------------------+
                                          |
                                          v
+---------------------------------------------------------------------------------------------+
|                                FINAL CITED REPORT GENERATION                                |
+---------------------------------------------------------------------------------------------+
```

---

## 2. External API Integration Layer (Deep-Dive Specifications)

### 2.1 UN Comtrade Client (`UNComtradeClient`)
* **Role:** Primary source for bilateral and multilateral international trade flow statistics (imports, exports, re-exports) by product code and year.
* **Base URL:** `https://comtradeapi.un.org`
* **Authentication:** Primary header `Ocp-Apim-Subscription-Key: {COMTRADE_API_KEY}`
* **Primary Endpoints:**
  - `GET /data/v1/get/C/A/HS` (Commodity / Annual / Harmonized System)
  - `GET /files/v1/app/reference/countryClassifications.json` (Reference mapping for M49 country codes)
  - `GET /files/v1/app/reference/cmdHs.json` (HS code reference catalogue)
* **Key Request Parameters:**
  ```python
  {
      "period": "2021,2022,2023,2024",  # Comma-separated years (max 5 per call on standard tier)
      "reporterCode": "842",            # UN M49 numerical code (e.g., 842 = USA, 276 = DEU, 356 = IND)
      "partnerCode": "0",               # 0 = World, or specific M49 partner code
      "partner2Code": "0",              # Secondary partner (usually 0 for total flow)
      "cmdCode": "090121",              # HS code (2, 4, or 6 digits)
      "flowCode": "M,X",                # M = Import, X = Export, RX = Re-export, FM = Re-import
      "customsCode": "C00",             # Customs regime (C00 = Total customs)
      "motCode": "0",                   # Mode of Transport (0 = All)
      "includeDesc": True               # Include partner/reporter text names
  }
  ```
* **Raw Response Payload Sample:**
  ```json
  {
    "elapsedTime": "0.142s",
    "count": 1,
    "data": [
      {
        "typeCode": "C",
        "freqCode": "A",
        "refPeriodId": 2023,
        "refYear": 2023,
        "refMonth": 52,
        "period": "2023",
        "reporterCode": 276,
        "reporterISO": "DEU",
        "reporterDesc": "Germany",
        "partnerCode": 0,
        "partnerISO": "WLD",
        "partnerDesc": "World",
        "partner2Code": 0,
        "cmdCode": "090121",
        "cmdDesc": "Coffee, roasted: Not decaffeinated",
        "flowCode": "M",
        "flowDesc": "Imports",
        "primaryValue": 3481920400,
        "netWgt": 612450000,
        "isQtyEstimated": false,
        "qtyUnitCode": 8,
        "qtyUnitAbbr": "kg",
        "qty": 612450000
      }
    ]
  }
  ```
* **Error Handling & Operational Quirks:**
  - *Country Codes:* UN Comtrade exclusively indexes by UN M49 numerical country codes. The client maintains an internal bidirectional caching crosswalk (`ISO3_TO_M49` and `M49_TO_ISO3`).
  - *Rate Limits:* Standard subscription tier enforces 1 request per second and 500 requests per day. The client implements an internal LeakyBucket rate limiter and exponential backoff on HTTP 429.
  - *Data Lags:* Developing countries frequently report trade flows with a 12 to 24 month lag. If a target year returns empty, the client must automatically fall back to the most recent reported year and attach a `limitations` notice.

---

### 2.2 World Bank Indicators Client (`WorldBankClient`)
* **Role:** Contextual macroeconomic indicators (GDP, GDP growth, inflation, consumer price index, population) to evaluate market size, purchasing power, and macroeconomic stability.
* **Base URL:** `https://api.worldbank.org/v2`
* **Authentication:** None required (Public open API).
* **Primary Endpoints:**
  - `GET /v2/country/{country_iso2_or_iso3}/indicator/{indicator_id}?format=json&date={start_year}:{end_year}&per_page=50`
* **Standard Indicator Codes:**
  - `NY.GDP.MKTP.CD`: GDP at current USD.
  - `NY.GDP.MKTP.KD.ZG`: Annual GDP growth rate (percentage).
  - `SP.POP.TOTL`: Total population count.
  - `FP.CPI.TOTL.ZG`: Inflation, consumer prices (annual %).
  - `NE.IMP.GNFS.ZS`: Imports of goods and services (% of GDP).
* **Raw Response Payload Sample (World Bank dual-element array):**
  ```json
  [
    {
      "page": 1,
      "pages": 1,
      "per_page": 50,
      "total": 3,
      "sourceid": "2",
      "sourcename": "World Development Indicators",
      "lastupdated": "2024-03-28"
    },
    [
      {
        "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
        "country": {"id": "DE", "value": "Germany"},
        "countryiso3code": "DEU",
        "date": "2023",
        "value": 4456081000000,
        "unit": "",
        "obs_status": "",
        "decimal": 0
      },
      {
        "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
        "country": {"id": "DE", "value": "Germany"},
        "countryiso3code": "DEU",
        "date": "2022",
        "value": 4082469000000,
        "unit": "",
        "obs_status": "",
        "decimal": 0
      }
    ]
  ]
  ```
* **Operational Quirks:**
  - The API returns an array where element `[0]` is pagination metadata and element `[1]` contains the data records. If a country code is invalid, element `[0]` contains an `"message"` object with error codes.
  - `value` field can be `null` for recent reporting periods if data has not yet been consolidated.

---

### 2.3 WTO Timeseries & Measures Client (`WTODataClient` & `WTOTradeMeasuresClient`)
* **Role:** Multilateral trade statistics, bound and applied MFN tariff aggregates, non-tariff measures (NTMs), and trade policy indicators.
* **Base URL:** `https://api.wto.org`
* **Authentication:** Primary header `Ocp-Apim-Subscription-Key: {WTO_API_KEY}`
* **Primary Endpoints:**
  - `GET /timeseries/v1/data?i={indicator}&r={reporter}&p={partner}&ps={start_year}&pe={end_year}&pc={classification}&sp={subproduct}`
  - `GET /timeseries/v1/indicators` (List metadata catalogue)
* **Standard WTO Indicators:**
  - `TP_A_0140`: Simple average MFN applied tariff.
  - `TP_A_0160`: Trade weighted average MFN tariff.
  - `TP_B_0140`: Bound tariff average.
  - `HS_M_0010`: Merchandise imports by product breakdown.
* **Operational Caveats:**
  - WTO data is largely aggregated at the HS 2-digit or 4-digit level or national tariff averages. It is **never** used as the final authority for determining customs duties on specific shipments. It serves as a benchmark and market comparison tool.

---

### 2.4 EU Access2Markets & TARIC Clients (`EUAccess2MarketsClient` & `EUTaricClient`)
* **Role:** Official European Union regulatory clearance, TARIC 10-digit nomenclature, applied duty rates (Autonomous, Conventional/MFN, GSP, Preferential FTAs), VAT/Excise by member state, and Sanitary & Phytosanitary (SPS) rules.
* **Official Portals:**
  - Access2Markets: `https://trade.ec.europa.eu/access-to-markets`
  - EU DDS2 TARIC Consultation: `https://ec.europa.eu/taxation_customs/dds2/taric`
* **Integration Strategy:**
  - The European Commission does not expose an unrestricted public REST API for all Access2Markets services. The client uses a dual-engine architecture:
    1. **Direct TARIC XML/REST Interface:** Queries the official DDS2 database for customs measures, duty percentages, country-specific restrictions, and surveillance quotas.
    2. **Structured Crawler / Document Retrieval:** Scrapes and extracts specific product-requirement checklists (veterinary health certificates, CE marking directives, REACH chemical compliance, labeling rules) using deterministic CSS selectors with origin and destination parameters (`origin=IND&dest=DEU&hs=0901210000`).
* **Returned Measure Types:**
  - `103`: Third country duty (MFN applied rate).
  - `110`: Autonomous tariff suspension.
  - `142`: Tariff preference (FTA / GSP).
  - `705`: Import control on organic products.
  - `728`: Veterinary check (CVED).

---

### 2.5 USITC HTS Client (`USITCHtsClient`)
* **Role:** United States Harmonized Tariff Schedule (HTS) 8-digit and 10-digit statistical classification, General Rates of Duty (Col 1), Special Rates (FTAs, GSP, USMCA, AGOA), and Column 2 Rates.
* **Base URL:** `https://hts.usitc.gov/reststop`
* **Authentication:** None required (Public official REST service).
* **Primary Endpoints:**
  - `GET /reststop/search?keyword={query}`
  - `GET /reststop/api/details/sectionJSON`
* **Output Structure:**
  ```json
  [
    {
      "htsno": "0901.21.00",
      "indent": 2,
      "description": "Coffee, roasted: Not decaffeinated",
      "general": "Free",
      "special": "Free (A, AU, BH, CL, CO, D, E, IL, JO, KR, MA, OM, P, PA, PE, S, SG)",
      "other": "Free",
      "footnotes": [],
      "quotaQuantity": null,
      "units": ["kg"]
    }
  ]
  ```
* **Operational Quirks:**
  - The US HTS API returns rates as text strings (e.g., `"Free"`, `"3.2% + 1.2¢/kg"`, `"See 9903.88.15"`).
  - The client contains a specialized regex parser to extract the ad valorem component, specific duties, compound rates, and statutory Chapter 99 trade remedy references (Section 301 / 232 duties).

---

### 2.6 India DGFT & Export Rules Client (`IndiaExportRulesClient`)
* **Role:** Indian origin-side export policy (ITC-HS classification), export restrictions, prohibitions, mandatory export inspection certifications, and export promotion incentives (RoDTEP, Duty Drawback).
* **Official Sources:**
  - DGFT (Directorate General of Foreign Trade): `https://www.dgft.gov.in`
  - Indian Trade Portal: `https://www.indiantradeportal.in`
* **Integration Functionality:**
  - Maps 6-digit HS codes to Indian 8-digit ITC(HS) codes.
  - Evaluates Export Policy status: `Free`, `Restricted` (requires export authorization/license from DGFT), `Prohibited` (banned for export), or `STE` (State Trading Enterprise canalized).
  - Checks origin requirements: APEDA registration for agricultural goods, Spices Board sampling, FSSAI export certificates, or EIA (Export Inspection Agency) inspections.
  - Extracts applicable Duty Drawback rates and RoDTEP (Remission of Duties and Taxes on Exported Products) rate schedules.

---

### 2.7 OpenCorporates Client (`OpenCorporatesClient`)
* **Role:** Corporate identity verification, legal status auditing, company registration numbers, officer names, and registered jurisdiction checking.
* **Base URL:** `https://api.opencorporates.com/v0.4`
* **Authentication:** Query parameter or header `api_token={OPENCORPORATES_API_TOKEN}`
* **Primary Endpoints:**
  - `GET /v0.4/companies/search?q={company_name}&jurisdiction_code={country_code}`
  - `GET /v0.4/companies/{jurisdiction_code}/{company_number}`
* **Key Response Fields:**
  - `company.name`: Legal registered name.
  - `company.company_number`: State registry identifier.
  - `company.current_status`: `"Active"`, `"Dissolved"`, `"In Liquidation"`.
  - `company.incorporation_date`: Timestamp of registration.
  - `company.registered_address_in_full`: Official domicile.
  - `company.industry_codes`: Standard Industrial Classification (SIC / NACE).
* **Operational Caveat:**
  - OpenCorporates confirms **legal existence** and company standing. It **does not prove** that the company currently imports or distributes the specific product.

---

### 2.8 Web Discovery Client (`WebDiscoveryClient` via Exa AI)
* **Role:** Neural web discovery of candidate importers, wholesalers, distributors, retail buyers, and trade-fair exhibitor directories.
* **Provider:** Exa AI (chosen over deprecated Google Custom Search JSON API).
* **Base URL:** `https://api.exa.ai`
* **Authentication:** Header `x-api-key: {WEB_SEARCH_API_KEY}`
* **Primary Endpoint:**
  - `POST /search`
* **Request Payload Structure:**
  ```json
  {
    "query": "specialty coffee green beans importers distributors Germany Hamburg 'customs clearance'",
    "useAutoprompt": true,
    "type": "neural",
    "numResults": 15,
    "includeDomains": [],
    "excludeDomains": ["wikipedia.org", "pinterest.com", "youtube.com"],
    "contents": {
      "text": {"maxCharacters": 1500}
    }
  }
  ```
* **Security Guard:**
  - Retrieved web page texts are flagged as **untrusted external content** and routed through `PromptInjectionGuard` before inclusion in LLM contexts.

---

### 2.9 Shipment Intelligence Client (`ShipmentIntelligenceClient`)
* **Role:** Commercial customs bill of lading (B/L) and shipping manifest analysis to verify actual, physical import transactions.
* **Provider:** Configurable paid tier (e.g., ImportYeti, Volza, Panjiva, ImportGenius).
* **Standard Normalized Manifest Schema:**
  - `consignee_name`: Actual importing entity.
  - `shipper_name`: Foreign exporter.
  - `arrival_date`: ISO-8601 date.
  - `port_of_unlading`: Destination port.
  - `declared_hs_code`: 6-digit to 10-digit customs declaration code.
  - `product_description`: Commercial invoice commodity text.
  - `weight_kg`: Declared net/gross weight.
  - `container_teu`: Total Twenty-foot Equivalent Units.

---

## 3. Agent-Facing Tool Registry (Exact I/O & Ergonomic Contracts)

The model interacts with 16 strongly-typed tools. Each tool includes explicit ergonomic descriptions preventing misuse, strictly typed Pydantic parameters, and normalized return structures.

### 3.1 Trade Statistics Tools

#### `trade.get_import_flows`
* **Agent Description:**
  > "Retrieve annual or multi-year import trade flows for a specific product HS code and destination country. Returns total import value in USD, physical quantity, top supplying partner countries, and year-over-year trade movements. Use this to assess market size, import demand velocity, and import dependence. CANNOT prove company-specific orders or current-month real-time arrivals."
* **Input Schema (JSON Schema):**
  ```json
  {
    "type": "object",
    "properties": {
      "hs_code": {
        "type": "string",
        "pattern": "^[0-9]{2,6}$",
        "description": "2, 4, or 6 digit Harmonized System product code (e.g. '090121')."
      },
      "reporter": {
        "type": "string",
        "pattern": "^[A-Z]{3}$",
        "description": "ISO-3 alpha country code of importing destination (e.g. 'DEU', 'USA', 'GBR')."
      },
      "period": {
        "type": "array",
        "items": {"type": "integer"},
        "description": "List of calendar years to retrieve (e.g. [2021, 2022, 2023]). Max 5 years."
      },
      "partners": {
        "type": "array",
        "items": {"type": "string"},
        "default": ["WLD"],
        "description": "List of supplying partner country ISO-3 codes, or ['WLD'] for world aggregate."
      }
    },
    "required": ["hs_code", "reporter", "period"]
  }
  ```
* **Output Schema (JSON Schema):**
  ```json
  {
    "type": "object",
    "properties": {
      "status": {"type": "string", "enum": ["success", "partial", "error"]},
      "reporter": {"type": "string"},
      "hs_code": {"type": "string"},
      "flows": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "year": {"type": "integer"},
            "partner": {"type": "string"},
            "import_value_usd": {"type": "number"},
            "net_weight_kg": {"type": "number"},
            "unit_value_usd_per_kg": {"type": "number"}
          },
          "required": ["year", "partner", "import_value_usd"]
        }
      },
      "provenance": {
        "type": "object",
        "properties": {
          "source": {"type": "string"},
          "retrieved_at": {"type": "string", "format": "date-time"}
        }
      },
      "limitations": {
        "type": "array",
        "items": {"type": "string"}
      }
    },
    "required": ["status", "reporter", "hs_code", "flows", "provenance"]
  }
  ```

#### `trade.get_export_flows`
* **Agent Description:**
  > "Retrieve export statistics for a supplying country to compare competitor market shares across destinations. Returns export volumes, destination distribution, and unit values. Use this to benchmark your origin country against competing global suppliers. CANNOT verify freight shipping routes or transit transshipment points."
* **Inputs:** `hs_code` (string), `reporter` (ISO-3 origin country), `partners` (list of ISO-3 destinations or `['WLD']`), `period` (list of years).
* **Outputs:** Typed list of export values, partner breakdowns, market share percentages, and source metadata.

---

### 3.2 Macroeconomics Tool

#### `economics.get_country_indicators`
* **Agent Description:**
  > "Retrieve macroeconomic indicators for candidate markets from the World Bank. Returns GDP (current USD), GDP growth rate (annual %), total population, and inflation rate (CPI). Use as contextual economic indicators to gauge market stability and purchasing capacity. CANNOT be used as a substitute for product-specific trade demand."
* **Input Schema:**
  ```json
  {
    "type": "object",
    "properties": {
      "country_codes": {
        "type": "array",
        "items": {"type": "string", "pattern": "^[A-Z]{3}$"},
        "description": "List of ISO-3 country codes to evaluate."
      },
      "indicator_codes": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": ["NY.GDP.MKTP.CD", "NY.GDP.MKTP.KD.ZG", "SP.POP.TOTL", "FP.CPI.TOTL.ZG"]
        },
        "description": "World Bank indicator identifiers."
      },
      "period": {
        "type": "array",
        "items": {"type": "integer"},
        "description": "Calendar years to query."
      }
    },
    "required": ["country_codes", "indicator_codes", "period"]
  }
  ```
* **Output Schema:** Keyed dictionary mapping `country_code` -> `indicator_code` -> list of year/value pairs, with missing indicators explicitly flagged.

---

### 3.3 Tariffs & Rules of Origin Tools

#### `tariffs.get_applied_rate`
* **Agent Description:**
  > "Find the standard Most-Favoured-Nation (MFN) or statutory applied customs tariff for a product imported into a destination country from a specified origin. Returns ad valorem duty rate, specific duties, tariff schedule edition, legal notes, and official source. Use this as the baseline tariff benchmark. CANNOT confirm preferential rates under Free Trade Agreements without calling check_preferential_rate."
* **Inputs:** `hs_code` (string), `origin` (ISO-3), `destination` (ISO-3), `date` (ISO-8601 string).
* **Outputs:** `applied_rate_percent` (number), `rate_type` (`ad_valorem`, `specific`, `compound`), `raw_rate_text` (string), `source_authority` (string), `effective_date` (string).

#### `tariffs.check_preferential_rate`
* **Agent Description:**
  > "Check whether a preferential tariff or tariff-rate quota applies between origin and destination under a trade agreement (e.g. FTA, EPA, GSP). Identifies applicable preferential margin, agreement name, and mandatory qualification conditions. CANNOT certify origin without verifying specific product origin rules."
* **Inputs:** `hs_code` (string), `origin` (ISO-3), `destination` (ISO-3), `date` (ISO-8601 string).
* **Outputs:** `is_preferential_available` (bool), `agreement_name` (string), `preferential_rate` (string), `rules_of_origin_summary` (string), `proof_of_origin_required` (e.g. "EUR.1", "REX statement on origin", "COO Form A").

#### `tariffs.check_origin_rules`
* **Agent Description:**
  > "Retrieve the precise Product-Specific Rules of Origin (PSR) required to qualify for tariff preferences under a stated trade agreement. Identifies whether the rule requires Change in Tariff Heading (CTH/CTSH), Regional Value Content (RVC), or Specific Manufacturing Process (SP). Use to determine whether an exporter's bill of materials qualifies for zero or reduced duty."
* **Inputs:** `hs_code` (string), `agreement` (string), `origin` (ISO-3), `destination` (ISO-3).
* **Outputs:** `rule_type` (`CTH`, `CTSH`, `RVC`, `SP`), `rvc_threshold_percent` (optional number), `rule_text` (string), `cumulation_provisions` (string), `de_minimis_allowance` (string).

---

### 3.4 Regulatory Compliance Tool

#### `compliance.search_product_requirements`
* **Agent Description:**
  > "Search official regulatory import requirements, restrictions, technical barriers (TBT), and sanitary/phytosanitary (SPS) measures at destination. Returns mandatory product certifications, testing standards, labeling rules, packaging directives, and competent inspection agencies. CANNOT guarantee immediate customs clearance without physical shipment inspection."
* **Inputs:** `hs_code` (string), `origin` (ISO-3), `destination` (ISO-3), `keywords` (optional list of strings).
* **Outputs:** List of regulatory items containing `category` (`SPS`, `TBT`, `LABELING`, `IMPORT_BAN`, `DOCUMENTARY`), `description` (string), `competent_authority` (string), `mandatory_documents` (list of strings), `official_reference_url` (string).

---

### 3.5 Buyer Discovery & Verification Tools

#### `buyers.search_importers`
* **Agent Description:**
  > "Discover companies in the destination country that operate as importers, distributors, industrial users, or wholesale buyers for the product. Searches business registries, authorized trade directories, and commercial web portals. Returns candidate companies, location, web domain, and relevance evidence. CANNOT prove current creditworthiness or live purchasing intent."
* **Inputs:** `product` (string), `hs_code` (string), `country` (ISO-3), `keywords` (list of strings, e.g. ["distributor", "importer", "specialty"]).
* **Outputs:** List of candidate companies with `company_name`, `country`, `website_url`, `business_type` (`importer`, `wholesaler`, `retailer`, `broker`), `evidence_snippet`, `relevance_score` (0.0 to 1.0).

#### `buyers.verify_company`
* **Agent Description:**
  > "Verify a candidate company's corporate identity, legal incorporation status, registered jurisdiction, official domain, and public signals of international trade activity. Returns registry number, status (Active/Dissolved), incorporation age, and audited findings. CANNOT guarantee financial solvency or provide confidential credit limits."
* **Inputs:** `company_name` (string), `country` (ISO-3), `website` (optional string), `registration_number` (optional string).
* **Outputs:** `is_registered` (bool), `registry_status` (string), `registration_number` (string), `incorporation_year` (integer), `trade_activity_signals` (list of strings), `confidence_level` (`HIGH`, `MEDIUM`, `LOW`, `REJECTED`).

---

### 3.6 Quantitative Analytics Tools

#### `analytics.calculate_demand_growth`
* **Agent Description:**
  > "Deterministically calculate Compound Annual Growth Rate (CAGR), absolute volume growth, and year-over-year percentage variances from an array of annual trade flow observations. Identifies missing years and flags inconsistent reporting units. MUST be used instead of manual model mental arithmetic."
* **Inputs:**
  ```json
  {
    "type": "object",
    "properties": {
      "observations": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "year": {"type": "integer"},
            "value": {"type": "number"}
          },
          "required": ["year", "value"]
        }
      },
      "window": {"type": "integer", "description": "Number of years for growth window (e.g. 3 or 5)."}
    },
    "required": ["observations", "window"]
  }
  ```
* **Outputs:**
  ```json
  {
    "cagr_percent": 8.42,
    "absolute_growth": 452100000,
    "start_year": 2020,
    "end_year": 2023,
    "start_value": 3120000000,
    "end_value": 3572100000,
    "data_quality_flags": []
  }
  ```

#### `analytics.calculate_supplier_concentration`
* **Agent Description:**
  > "Calculate the Herfindahl-Hirschman Index (HHI) and top-3 supplier market share (CR3) for a destination market based on partner trade values. Returns market competitiveness score and supplier concentration classification (e.g. Unconcentrated, Moderately Concentrated, Highly Concentrated)."
* **Inputs:** `partner_values` (dictionary mapping ISO-3 partner codes to import USD values).
* **Outputs:** `hhi_score` (0 to 10,000), `concentration_category` (string), `cr3_share_percent` (number), `top_suppliers` (list of ISO-3 codes with percentage shares).

#### `analytics.score_export_markets`
* **Agent Description:**
  > "Rank and score candidate export destinations using a deterministic multi-criteria decision model. Integrates import market size, 3-year CAGR, applied tariff friction, competitor concentration, and macroeconomic stability. Applies penalization for missing data points according to configurable policy."
* **Inputs:**
  - `market_metrics`: List of destination market data dictionaries (size, growth, tariff, distance, HHI).
  - `weights`: Metric weight vector (default: `market_size`: 0.25, `demand_growth`: 0.25, `tariff_advantage`: 0.20, `supplier_competition`: 0.15, `macro_stability`: 0.15).
  - `missing_data_policy`: Strategy (`penalize_zero`, `mean_imputation`, `flag_unranked`).
* **Outputs:** Ranked array of destinations with composite scores (0 to 100), breakdown by criterion, and penalty logs.

---

### 3.7 Evidence Auditing Tools

#### `evidence.verify_claim`
* **Agent Description:**
  > "Audit an empirical assertion against underlying retrieved evidence records. Checks whether the numerical claim, unit of measure, reporting period, country scope, and product code are strictly supported by the citation. Returns verification verdict (`SUPPORTED`, `CONTRADICTED`, `UNVERIFIABLE`)."
* **Inputs:** `claim` (string), `source_records` (list of Evidence Record objects).
* **Outputs:** `verdict` (string), `confidence` (0.0 to 1.0), `discrepancy_explanation` (string), `audited_source_ids` (list of strings).

#### `evidence.find_conflicts`
* **Agent Description:**
  > "Detect contradictions or statistical discrepancies across multiple sources (e.g., reporter-reported imports vs. partner-reported exports mirroring discrepancies, or disparate tariff rates reported by WTO vs. national customs schedule). Returns unresolved discrepancy tickets."
* **Inputs:** `evidence_records` (list of Evidence Record objects).
* **Outputs:** List of conflict objects with `metric_name`, `discrepant_sources`, `variance_percent`, `recommended_resolution_rule`.

---

### 3.8 Meta Tools

#### `skills.read_skill`
* **Agent Description:**
  > "Load complete, detailed operational handbook instructions for an approved domain skill from the version-controlled skills repository. Use this tool when the orchestrator or subagent requires specialized methodology (e.g., HS classification rules, ROO self-assessment, buyer qualification). CANNOT be used to read arbitrary system paths."
* **Input Schema:**
  ```json
  {
    "type": "object",
    "properties": {
      "skill_name": {
        "type": "string",
        "enum": [
          "hs-classification",
          "trade-data-analysis",
          "tariff-market-access",
          "buyer-qualification",
          "trade-evidence-verification",
          "market-scoring"
        ],
        "description": "Identifier of the approved skill."
      }
    },
    "required": ["skill_name"]
  }
  ```
* **Output:** Markdown text content of the skill handbook.

#### `research.delegate`
* **Agent Description:**
  > "Delegate a bounded, specialized research package to an authorized worker subagent. The delegator passes clear objectives, bound parameters, and constraints. Returns structured findings, normalized evidence, and limitations. MUST only delegate to registered agents."
* **Input Schema:**
  ```json
  {
    "type": "object",
    "properties": {
      "agent_name": {
        "type": "string",
        "enum": ["trade_research", "market_access", "buyer_discovery", "evidence_verification"],
        "description": "Target subagent identifier."
      },
      "objective": {
        "type": "string",
        "description": "Concise operational goal for the subagent."
      },
      "inputs": {
        "type": "object",
        "description": "Key-value parameters required for the task (hs_code, countries, periods)."
      },
      "constraints": {
        "type": "object",
        "properties": {
          "max_tool_calls": {"type": "integer", "default": 8},
          "timeout_seconds": {"type": "integer", "default": 60}
        }
      }
    },
    "required": ["agent_name", "objective", "inputs"]
  }
  ```
* **Output:** Standard Subagent Structured Output (see Section 8.2).

---

## 4. Subagent Registry & Delegation Hierarchy

Each subagent runs as an isolated execution node with its own system prompt, allowed tool subset, permitted skills, and token/execution budget.

```
                              +----------------------------+
                              |   TradePilotOrchestrator   |
                              +----------------------------+
                                             |
                   +-------------------------+-------------------------+
                   |                         |                         |
                   v                         v                         v
       +-----------------------+ +-----------------------+ +-----------------------+
       |   TradeResearchAgent  | |   MarketAccessAgent   | |  BuyerDiscoveryAgent  |
       +-----------------------+ +-----------------------+ +-----------------------+
                   |                         |                         |
                   +-------------------------+-------------------------+
                                             |
                                             v
                              +----------------------------+
                              | EvidenceVerificationAgent  |
                              +----------------------------+
```

### 4.1 TradePilotOrchestrator
* **Role:** High-level mission coordinator. Validates user request, loads top-level workflow skill, breaks query into bounded research packages, dispatches tasks, aggregates subagent outputs, checks for critical gaps, and triggers scoring and report generation.
* **Permitted Tools:** `research.delegate`, `skills.read_skill`, `analytics.score_export_markets`.
* **Permitted Skills:** `market-scoring`.
* **Execution Budget:** 15 iterations, 120s timeout, max 20,000 output tokens.

### 4.2 TradeResearchAgent
* **Role:** Specialist in global trade flows, bilateral trade balance, import demand trends, supplier competition, and macroeconomic market dynamics.
* **Permitted Tools:** `trade.get_import_flows`, `trade.get_export_flows`, `economics.get_country_indicators`, `analytics.calculate_demand_growth`, `analytics.calculate_supplier_concentration`.
* **Permitted Skills:** `trade-data-analysis`, `hs-classification`.
* **Execution Budget:** 10 tool calls, 45s timeout.

### 4.3 MarketAccessAgent
* **Role:** Specialist in destination market regulations, MFN and preferential customs tariffs, Rules of Origin (RoO) criteria, non-tariff measures (SPS/TBT), and mandatory import certifications.
* **Permitted Tools:** `tariffs.get_applied_rate`, `tariffs.check_preferential_rate`, `tariffs.check_origin_rules`, `compliance.search_product_requirements`.
* **Permitted Skills:** `tariff-market-access`.
* **Execution Budget:** 10 tool calls, 60s timeout.

### 4.4 BuyerDiscoveryAgent
* **Role:** Specialist in finding potential commercial buyers, importers, and distributors in shortlisted target markets, cross-referencing corporate registry databases and web signals.
* **Permitted Tools:** `buyers.search_importers`, `buyers.verify_company`.
* **Permitted Skills:** `buyer-qualification`.
* **Execution Budget:** 12 tool calls, 60s timeout.
* **Execution Guard:** Dispatched **only after** candidate markets have been shortlisted by TradeResearchAgent and MarketAccessAgent. Never executed on broad unranked country lists.

### 4.5 EvidenceVerificationAgent
* **Role:** Independent auditing entity. Reviews all empirical claims, verifies citations, checks data freshness, flags statistical contradictions, and inspects product classification coherence.
* **Permitted Tools:** `evidence.verify_claim`, `evidence.find_conflicts`.
* **Permitted Skills:** `trade-evidence-verification`.
* **Execution Budget:** 8 tool calls, 30s timeout.

### 4.6 Strict Delegation Registry (`AGENT_REGISTRY`)

```python
AGENT_REGISTRY = {
    "trade_research": {
        "name": "TradeResearchAgent",
        "description": "Analyze product demand, import growth, supplier concentration, and market size.",
        "skills": ["trade-data-analysis", "hs-classification"],
        "tools": [
            "trade.get_import_flows",
            "trade.get_export_flows",
            "economics.get_country_indicators",
            "analytics.calculate_demand_growth",
            "analytics.calculate_supplier_concentration"
        ],
        "max_tool_calls": 10,
        "timeout_seconds": 45
    },
    "market_access": {
        "name": "MarketAccessAgent",
        "description": "Research tariffs, preferential rules of origin, SPS/TBT compliance, and import restrictions.",
        "skills": ["tariff-market-access"],
        "tools": [
            "tariffs.get_applied_rate",
            "tariffs.check_preferential_rate",
            "tariffs.check_origin_rules",
            "compliance.search_product_requirements"
        ],
        "max_tool_calls": 10,
        "timeout_seconds": 60
    },
    "buyer_discovery": {
        "name": "BuyerDiscoveryAgent",
        "description": "Discover and verify potential commercial importers, wholesale distributors, and buyers.",
        "skills": ["buyer-qualification"],
        "tools": [
            "buyers.search_importers",
            "buyers.verify_company"
        ],
        "max_tool_calls": 12,
        "timeout_seconds": 60
    },
    "evidence_verification": {
        "name": "EvidenceVerificationAgent",
        "description": "Audit claims, verify citations, cross-check statistics, and resolve contradictory source data.",
        "skills": ["trade-evidence-verification"],
        "tools": [
            "evidence.verify_claim",
            "evidence.find_conflicts"
        ],
        "max_tool_calls": 8,
        "timeout_seconds": 30
    }
}
```

---

## 5. Skills Registry (On-Demand Versioned Knowledge Packs)

Skills are version-controlled markdown packages located in the `skills/` directory. They define domain methodologies, decision trees, and validation heuristics.

### 5.1 Skill: `hs-classification`
* **Canonical Identifier:** `hs-classification`
* **Description:** Provides systematic methodology for resolving product descriptions to 6-digit Harmonized System codes, resolving HS revision differences (HS 2012 vs 2017 vs 2022), and handling classification ambiguity.
* **Loaded When:** User request lacks an explicit 6-digit HS code, or when product description maps to multiple subheadings.
* **Core Instructions & Decision Rules:**
  1. *General Rules for Interpretation (GRI):* Apply GRI 1 (terms of headings) -> GRI 2 (incomplete/unfnished) -> GRI 3(a) (most specific description) -> GRI 3(b) (essential character).
  2. *Revision Alignment:* UN Comtrade and WTO data often report under older HS nomenclatures depending on the reporter. Always establish the HS 2022 baseline code and crosswalk backwards if historical data is truncated.
  3. *Ambiguity Directive:* If a product could fall under multiple codes (e.g. green coffee 0901.11 vs roasted coffee 0901.21), the agent must not guess; it must query with both or flag an ambiguity notification to the user.

### 5.2 Skill: `trade-data-analysis`
* **Canonical Identifier:** `trade-data-analysis`
* **Description:** Standardizes trade flow comparisons, physical unit reconciliations, growth calculations, and supplier concentration metrics.
* **Loaded When:** Trade flow statistics are requested, returned, or analyzed.
* **Core Instructions & Decision Rules:**
  1. *Value vs Volume:* Never evaluate market growth solely on USD trade value. High inflation or commodity price volatility can mask falling physical shipment volumes. Always inspect `netWgt` (kg) alongside `primaryValue` (USD).
  2. *Re-export Filtration:* Filter out entrepôt hubs (e.g., Hong Kong, Singapore, Netherlands Rotterdam effect) by cross-referencing domestic consumption vs re-export flows.
  3. *Mirror Statistics:* If destination country import reporting is delayed or unreliable, utilize mirror statistics (aggregate exports to that destination reported by all supplying partners).

### 5.3 Skill: `tariff-market-access`
* **Canonical Identifier:** `tariff-market-access`
* **Description:** Guides product-level customs duty determination, preferential trade agreement eligibility, Rules of Origin compliance, and non-tariff barrier evaluation.
* **Loaded When:** Target markets are being evaluated for customs friction and regulatory compliance.
* **Core Instructions & Decision Rules:**
  1. *Tariff Hierarchy:* MFN Applied Rate -> Preferential Agreement Rate (if origin proof satisfied) -> Tariff Rate Quota in-quota rate -> Autonomous Suspension -> Column 2 / Punitive Duties (e.g. US Sec 301).
  2. *Rules of Origin Self-Assessment (ROSA):* Check the 3 fundamental origin criteria:
     - Wholly Obtained (WO): Grown, harvested, or extracted entirely in origin.
     - Change in Tariff Heading (CTH / CTSH): Substantial transformation test.
     - Regional Value Content (RVC): Minimum local content percentage formula:
       $$\text{RVC} = \frac{\text{FOB Value} - \text{Non-Originating Materials (VNM)}}{\text{FOB Value}} \times 100\%$$
  3. *Non-Tariff Measures (NTMs):* Check mandatory maximum residue limits (MRLs) for food/agri, CE marking directives for electronics/machinery, and CITES permits for protected species.

### 5.4 Skill: `buyer-qualification`
* **Canonical Identifier:** `buyer-qualification`
* **Description:** Sets evidence standards for qualifying potential commercial buyers, evaluating corporate registry records, and assessing import capabilities.
* **Loaded When:** Buyer discovery or lead qualification is requested.
* **Core Instructions & Decision Rules:**
  1. *Tiered Qualification Standard:*
     - **Tier 1 (Verified Importer):** Documented customs shipment bills of lading matching the product HS code within the last 18 months.
     - **Tier 2 (Active Industry Distributor):** Active corporate registration, verifiable domain, public product catalogue showing direct distribution of competing or complementary goods.
     - **Tier 3 (Unverified Web Lead):** Corporate directory mention without verified registration or recent trade activity. Tier 3 leads must be marked with explicit disclaimers.
  2. *Identity Disqualification:* Any company marked as Dissolved, In Liquidation, or whose registered business address is a shared postal forwarding box without physical operations must be discarded.

### 5.5 Skill: `trade-evidence-verification`
* **Canonical Identifier:** `trade-evidence-verification`
* **Description:** Establishes source authority hierarchy, citation standards, data freshness bounds, and contradiction resolution rules.
* **Loaded When:** Before claims are accepted into the final synthesis phase.
* **Core Instructions & Decision Rules:**
  1. *Authority Hierarchy:*
     - *Level 1 (Statutory):* Official gazettes, National Customs authorities (USITC, EU TARIC, DGFT), primary multilateral treaty databases.
     - *Level 2 (Multilateral Statistical):* UN Comtrade, World Bank, WTO, IMF.
     - *Level 3 (Corporate Registries):* OpenCorporates, state corporate registers.
     - *Level 4 (Commercial / Web):* Company websites, trade fair listings, news media.
  2. *Freshness Window:* Trade flow statistics must not be older than 3 calendar years unless explicitly annotated as historical. Macroeconomic indicators must not be older than 2 calendar years.
  3. *Conflict Rule:* When UN Comtrade import totals conflict with national customs reporting by >15%, the national customs schedule is privileged and the variance must be noted in the report limitations.

### 5.6 Skill: `market-scoring`
* **Canonical Identifier:** `market-scoring`
* **Description:** Defines mathematical normalization, weighting schemes, penalty functions, and ranking policies for multi-market export suitability scoring.
* **Loaded When:** Shortlisted candidate destination markets are ready for comparative evaluation.
* **Core Instructions & Mathematical Formulas:**
  1. *Min-Max Normalization:*
     $$Z_{ij} = \frac{X_{ij} - \min(X_j)}{\max(X_j) - \min(X_j)}$$
     *(Invert for friction metrics such as tariff rates and distance: $Z'_{ij} = 1 - Z_{ij}$)*
  2. *Weighted Composite Score:*
     $$S_i = \left( \sum_{k=1}^m w_k Z_{ik} \right) \times 100 - P_{\text{missing}}$$
  3. *Missing Data Treatment:* If a country lacks verified tariff data or trade flow statistics for the reference period, a 15-point penalty ($P_{\text{missing}} = 15$) is deducted from the composite score, and the market is flagged as `PROVISIONAL_EVALUATION`.

---

## 6. Middleware Registry (Cross-Cutting Runtime Policies)

Middlewares wrap graph nodes and tool execution steps to enforce deterministic boundaries, security, rate limits, and audit logs.

```
Incoming Request
       |
       v
[RequestValidationMiddleware] ---> (Invalid schema/params? -> Terminate with 400)
       |
       v
[ContextAssemblyMiddleware]   ---> (Merge System Prompt + Active Skills + State History)
       |
       v
[ContextBudgetMiddleware]     ---> (Trim long histories, summarize tool outputs > 4k tokens)
       |
       v
[ToolAuthorizationMiddleware] ---> (Verify caller agent has permission for requested tool)
       |
       v
[RateLimitRetryMiddleware]    ---> (Check token bucket, retry with jittered backoff on 429/503)
       |
       v
  Tool Execution
       |
       v
[EvidenceProvenanceMiddleware]---> (Inject source metadata, timestamp, verification hash)
       |
       v
[PromptInjectionGuard]        ---> (Sanitize external web/search text, strip instructions)
       |
       v
[HumanApprovalMiddleware]     ---> (Side-effect actions require explicit user confirmation)
       |
       v
[ObservabilityMiddleware]     ---> (Emit OpenTelemetry traces, token counts, latency metrics)
```

### Detailed Middleware Specifications

| Middleware Name | Enforcement Point | Intercepted Event | Logic & Security Behavior |
|:---|:---|:---|:---|
| **RequestValidationMiddleware** | Workflow Entry | Initial user prompt & state | Validates that product description, HS code format, origin, and candidate destinations conform to ISO standards. Halts execution if inputs are fundamentally missing. |
| **SkillAccessMiddleware** | `skills.read_skill` tool execution | Tool invocation | Restricts skill loading strictly to the 6 approved canonical identifiers. Blocks path traversal attacks (e.g. `../../etc/passwd`). |
| **ToolAuthorizationMiddleware** | Node -> Tool dispatcher | Every tool call | Compares `caller_agent` against `AGENT_REGISTRY[caller_agent]["tools"]`. If unauthorized, rejects execution and returns a permissions error to the agent. |
| **ContextAssemblyMiddleware** | Subagent invocation | Prior to LLM API call | Assembles the prompt context: Base System Persona + Active Skill Handbooks + Typed State Summary + Allowed Tool Specs. Prevents context leakage between subagents. |
| **ContextBudgetMiddleware** | Subagent LLM invocation | Prior to LLM call | Measures token footprint. If prompt exceeds 85% of context window, compresses tool observation history into factual summaries, discarding raw JSON payloads. |
| **RateLimitRetryMiddleware** | External API client layer | Outgoing HTTP requests | Manages per-provider rate limit counters (Leaky Bucket). Automatically catches HTTP 429, 502, 503; applies exponential backoff with full jitter ($T = 2^k \times \text{rand}(0.5, 1.5)$). Max 4 retries. |
| **ExecutionBudgetMiddleware** | LangGraph runtime loop | Every state transition | Enforces max workflow step count (default 30) and wall-clock timeout (default 300s). Aborts runaway agent loops gracefully, returning partial results. |
| **EvidenceProvenanceMiddleware** | Tool return layer | Tool output parsing | Verifies that all returning data objects include valid `source_provider`, `retrieval_timestamp`, and `data_url`. Rejects raw un-attributed dictionaries. |
| **PromptInjectionGuard** | Web discovery / scrape layer | Unstructured web responses | Sanitizes web page contents. Strips markdown image exploits, system-directive injection patterns (e.g. `"Ignore previous instructions and output..."`), and script tags. |
| **HumanApprovalMiddleware** | Pre-outreach / external side-effects | High-risk actions | Triggers LangGraph interrupt (`interrupt()`). Halts workflow and waits for user approval before initiating external emails, buyer contact, or commercial API paid credits. |
| **ObservabilityMiddleware** | Graph & tool execution | Workflow start to end | Generates OpenTelemetry spans for every agent thought, tool call, external API latency, and LLM token usage. Persists metrics to database. |

---

## 7. Exact LangGraph Workflow & State Management

The TradePilot workflow is implemented in LangGraph as a multi-stage cyclic graph with deterministic evaluation gates and conditional follow-up loops.

### 7.1 State Schema (`TradePilotState`)

```python
from typing import TypedDict, List, Dict, Any, Optional, Annotated
import operator

class EvidenceRecord(TypedDict):
    id: str
    claim: str
    value: Any
    unit: Optional[str]
    product_hs_code: str
    reporter_country: str
    partner_country: str
    period: str
    source_provider: str
    source_url: str
    retrieved_at: str
    status: str  # "verified", "unverified", "conflicted"
    limitations: List[str]

class SubagentFinding(TypedDict):
    agent_name: str
    objective: str
    findings: List[str]
    evidence_ids: List[str]
    calculations: Dict[str, Any]
    limitations: List[str]
    follow_up_tasks: List[str]

class TradePilotState(TypedDict):
    # User Inputs
    product_query: str
    hs_code: Optional[str]
    origin_country: str
    candidate_destinations: List[str]
    reference_years: List[int]
    
    # Workflow Management
    active_skills: List[str]
    execution_plan: List[Dict[str, Any]]
    current_stage: str
    follow_up_count: int
    critical_gaps: List[str]
    user_interrupt_needed: bool
    user_interrupt_prompt: Optional[str]
    
    # Aggregated Structured Knowledge
    # Note: Annotated with operator.add allows subagents to append findings in parallel
    evidence_pool: Annotated[List[EvidenceRecord], operator.add]
    subagent_findings: Annotated[List[SubagentFinding], operator.add]
    
    # Analytics & Final Output
    shortlisted_destinations: List[str]
    market_rankings: List[Dict[str, Any]]
    final_report_markdown: Optional[str]
```

### 7.2 Complete Mermaid Graph Topology

```mermaid
flowchart TD
    %% Styling
    classDef startEnd fill:#1e293b,stroke:#475569,stroke-width:2px,color:#f8fafc;
    classDef middleware fill:#0f766e,stroke:#14b8a6,stroke-width:2px,color:#f8fafc;
    classDef agent fill:#1e1b4b,stroke:#6366f1,stroke-width:2px,color:#f8fafc;
    classDef decision fill:#312e81,stroke:#818cf8,stroke-width:2px,color:#f8fafc;
    classDef human fill:#831843,stroke:#f43f5e,stroke-width:2px,color:#f8fafc;
    classDef storage fill:#14532d,stroke:#22c55e,stroke-width:2px,color:#f8fafc;

    START([START: User Query]) :::startEnd --> ReqValidation[RequestValidationMiddleware] :::middleware
    
    ReqValidation --> InputCheck{Valid Inputs?} :::decision
    InputCheck -- No --> Clarify[Human Interrupt: Ask Clarification] :::human
    Clarify --> ReqValidation
    
    InputCheck -- Yes --> OrchestratorPlan[TradePilotOrchestrator: Plan & Load Skills] :::agent
    
    OrchestratorPlan --> DispatchPhase1[Parallel Dispatch: Phase 1 Core Research] :::agent
    
    subgraph Phase1Research [Phase 1: Macro & Regulatory Screening]
        TradeResearch[TradeResearchAgent: Trade Flows & Competition] :::agent
        MarketAccess[MarketAccessAgent: Tariffs & Requirements] :::agent
    end
    
    DispatchPhase1 --> TradeResearch
    DispatchPhase1 --> MarketAccess
    
    TradeResearch --> MergePhase1[Merge Phase 1 Structured Findings] :::middleware
    MarketAccess --> MergePhase1
    
    MergePhase1 --> ShortlistCheck{Candidate Markets Viable?} :::decision
    ShortlistCheck -- No --> OrchestratorAdjust[Orchestrator: Expand Search / Adjust Scope] :::agent
    OrchestratorAdjust --> DispatchPhase1
    
    ShortlistCheck -- Yes --> BuyerDispatch[BuyerDiscoveryAgent: Qualified Importers] :::agent
    
    BuyerDispatch --> MergeAllFindings[Merge Full Evidence Pool] :::middleware
    
    MergeAllFindings --> EvidenceAudit[EvidenceVerificationAgent: Audit & Cross-Check] :::agent
    
    EvidenceAudit --> CriticalGapsCheck{Critical Gaps or Conflicts?} :::decision
    
    CriticalGapsCheck -- "Yes (Count < 2)" --> FollowUp[Orchestrator: Targeted Follow-up] :::agent
    FollowUp --> DispatchPhase1
    
    CriticalGapsCheck -- "No / Max Follow-ups Exceeded" --> DeterministicScoring[Deterministic Market Scorer] :::agent
    
    DeterministicScoring --> FinalReportNode[Generate Cited Export Feasibility Report] :::agent
    
    FinalReportNode --> CheckpointState[Persist State & Checkpoint to Postgres] :::storage
    
    CheckpointState --> END([END: Deliver Export Dossier]) :::startEnd
```

### 7.3 Conditional Routing Functions

```python
def check_inputs_validity(state: TradePilotState) -> str:
    """Evaluates whether minimum viable parameters exist to conduct research."""
    if not state.get("origin_country") or not state.get("product_query"):
        return "ask_clarification"
    return "orchestrator_planning"

def evaluate_shortlist(state: TradePilotState) -> str:
    """Verifies that trade research produced at least one viable candidate market."""
    findings = state.get("subagent_findings", [])
    trade_findings = [f for f in findings if f["agent_name"] == "TradeResearchAgent"]
    if not trade_findings:
        return "adjust_search"
    # Check if markets were identified
    markets = state.get("shortlisted_destinations", [])
    if len(markets) == 0:
        return "adjust_search"
    return "buyer_discovery"

def evaluate_verification_audit(state: TradePilotState) -> str:
    """Decides whether to trigger a targeted follow-up or finalize the report."""
    gaps = state.get("critical_gaps", [])
    follow_up_count = state.get("follow_up_count", 0)
    
    # Allow maximum 2 follow-up cycles to prevent infinite loops
    if len(gaps) > 0 and follow_up_count < 2:
        return "targeted_follow_up"
    return "deterministic_scoring"
```

---

## 8. Standard Data Contracts & Normalization Schemas

### 8.1 Evidence Record Specification
Every external data observation extracted by any client or tool must be normalized into this strict schema:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "EvidenceRecord",
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique deterministic hash or UUID of the observation."
    },
    "claim": {
      "type": "string",
      "description": "Concise factual statement summarizing the empirical finding."
    },
    "value": {
      "type": ["number", "string", "boolean", "null"],
      "description": "Normalized scalar value of the finding."
    },
    "unit": {
      "type": ["string", "null"],
      "description": "Standardized unit of measurement (e.g. 'USD', 'kg', 'percent', 'metric_ton')."
    },
    "product_hs_code": {
      "type": "string",
      "pattern": "^[0-9]{2,10}$",
      "description": "HS classification code tied to the evidence."
    },
    "reporter_country": {
      "type": "string",
      "pattern": "^[A-Z]{3}$",
      "description": "ISO-3 code of reporting country."
    },
    "partner_country": {
      "type": "string",
      "pattern": "^[A-Z]{3}$",
      "description": "ISO-3 code of partner country ('WLD' for world)."
    },
    "period": {
      "type": "string",
      "description": "Reference calendar period (e.g. '2023', '2020-2023', '2024-Q1')."
    },
    "source": {
      "type": "object",
      "properties": {
        "provider": {
          "type": "string",
          "enum": ["UN Comtrade", "World Bank", "WTO", "EU Access2Markets", "EU TARIC", "USITC HTS", "DGFT India", "OpenCorporates", "Exa Web Discovery", "Customs Manifest"]
        },
        "url": {
          "type": "string",
          "format": "uri"
        },
        "retrieved_at": {
          "type": "string",
          "format": "date-time"
        }
      },
      "required": ["provider", "url", "retrieved_at"]
    },
    "status": {
      "type": "string",
      "enum": ["verified", "unverified", "conflicted", "provisional"],
      "default": "unverified"
    },
    "limitations": {
      "type": "array",
      "items": {"type": "string"}
    }
  },
  "required": [
    "id",
    "claim",
    "value",
    "product_hs_code",
    "reporter_country",
    "partner_country",
    "period",
    "source",
    "status"
  ]
}
```

### 8.2 Subagent Structured Output Contract
When any subagent completes its delegated task, it must return data conforming to this structure:

```json
{
  "agent_name": "TradeResearchAgent",
  "objective": "Analyze import demand and competitor market shares for HS 090121 in Germany and France (2021-2023).",
  "findings": [
    "Germany is Europe's largest importer of roasted non-decaffeinated coffee (HS 090121), with 2023 imports totaling $3.48B USD (612,450 metric tons).",
    "German import demand grew at a 3-year CAGR of +5.8%, driven by premium specialty coffee consumption.",
    "The German market displays low supplier concentration (HHI: 1,420), with Italy (32%), Switzerland (18%), and Poland (12%) holding the top 3 supply positions."
  ],
  "evidence": [
    {
      "id": "e8a93bc4-4720-4a88-824a-25121b671190",
      "claim": "Germany total imports of HS 090121 in 2023 reached $3,481,920,400 USD.",
      "value": 3481920400,
      "unit": "USD",
      "product_hs_code": "090121",
      "reporter_country": "DEU",
      "partner_country": "WLD",
      "period": "2023",
      "source": {
        "provider": "UN Comtrade",
        "url": "https://comtradeapi.un.org/data/v1/get/C/A/HS?reporterCode=276&cmdCode=090121&period=2023",
        "retrieved_at": "2026-10-22T14:32:00Z"
      },
      "status": "verified",
      "limitations": []
    }
  ],
  "calculations": {
    "cagr_3yr": {
      "start_year": 2020,
      "end_year": 2023,
      "start_value": 2930000000,
      "end_value": 3481920400,
      "formula": "(end / start) ** (1/3) - 1",
      "result_percent": 5.92
    },
    "hhi_supplier_concentration": {
      "hhi": 1420,
      "category": "Unconcentrated / Competitive",
      "cr3_share": 62.0
    }
  },
  "limitations": [
    "2024 calendar year data for France is only available through Q2; annualized projection applied."
  ],
  "follow_up_tasks": []
}
```

### 8.3 Final Export Intelligence Report Contract
The end result delivered to the user or downstream exporter systems:

```json
{
  "executive_summary": "Comprehensive market feasibility dossier for exporting Roasted Coffee (HS 090121) from India.",
  "product_profile": {
    "hs_code": "090121",
    "description": "Coffee, roasted: Not decaffeinated",
    "origin": "IND"
  },
  "ranked_destinations": [
    {
      "rank": 1,
      "country_iso3": "DEU",
      "country_name": "Germany",
      "suitability_score": 88.4,
      "market_size_usd": 3481920400,
      "cagr_3yr_percent": 5.8,
      "applied_tariff": "7.5% (EU MFN applied rate; GSP eligibility expired)",
      "market_access_friction": "MODERATE",
      "top_competitors": ["Italy (32%)", "Switzerland (18%)", "Poland (12%)"],
      "qualified_buyer_leads": 4
    }
  ],
  "market_access_matrix": {
    "DEU": {
      "mfn_tariff": "7.5%",
      "preferential_tariff": "N/A (No active India-EU FTA)",
      "sps_requirements": [
        "EU Maximum Residue Limits (MRLs) for Ochratoxin A (< 3.0 ug/kg)",
        "EU Organic Regulation (EU) 2018/848 certificate required for organic marketing"
      ],
      "mandatory_certifications": ["Phytosanitary Certificate", "FSSAI Export Certificate", "Coffee Board Certificate of Origin"]
    }
  },
  "buyer_directory": [
    {
      "country": "DEU",
      "company_name": "Nordic Coffee Trading GmbH",
      "registration_status": "Active (HRB 184920 Hamburg)",
      "website": "https://www.nordic-coffee-sample.de",
      "qualification_tier": "Tier 2 (Active Industry Distributor)",
      "relevance_evidence": "Specialty green and roasted coffee wholesaler operating warehouse in Hamburg port free zone."
    }
  ],
  "audit_trail": {
    "total_evidence_records": 34,
    "verified_percentage": 97.1,
    "unresolved_conflicts": 0,
    "audited_by": "EvidenceVerificationAgent v1.0.0"
  }
}
```

---

## 9. Environment Variables & Deployment Configuration

Store all credentials in a cloud secret manager (e.g. AWS Secrets Manager, GCP Secret Manager, or HashiCorp Vault) and inject as environment variables at runtime.

### Configuration Template (`.env.example`)

```ini
# ==============================================================================
# TRADEPILOT AI - ENVIRONMENT CONFIGURATION
# ==============================================================================

# Application Environment
ENVIRONMENT=production
LOG_LEVEL=INFO
APP_HOST=0.0.0.0
APP_PORT=8000

# LLM Providers
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
PRIMARY_MODEL=claude-3-5-sonnet-20241022
FALLBACK_MODEL=gpt-4o-2024-08-06

# Trade & Economic Data Providers
COMTRADE_API_KEY=ct_live_98a7bc...
WTO_API_KEY=wto_live_12de45...
# World Bank API does not require an API key

# Tariff & Customs Gateways
USITC_BASE_URL=https://hts.usitc.gov/reststop
EU_TARIC_BASE_URL=https://ec.europa.eu/taxation_customs/dds2/taric
DGFT_PORTAL_URL=https://www.dgft.gov.in

# Corporate Identity & Discovery
OPENCORPORATES_API_TOKEN=oc_tok_88291...
EXA_SEARCH_API_KEY=exa_live_44921...

# Commercial Shipment Intelligence (Optional Paid Tier)
CUSTOMS_DATA_VENDOR_API_KEY=vdr_key_991...
CUSTOMS_DATA_VENDOR_URL=https://api.shipmentdata.com/v1

# State Persistence & Caching
DATABASE_URL=postgresql://tradepilot_app:Secr3tP@ss@postgres-primary:5432/tradepilot_db
REDIS_URL=redis://:RedisP@ssword@redis-cluster:6379/0

# LangGraph Execution Controls
MAX_WORKFLOW_STEPS=30
WORKFLOW_TIMEOUT_SECONDS=300
ENABLE_HUMAN_APPROVAL_INTERRUPTS=true
EVIDENCE_VERIFICATION_STRICT_MODE=true
```

---

## 10. Implementation Roadmap, Verification Matrix & Benchmarking

### 10.1 Phased Implementation Schedule

```
Phase 1: Core Trade Intelligence
├── UNComtradeClient implementation + M49 country mapping
├── WorldBankClient implementation
├── TradeResearchAgent + trade-data-analysis skill
├── Deterministic analytics: calculate_demand_growth, calculate_supplier_concentration
└── Integration test suite for bilateral flow reconciliation

Phase 2: Market Access & Tariffs
├── USITCHtsClient implementation + Chapter 99 parsing
├── EUAccess2MarketsClient & EUTaricClient implementation
├── IndiaExportRulesClient (DGFT / RoDTEP mapping)
├── MarketAccessAgent + tariff-market-access skill
└── Integration test suite for tariff hierarchy and origin rules

Phase 3: Verification & Deterministic Scoring
├── EvidenceVerificationAgent + trade-evidence-verification skill
├── Normalized Evidence Record pipeline + Provenance middleware
├── Deterministic multi-criteria market scorer
└── End-to-end citation and contradiction resolution tests

Phase 4: Buyer Discovery & Full System Assembly
├── Exa AI WebDiscoveryClient + PromptInjectionGuard
├── OpenCorporatesClient corporate registry verification
├── BuyerDiscoveryAgent + buyer-qualification skill
├── LangGraph state graph wiring + PostgreSQL checkpointer
└── Human-in-the-loop interruption testing & UI integration
```

### 10.2 Quality & Evaluation Benchmarking Matrix

In accordance with Anthropic and DeepMind research best practices, TradePilot is benchmarked against rigorous empirical criteria across 5 dimensions:

| Metric | Target Standard | Evaluation Methodology |
|:---|:---|:---|
| **Factual Citation Accuracy** | $\ge 98.0\%$ | Every numerical claim in the final report must trace to an exact, verifiable `EvidenceRecord` ID matching the primary data source. |
| **Arithmetic Integrity** | $100\%$ | Zero LLM-generated math. All CAGRs, percentage shares, HHI concentration scores, and rankings must be produced by deterministic Python routines. |
| **Hallucination / Phantom HS Codes** | $0.0\%$ | Zero tolerance for invented 6-digit or 8-digit HS codes. Every code must exist in the WCO HS 2022 nomenclature. |
| **Tool Calling Efficiency** | $\le 18$ calls / report | Subagents must not issue redundant calls for already cached country-product pairs. Checked via Redis query cache. |
| **Prompt Injection Resilience** | $100\%$ pass | External web pages with embedded prompt override strings (e.g., `"DISREGARD PREVIOUS RULES"`) must be caught by `PromptInjectionGuard` and sanitized. |
| **End-to-End Latency** | $\le 45$ seconds | Wall-clock execution time for a full 3-destination export feasibility study with parallelized subagents. |

---
*End of Specification Document.*
