// ============================================================
// DASHBOARD DATA CONTRACT
// Standard internal data format used by all UI, charts and risk logic.
// Excel/API payloads should be mapped into this shape before rendering.
// ============================================================

(function registerDashboardData(global) {
  "use strict";

  const CATEGORY_ORDER = ["market", "macro", "company"];

  const CATEGORIES = {
    market: {
      id: "market",
      name: "Market Risk",
      description: "Oil prices, refined products and market dynamics",
      kriCodes: [
        "MR_BRENT",
        "MR_NAPHTHA",
        "MR_GASOIL",
        "MR_GASOLINE",
        "MR_FORCADOS",
        "MR_WTI",
        "MR_JET"
      ],
      dotClass: "market-dot",
      weight: 1
    },

    macro: {
      id: "macro",
      name: "Macro/Geopolitical Risk",
      description: "Global events, policy and supply disruptions",
      kriCodes: [
        "MG_SUPPLY_DISRUPTION",
        "MG_OPEC_COMPLIANCE",
        "MG_DXY",
        "MG_GEO_TENSION"
      ],
      dotClass: "macro-dot",
      weight: 1.1
    },

    company: {
      id: "company",
      name: "Company Exposures",
      description: "Operational, credit and counterparty risks",
      kriCodes: [
        "CE_COUNTERPARTY_CREDIT",
        "CE_CUSTOMER_OFFTAKE",
        "CE_INVENTORY_STOCK",
        "CE_VLCC_FREIGHT"
      ],
      dotClass: "company-dot",
      weight: 1
    }
  };

  const SAMPLE_WORKBOOK_SCHEMA = [
    {
      field: "KRI_Code",
      purpose: "Stable internal KRI identifier, such as MR_BRENT"
    },
    {
      field: "KRI_Name",
      purpose: "Human readable KRI name"
    },
    {
      field: "Category",
      purpose: "Market Risk, Macro/Geopolitical Risk or Company Exposures"
    },
    {
      field: "Current_Value",
      purpose: "Latest numeric KRI value"
    },
    {
      field: "Previous_Value",
      purpose: "Prior observation used for 1D change"
    },
    {
      field: "Unit",
      purpose: "Display unit such as USD/bbl, %, Index or USD/day"
    },
    {
      field: "Status",
      purpose: "Optional source status; thresholds remain the primary rating logic"
    },
    {
      field: "Exposure",
      purpose: "Exposure description for company KRIs"
    },
    {
      field: "Comment",
      purpose: "Management comment or qualitative observation"
    },
    {
      field: "As_Of_Date",
      purpose: "Observation date in ISO or Excel date format"
    }
  ];

  const HISTORY_10_DATES = [
    "2026-08-31",
    "2026-09-01",
    "2026-09-02",
    "2026-09-03",
    "2026-09-04",
    "2026-09-05",
    "2026-09-06",
    "2026-09-07",
    "2026-09-08",
    "2026-09-09"
  ];

  const HISTORY_30_DATES = [
    "2026-08-11",
    "2026-08-12",
    "2026-08-13",
    "2026-08-14",
    "2026-08-15",
    "2026-08-16",
    "2026-08-17",
    "2026-08-18",
    "2026-08-19",
    "2026-08-20",
    "2026-08-21",
    "2026-08-22",
    "2026-08-23",
    "2026-08-24",
    "2026-08-25",
    "2026-08-26",
    "2026-08-27",
    "2026-08-28",
    "2026-08-29",
    "2026-08-30",
    "2026-08-31",
    "2026-09-01",
    "2026-09-02",
    "2026-09-03",
    "2026-09-04",
    "2026-09-05",
    "2026-09-06",
    "2026-09-07",
    "2026-09-08",
    "2026-09-09"
  ];

  const HISTORY_16_DATES = [
    "2026-08-10",
    "2026-08-12",
    "2026-08-14",
    "2026-08-16",
    "2026-08-18",
    "2026-08-20",
    "2026-08-22",
    "2026-08-24",
    "2026-08-26",
    "2026-08-28",
    "2026-08-30",
    "2026-09-01",
    "2026-09-03",
    "2026-09-05",
    "2026-09-07",
    "2026-09-09"
  ];

  function history(values, dates) {
    return values.map((value, index) => ({
      date: dates[index],
      value
    }));
  }

  const DEMO_KRIS = {
    MR_BRENT: {
      code: "MR_BRENT",
      marketDataCode: "PCAAS00",
      name: "Dated Brent",
      categoryId: "market",
      currentValue: 86.4,
      previousValue: 85.7,
      unit: "USD/bbl",
      format: "currency",
      decimals: 2,
      commodityCurrency: "USD",
      commodityUnit: "BBL",
      commodityValueFormat: true,
      exposure: "",
      comment: "Brent remains firm as risk premium offsets softer prompt demand.",
      history: history(
        [
          80.9, 81.4, 81.1, 81.8, 82.0, 81.7, 82.3, 82.6, 82.2, 82.8,
          83.1, 83.5, 83.2, 83.8, 84.1, 84.4, 84.0, 84.6, 84.9, 84.3,
          82.1, 82.8, 83.6, 84.4, 83.9, 84.7, 85.2, 84.9, 85.7, 86.4
        ],
        HISTORY_30_DATES
      ),
      riskRule: {
        method: "higher-is-risk",
        moderate: 85,
        high: 95
      },
      riskWeight: 1
    },

    MR_NAPHTHA: {
      code: "MR_NAPHTHA",
      marketDataCode: "PAAAM00",
      name: "Naphtha FOB Rdam Barge",
      categoryId: "market",
      currentValue: 691.15,
      previousValue: 688.3,
      unit: "USD/MT",
      format: "currency",
      decimals: 2,
      commodityCurrency: "USD",
      commodityUnit: "MT",
      commodityValueFormat: true,
      exposure: "",
      comment: "Naphtha values are firming with stronger prompt blending and petrochemical demand.",
      history: history(
        [
          641.25, 644.50, 639.75, 646.10, 650.30, 648.80, 652.40, 655.10, 651.85, 658.20,
          662.15, 659.90, 663.70, 666.25, 664.10, 668.45, 671.20, 669.75, 673.60, 676.30,
          672.40, 675.90, 679.10, 681.35, 678.75, 682.60, 686.20, 684.95, 688.30, 691.15
        ],
        HISTORY_30_DATES
      ),
      riskRule: {
        method: "higher-is-risk",
        moderate: 680,
        high: 760
      },
      riskWeight: 1
    },

    MR_GASOIL: {
      code: "MR_GASOIL",
      marketDataCode: "AAVJI00",
      name: "Gasoil 0.1%S FOB Med Cargo (NextGen MOC)",
      categoryId: "market",
      currentValue: 796.25,
      previousValue: 792.5,
      unit: "USD/MT",
      format: "currency",
      decimals: 2,
      commodityCurrency: "USD",
      commodityUnit: "MT",
      commodityValueFormat: true,
      exposure: "",
      comment: "Gasoil prices remain supported by middle-distillate tightness.",
      history: history(
        [
          721.40, 724.80, 728.20, 726.75, 731.10, 735.60, 733.25, 738.90, 742.15, 740.80,
          745.25, 748.70, 751.40, 749.95, 754.30, 758.20, 756.85, 761.60, 765.25, 768.90,
          766.40, 771.20, 775.60, 778.35, 776.80, 781.45, 786.10, 789.35, 792.50, 796.25
        ],
        HISTORY_30_DATES
      ),
      riskRule: {
        method: "higher-is-risk",
        moderate: 780,
        high: 900
      },
      riskWeight: 1
    },

    MR_GASOLINE: {
      code: "MR_GASOLINE",
      marketDataCode: "PGABM00",
      name: "Gasoline Prem Unleaded 10ppmS FOB AR Barge",
      categoryId: "market",
      currentValue: 841.35,
      previousValue: 838.15,
      unit: "USD/MT",
      format: "currency",
      decimals: 2,
      commodityCurrency: "USD",
      commodityUnit: "MT",
      commodityValueFormat: true,
      exposure: "",
      comment: "Gasoline prices remain elevated while prompt Atlantic Basin demand holds up.",
      history: history(
        [
          781.90, 785.25, 783.60, 789.10, 792.45, 790.85, 795.30, 799.20, 796.75, 801.40,
          805.85, 803.50, 807.90, 811.35, 809.70, 813.95, 817.40, 815.25, 819.80, 823.10,
          820.75, 824.30, 827.60, 825.95, 829.40, 833.25, 831.80, 835.60, 838.15, 841.35
        ],
        HISTORY_30_DATES
      ),
      riskRule: {
        method: "higher-is-risk",
        moderate: 820,
        high: 940
      },
      riskWeight: 1
    },

    MR_FORCADOS: {
      code: "MR_FORCADOS",
      marketDataCode: "PCABC00",
      name: "Forcados FOB Nigeria",
      categoryId: "market",
      currentValue: 88.05,
      previousValue: 87.1,
      unit: "USD/bbl",
      format: "currency",
      decimals: 2,
      commodityCurrency: "USD",
      commodityUnit: "BBL",
      commodityValueFormat: true,
      exposure: "",
      comment: "Forcados is trading at a premium as regional supply remains closely watched.",
      history: history(
        [
          82.1, 82.7, 82.4, 83.0, 83.3, 83.1, 83.8, 84.0, 83.7, 84.3,
          84.6, 85.0, 84.7, 85.3, 85.6, 85.9, 85.5, 86.1, 86.4, 85.9,
          83.8, 84.5, 85.2, 86.0, 85.6, 86.3, 86.8, 86.6, 87.1, 88.05
        ],
        HISTORY_30_DATES
      ),
      riskRule: {
        method: "higher-is-risk",
        moderate: 86,
        high: 96
      },
      riskWeight: 1
    },

    MR_WTI: {
      code: "MR_WTI",
      marketDataCode: "PCACG00",
      name: "WTI Cushing Mo01",
      categoryId: "market",
      currentValue: 83.1,
      previousValue: 82.45,
      unit: "USD/bbl",
      format: "currency",
      decimals: 2,
      commodityCurrency: "USD",
      commodityUnit: "BBL",
      commodityValueFormat: true,
      exposure: "",
      comment: "WTI is tracking Brent higher, with Cushing draws tightening the front end.",
      history: history(
        [
          77.4, 77.8, 77.6, 78.0, 78.3, 78.1, 78.7, 79.0, 78.8, 79.2,
          79.6, 80.0, 79.7, 80.3, 80.5, 80.8, 80.6, 81.0, 81.3, 80.9,
          78.6, 79.3, 80.1, 80.8, 80.4, 81.2, 81.7, 82.0, 82.45, 83.1
        ],
        HISTORY_30_DATES
      ),
      riskRule: {
        method: "higher-is-risk",
        moderate: 80,
        high: 90
      },
      riskWeight: 1
    },

    MR_JET: {
      code: "MR_JET",
      marketDataCode: "PJAAV00",
      name: "Jet FOB NWE Cargo",
      categoryId: "market",
      currentValue: 812.75,
      previousValue: 809.2,
      unit: "USD/MT",
      format: "currency",
      decimals: 2,
      commodityCurrency: "USD",
      commodityUnit: "MT",
      commodityValueFormat: true,
      exposure: "",
      comment: "Jet values are steady as aviation demand remains broadly resilient.",
      history: history(
        [
          742.5, 746.1, 748.4, 747.2, 751.8, 755.3, 754.6, 759.1, 762.4, 761.0,
          765.5, 768.8, 771.6, 770.2, 774.7, 778.1, 776.9, 781.4, 785.0, 788.6,
          786.2, 790.5, 794.0, 797.3, 795.8, 800.1, 804.3, 806.7, 809.2, 812.75
        ],
        HISTORY_30_DATES
      ),
      riskRule: {
        method: "higher-is-risk",
        moderate: 800,
        high: 920
      },
      riskWeight: 1
    },

    MG_SUPPLY_DISRUPTION: {
      code: "MG_SUPPLY_DISRUPTION",
      name: "Global Supply Disruption Risk",
      categoryId: "macro",
      currentValue: 62,
      previousValue: 57,
      unit: "Index 0-100",
      format: "number",
      decimals: 0,
      exposure: "",
      comment: "Shipping disruption and production outage risk have moved higher.",
      history: history(
        [38, 40, 42, 44, 47, 49, 52, 54, 57, 62],
        HISTORY_10_DATES
      ),
      riskRule: {
        method: "higher-is-risk",
        moderate: 45,
        high: 60
      },
      riskWeight: 1.2
    },

    MG_OPEC_COMPLIANCE: {
      code: "MG_OPEC_COMPLIANCE",
      name: "OPEC+ Compliance",
      categoryId: "macro",
      currentValue: 106,
      previousValue: 105,
      unit: "%",
      format: "percent",
      decimals: 0,
      exposure: "",
      comment: "Compliance remains above target, limiting downside supply pressure.",
      history: history(
        [101, 102, 103, 103, 104, 104, 105, 104, 105, 106],
        HISTORY_10_DATES
      ),
      riskRule: {
        method: "lower-is-risk",
        moderate: 100,
        high: 94
      },
      riskWeight: 0.8
    },

    MG_DXY: {
      code: "MG_DXY",
      name: "US Dollar Index (DXY)",
      categoryId: "macro",
      currentValue: 103.2,
      previousValue: 102.8,
      unit: "Index",
      format: "number",
      decimals: 1,
      exposure: "",
      comment: "A firmer dollar is a moderate headwind for crude demand and pricing.",
      history: history(
        [101.4, 101.8, 102.1, 101.9, 102.3, 102.5, 102.4, 102.6, 102.8, 103.2],
        HISTORY_10_DATES
      ),
      riskRule: {
        method: "higher-is-risk",
        moderate: 102,
        high: 107
      },
      riskWeight: 0.8
    },

    MG_GEO_TENSION: {
      code: "MG_GEO_TENSION",
      name: "Geopolitical Tension Index",
      categoryId: "macro",
      currentValue: 71,
      previousValue: 67,
      unit: "Index 0-100",
      format: "number",
      decimals: 0,
      exposure: "",
      comment: "Regional security risk remains elevated around key shipping lanes.",
      history: history(
        [35, 39, 42, 46, 44, 50, 48, 55, 58, 61, 57, 63, 65, 66, 67, 71],
        HISTORY_16_DATES
      ),
      riskRule: {
        method: "higher-is-risk",
        moderate: 50,
        high: 70
      },
      riskWeight: 1.3
    },

    CE_COUNTERPARTY_CREDIT: {
      code: "CE_COUNTERPARTY_CREDIT",
      name: "Counterparty Credit Risk",
      categoryId: "company",
      currentValue: 46,
      previousValue: 43,
      unit: "Index 0-100",
      format: "number",
      decimals: 0,
      exposure: "Top 3 counterparties",
      comment: "Two counterparties remain on watch for delayed settlement patterns.",
      history: history(
        [31, 33, 34, 35, 37, 39, 40, 42, 43, 46],
        HISTORY_10_DATES
      ),
      riskRule: {
        method: "higher-is-risk",
        moderate: 35,
        high: 60
      },
      riskWeight: 1.15
    },

    CE_CUSTOMER_OFFTAKE: {
      code: "CE_CUSTOMER_OFFTAKE",
      name: "Customer/Offtake Risk",
      categoryId: "company",
      currentValue: 38,
      previousValue: 35,
      unit: "Index 0-100",
      format: "number",
      decimals: 0,
      exposure: "Term buyers and spot offtakers",
      comment: "Asian offtake nominations softened while core term demand held stable.",
      history: history(
        [25, 26, 27, 29, 30, 31, 32, 34, 35, 38],
        HISTORY_10_DATES
      ),
      riskRule: {
        method: "higher-is-risk",
        moderate: 35,
        high: 55
      },
      riskWeight: 1
    },

    CE_INVENTORY_STOCK: {
      code: "CE_INVENTORY_STOCK",
      name: "Inventory/Stock Level",
      categoryId: "company",
      currentValue: 17,
      previousValue: 18,
      unit: "Days of cover",
      format: "number",
      decimals: 0,
      exposure: "Crude and refined products",
      comment: "Stock cover tightened as cargo arrivals slipped by one laycan.",
      history: history(
        [24, 23, 22, 21, 21, 20, 19, 19, 18, 17],
        HISTORY_10_DATES
      ),
      riskRule: {
        method: "lower-is-risk",
        moderate: 20,
        high: 14
      },
      riskWeight: 1
    },

    CE_VLCC_FREIGHT: {
      code: "CE_VLCC_FREIGHT",
      name: "VLCC Freight Rate",
      categoryId: "company",
      currentValue: 58500,
      previousValue: 55500,
      unit: "USD/day",
      format: "currency0",
      decimals: 0,
      exposure: "Spot AG-China route",
      comment: "VLCC rates increased as vessel availability tightened.",
      history: history(
        [41000, 42500, 43800, 45500, 47200, 49000, 50500, 53200, 55500, 58500],
        HISTORY_10_DATES
      ),
      riskRule: {
        method: "higher-is-risk",
        moderate: 45000,
        high: 65000
      },
      riskWeight: 1
    }
  };

  const QUALITATIVE_COMMENTS = [
    {
      id: "counterparty-credit-risk",
      sourceCode: "CE_COUNTERPARTY_CREDIT",
      title: "Counterparty Credit Risk",
      iconClass: "fa-solid fa-handshake",
      comments: [
        "Two material customers remain on enhanced payment monitoring.",
        "Additional collateral is being reviewed for open receivables above limit."
      ]
    },
    {
      id: "customer-offtake-risk",
      sourceCode: "CE_CUSTOMER_OFFTAKE",
      title: "Customer/Offtake Risk",
      iconClass: "fa-solid fa-users",
      comments: [
        "Nominations softened in one Asian outlet, but term buyer demand is stable.",
        "Spot offtake remains price-sensitive while diesel-linked demand is firmer."
      ]
    },
    {
      id: "operational-risk",
      sourceCode: "QUAL_OPERATIONAL_RISK",
      title: "Operational Risk",
      iconClass: "fa-solid fa-gears",
      comments: [
        "One terminal is running at reduced capacity during planned maintenance.",
        "No material safety incident reported; alternate loading windows remain available."
      ]
    },
    {
      id: "regulatory-esg",
      sourceCode: "QUAL_REGULATORY_ESG",
      title: "Regulatory / ESG",
      iconClass: "fa-solid fa-leaf",
      comments: [
        "Selected customers are requesting additional emissions documentation.",
        "Sanctions screening remains heightened for cargoes, vessels and intermediaries."
      ]
    }
  ];

  const MARKET_PRODUCT_PRICES = {
    naphtha: {
      code: "PAAAM00",
      name: "Naphtha FOB Rdam Barge $/mt",
      shortName: "Naphtha",
      currency: "USD",
      commodityUnit: "MT",
      unit: "USD/MT",
      history: history(
        [
          641.25, 644.50, 639.75, 646.10, 650.30, 648.80, 652.40, 655.10, 651.85, 658.20,
          662.15, 659.90, 663.70, 666.25, 664.10, 668.45, 671.20, 669.75, 673.60, 676.30,
          672.40, 675.90, 679.10, 681.35, 678.75, 682.60, 686.20, 684.95, 688.30, 691.15
        ],
        HISTORY_30_DATES
      )
    },

    gasoil: {
      code: "AAVJI00",
      name: "Gasoil 0.1%S FOB Med Cargo (NextGen MOC)",
      shortName: "Gasoil",
      currency: "USD",
      commodityUnit: "MT",
      unit: "USD/MT",
      history: history(
        [
          721.40, 724.80, 728.20, 726.75, 731.10, 735.60, 733.25, 738.90, 742.15, 740.80,
          745.25, 748.70, 751.40, 749.95, 754.30, 758.20, 756.85, 761.60, 765.25, 768.90,
          766.40, 771.20, 775.60, 778.35, 776.80, 781.45, 786.10, 789.35, 792.50, 796.25
        ],
        HISTORY_30_DATES
      )
    },

    gasoline: {
      code: "PGABM00",
      name: "Gasoline Prem Unleaded 10ppmS FOB AR Barge",
      shortName: "Gasoline",
      currency: "USD",
      commodityUnit: "MT",
      unit: "USD/MT",
      history: history(
        [
          781.90, 785.25, 783.60, 789.10, 792.45, 790.85, 795.30, 799.20, 796.75, 801.40,
          805.85, 803.50, 807.90, 811.35, 809.70, 813.95, 817.40, 815.25, 819.80, 823.10,
          820.75, 824.30, 827.60, 825.95, 829.40, 833.25, 831.80, 835.60, 838.15, 841.35
        ],
        HISTORY_30_DATES
      )
    },

    jet: {
      code: "PJAAV00",
      name: "Jet FOB NWE Cargo",
      shortName: "Jet",
      currency: "USD",
      commodityUnit: "MT",
      unit: "USD/MT",
      history: history(
        [
          742.5, 746.1, 748.4, 747.2, 751.8, 755.3, 754.6, 759.1, 762.4, 761.0,
          765.5, 768.8, 771.6, 770.2, 774.7, 778.1, 776.9, 781.4, 785.0, 788.6,
          786.2, 790.5, 794.0, 797.3, 795.8, 800.1, 804.3, 806.7, 809.2, 812.75
        ],
        HISTORY_30_DATES
      )
    }
  };

  const DASHBOARD_DATA = {
    schemaVersion: "1.0.0",
    source: {
      type: "demo",
      label: "Demo",
      name: "Realistic development sample",
      asOfDate: "2026-09-09",
      lastRefreshed: new Date().toISOString(),
      refreshEndpoint: "/api/dashboard-data"
    },
    categoryOrder: CATEGORY_ORDER,
    categories: CATEGORIES,
    kris: DEMO_KRIS,
    marketProductPrices: MARKET_PRODUCT_PRICES,
    qualitativeComments: QUALITATIVE_COMMENTS,
    geopoliticalWatchlist: [
      "Middle East shipping disruptions and supply risk around Red Sea and Hormuz.",
      "OPEC+ policy signals, quota discipline and compliance updates.",
      "Sanctions and trade policy developments affecting Russia, Iran and Venezuela."
    ],
    takeaways: [
      "Crude prices remain firm as geopolitical premium offsets softer demand signals.",
      "Supply disruption and geopolitical indicators are the main drivers of current risk.",
      "OPEC+ compliance remains supportive, while refined-product prices remain firm.",
      "Company exposure is manageable, with counterparty and freight movements on watch."
    ],
    recommendedActions: [
      "Review near-term crude and refined-product hedge coverage.",
      "Monitor refined-product price movement and freight sensitivity.",
      "Reassess counterparty limits and collateral requirements for watched accounts.",
      "Validate terminal capacity, laycan flexibility and sanctions-screening controls."
    ],
    sampleWorkbookSchema: SAMPLE_WORKBOOK_SCHEMA
  };

  function cloneDashboardData(data) {
    const source = data || DASHBOARD_DATA;

    if (typeof structuredClone === "function") {
      return structuredClone(source);
    }

    return JSON.parse(JSON.stringify(source));
  }

  function getKriList(data) {
    return Object.values((data || DASHBOARD_DATA).kris);
  }

  function normalizeKey(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function findKriCodeByName(name) {
    const normalizedName = normalizeKey(name);
    const match = getKriList(DASHBOARD_DATA).find((kri) => (
      normalizeKey(kri.name) === normalizedName
    ));

    return match ? match.code : "";
  }

  function buildSampleWorkbookRows() {
    const kriRows = getKriList(DASHBOARD_DATA).map((kri) => ({
      KRI_Code: kri.code,
      KRI_Name: kri.name,
      Category: CATEGORIES[kri.categoryId].name,
      Current_Value: kri.currentValue,
      Previous_Value: kri.previousValue,
      Unit: kri.unit,
      Status: "",
      Exposure: kri.exposure,
      Comment: kri.comment,
      As_Of_Date: DASHBOARD_DATA.source.asOfDate
    }));

    const qualitativeRows = QUALITATIVE_COMMENTS
      .filter((item) => item.sourceCode.startsWith("QUAL_"))
      .map((item) => ({
        KRI_Code: item.sourceCode,
        KRI_Name: item.title,
        Category: CATEGORIES.company.name,
        Current_Value: "",
        Previous_Value: "",
        Unit: "",
        Status: "",
        Exposure: "Qualitative observation",
        Comment: item.comments.join(" "),
        As_Of_Date: DASHBOARD_DATA.source.asOfDate
      }));

    return kriRows.concat(qualitativeRows);
  }

  global.dashboardData = DASHBOARD_DATA;

  global.OilRiskData = {
    categoryOrder: CATEGORY_ORDER,
    categories: CATEGORIES,
    sampleWorkbookSchema: SAMPLE_WORKBOOK_SCHEMA,
    sampleWorkbookRows: buildSampleWorkbookRows(),
    cloneDashboardData,
    findKriCodeByName,
    getKriList,
    normalizeKey
  };
})(typeof window !== "undefined" ? window : globalThis);
