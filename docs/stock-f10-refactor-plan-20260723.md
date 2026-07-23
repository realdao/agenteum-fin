# stock_f10 重构方案：一次调用拿齐基本面分析资料

> 日期：2026-07-23
> 测试标的：贵州茅台（600519.SH，A股）、腾讯控股（00700.HK，港股）
> 对比对象：agenteum_fin `stock_f10`、workspace 技能 `company-fundamental-analysis`、wind 系列（`wind-mcp-skill`、`wind-alice`）

## 1. 背景与目标

`stock_f10` 是 agenteum_fin 里定位"公司基本面档案"的工具，但实测支撑不了通用基本面分析。重构目标：

**agent 对单只股票发起一次调用，即拿到覆盖以下七个维度的结构化资料：商业模式、产业链定位、业务结构、盈利能力、成长性、运营能力、债务风险。**

## 2. 实测对比

### 2.1 agenteum_fin stock_f10（现状）

实测 `600519.SH` 五个 section：

| section | 实测内容 | 评价 |
| --- | --- | --- |
| `company_profile` | 基本资料、申万/证监会行业、高管、公司简介、经营范围、IPO 信息 | 可用，是"定位"维度的主要来源 |
| `financial_analysis` | 8 期 headline 指标表：营收/营收同比/归母净利/EPS/每股净资产/每股经营现金流/毛利率/加权ROE/分红 | 缺扣非净利、净利率、ROA、负债率、周转、DuPont、OCF 绝对值口径 |
| `shareholders` | 股东户数、实控人、十大股东/流通股东 | 可用 |
| `capital_structure` | 股本总量与变动历史 | 可用但低频使用 |
| `latest_notice` | 最新公告摘要（未展开测） | 与公告工具重叠 |

硬伤：

1. **不支持港股**：`00700.HK` 直接返回 `unsupported_market: F10 is supported for A-shares only in v1`。
2. **没有主营业务构成**（按产品/行业/地区的收入、成本、毛利率拆分）——业务结构维度完全缺失。讽刺的是同一网关内 `iwencai_query(domain=business)` 实测能拉到茅台的结构化主营构成。
3. **没有扣非净利润**，无法判断主业盈利质量。
4. **没有资产负债表衍生指标**：资产负债率、流动比率、有息负债、货币资金、存货/应收、商誉——运营能力与债务风险两个维度缺失。
5. **输出是预排版文本**（markdown-ish 字符串内嵌表格），数字不可直接消费，agent 还要二次解析。
6. **拿全要 5 次调用**，且拼不出上述缺口。

### 2.2 company-fundamental-analysis 技能

实测 `python scripts/company_fundamental_data.py --code 600519 --format json`，**一次调用**返回结构化 JSON：

- `quote_and_valuation`：价格、市值、PE(TTM，自算)/扣非PE(TTM)/PS(TTM)、PB；
- `business`：同花顺主营简介 + 东财按行业/产品/地区构成（最新期，含收入/成本/毛利率/占比）；
- `shareholders`：十大股东 + 户数；
- `profitability_annual`：近 5 年收入/归母/**扣非**/OCF/毛利率/净利率/ROE/ROA/总资产周转/权益乘数/商誉；
- `growth_annual`：收入/归母/扣非 YoY × 4 年；
- `operations_and_debt`：最新季报 + 近 3 年报的货币资金/交易性金融资产/应收/存货/应收天数/资产负债率/流动比率/有息负债/商誉/长期股权投资；
- `balance_sheet_cleanliness`：投资收益、公允价值变动及占净利比等清洁度信号；
- `missing_information`：显式声明拿不到的（市场规模、客户集中度、量价拆分等）。

配套 `f_score.py` 输出 Piotroski 9 条规则逐项打分（茅台实测 5/9，neutral）。

**这就是"一次调用拿齐"的目标形态**，七个维度覆盖六个半（产业链定位只有主营简介文本，无上下游）。局限：

- 仅 A 股（akshare 6 位代码体系）；
- 数据源为免费接口，有零星缺失（实测十大股东中香港中央结算持股数为空）；
- 主营构成只有最新一期，无多期趋势；
- 取数与计算逻辑在 workspace 脚本里，agenteum_fin 其它工具（kline、announcements 等）无法复用。

### 2.3 wind-mcp-skill

实测腾讯（00700.HK）：

- `get_stock_basicinfo`：公司档案 + 主营收入构成（文本百分比：增值服务 49.1%/金融科技及企业服务 30.5%/本土游戏 21.8%…）+ 大股东 + 审计机构 + 员工数，字段规整；
- `get_stock_fundamentals`：近 3 年营收/净利/OCF/毛利率/ROE/资产负债率（结构化 columns/rows，含单位与币种 CNY）。

优势：**A/港/美股通吃**、Wind 数据质量、口径权威。作为"基本面快照"的问题：

- NL 接口，**返回字段集取决于问法**，同样问题换种措辞结果可能不同，不适合做稳定的数据底座；
- 拼全七个维度需要 4~6 次调用（basicinfo/fundamentals/equity_holders/events…），每次消耗积分；
- 无按产品的主营构成结构化表（成本/毛利率）、无扣非口径、无 TTM 自算；
- 估值字段（PE/PB/市值）要另走行情工具。

### 2.4 wind-alice（公司一页纸）

实测腾讯"公司一页纸"：数分钟生成完整投资 memo——护城河叙述、分部收入拆分与预测、估值水位与可比公司、催化剂、风险。内容最丰富，但它是 **LLM 报告产品**（分钟级耗时、重积分消耗、产出 prose），不是数据层。正确定位：深度研究时的**升级路径**，消费快照数据而不是替代快照。

### 2.5 能力矩阵

| 维度 | stock_f10 现状 | company-fundamental-analysis | wind-mcp | wind-alice 一页纸 |
| --- | --- | --- | --- | --- |
| 商业模式/定位 | 简介+经营范围 ✓ | 主营简介 ✓ | 档案+分部描述 ✓ | 叙述最丰富 ✓ |
| 产业链定位 | 仅行业分类 ✗ | 仅行业分类 ✗ | 部分（构成文本） | ✓（ prose ） |
| 业务结构（分产品/地区构成） | ✗ | ✓ 结构化 | 部分（文本%） | ✓ |
| 盈利能力（含扣非/ROE/DuPont） | 部分（无扣非/ROA） | ✓ | 部分（问啥给啥） | ✓ |
| 成长性（多年 YoY） | 2 列同比 | ✓ | ✓ | ✓（含预测） |
| 运营能力（周转/应收/存货） | ✗ | ✓ | 需单独问 | 部分 |
| 债务风险（负债率/有息负债/流动性） | ✗ | ✓ | 需单独问 | 部分 |
| 估值快照 | ✗（在 stock_profile） | ✓ TTM/扣非/PS | 需另调行情 | ✓ |
| 结构化 JSON | ✗（文本） | ✓ | ✓ | ✗（prose） |
| 港股 | ✗ | ✗ | ✓ | ✓ |
| 一次调用拿齐 | ✗（5 次仍缺） | ✓ | ✗（4~6 次） | ✓（分钟级+重积分） |

## 3. 重构方案

### 3.1 设计原则

1. **一次调用，默认全量**：新接口默认返回全部 block；提供 `sections` 参数按需裁剪。
2. **结构化 JSON**：数字是数字（统一"亿元"单位字段），不是内嵌在文本里；文本类（简介、经营范围）保留原文。
3. **衍生指标服务端算好**：TTM、扣非口径、YoY、DuPont、负债率、有息负债等由 provider 层计算，不让 agent 自己拼报表。
4. **块级降级**：任一 provider 失败只影响对应 block（返回 `error` + `null`），不拖垮整次调用；所有缺口进 `missing` 数组，**禁止编造**。
5. **口径显式**：标注每个 block 的 provider、报告期、币种、审计状态；扣非 vs 归母、TTM 计算窗口写进 `notes`。
6. **不重复造轮子**：原始三大报表仍走 `stock_financial_statements`，公告/新闻/研报走原有工具，Alice 一页纸是下游报告层。

### 3.2 接口形态

新增 `stock_fundamental_snapshot`（或 `stock_f10` v2 增加 `section="full"`，倾向**新工具**，避免与现有按 section 取文本的语义混淆）：

```jsonc
// 请求
{ "symbol": "600519.SH", "sections": ["all"], "annual_years": 5 }

// 响应（block 与七维度对应关系）
{
  "status": "ok",
  "symbol": { "market": "a_share", "display_symbol": "600519.SH" },
  "fetched_at": "...",
  "data": {
    "meta":        { "name": "贵州茅台", "currency": "CNY", "industry_sw": "食品饮料-白酒",
                     "industry_csrc": "制造业-酒、饮料和精制茶制造业", "providers": {...} },
    "profile":     { "简介/经营范围/成立上市/实控人/员工/高管" },        // 商业模式+定位
    "business_composition": {                                            // 业务结构
      "period": "2025-12-31",
      "by_industry": [ { "name": "酒类", "revenue_yi": 1687.7, "cost_yi": 148.1,
                          "gross_margin_pct": 91.2, "revenue_pct": 98.1 } ],
      "by_product":  [ ... ], "by_region": [ ... ],
      "previous_period": { ... }                                          // P2：多期趋势
    },
    "quote_valuation": { "price": 1292.01, "market_cap_yi": 16151.2,      // 估值快照
                         "pe_ttm": 19.53, "pe_ttm_deducted": 19.53,
                         "pe_static": 14.82, "pb": 6.94, "ps_ttm": 9.21 },
    "profitability": { "annual": [ { "period": "20251231", "revenue_yi": 1720.5,
        "net_profit_yi": 823.2, "deducted_net_profit_yi": 822.9,
        "ocf_yi": 615.2, "gross_margin_pct": 91.18, "net_margin_pct": 47.85,
        "roe_pct": 32.41, "roa_pct": 27.09, "asset_turnover": 0.566,
        "equity_multiplier": 1.196, "goodwill_yi": null } ],               // 盈利能力
      "latest_quarter": { ... } },
    "growth": [ { "period": "20251231", "revenue_yoy_pct": -1.2,
                  "net_profit_yoy_pct": -4.53, "deducted_yoy_pct": -4.58 } ], // 成长性
    "operations_solvency": [ { "period": "20251231", "cash_yi": 516.9,        // 运营+债务
        "trading_fin_assets_yi": null, "ar_yi": 0.03, "inventory_yi": 614.3,
        "receivable_days": 0.01, "liability_ratio_pct": 16.42,
        "current_ratio": 5.09, "interest_bearing_debt_yi": 0.44 } ],
    "balance_sheet_flags": { "goodwill_yi": null, "lt_equity_invest_yi": 1.47,
        "investment_income_yi": 0.006, "fair_value_gain_yi": 0.76,
        "fv_gain_to_net_profit": 0.001 },                                  // 清洁度信号
    "shareholders": { "holder_count": 243159, "controller": "贵州省国资委",
                      "top10": [ ... ] },
    "missing": [ "customer_concentration", "volume_price_split", ... ],
    "notes": [ "TTM=最新季报+上年年报-上年同期", "扣非口径优先于归母" ]
  }
}
```

### 3.3 Provider 编排（A 股）

全部复用 agenteum_fin 已有 provider，主要工作量在**服务端计算层与聚合 schema**：

| block | 数据来源 | 状态 |
| --- | --- | --- |
| meta / profile / shareholders / 股本 | eastmoney F10（现有 stock_f10 provider） | 已有 |
| 三大报表取数 | sina（现有 stock_financial_statements provider，注意偶发 timeout 需内置重试） | 已有 |
| business_composition | **iwencai business domain（实测可拉茅台结构化构成）为主**，eastmoney 主营构成兜底 | 打通即可 |
| quote_valuation 基础字段 | tencent quote（现有 stock_profile provider） | 已有 |
| TTM/扣非PE/PS、YoY、DuPont、负债率、有息负债、应收天数等 | 服务端本地计算 | **移植 `skills/company-fundamental-analysis/scripts/company_fundamental_data.py` 的逻辑** |

### 3.4 港股支持（分阶段）

- 基础可用：`stock_profile` 实测已支持港股（`00700.HK`，注意代码须归一化为 5 位数字，当前报错信息对 4 位输入不友好，顺手修）。
- P1 目标：`quote_valuation` + `profile` + `profitability/growth` 基础块。候选源：iwencai `hkstock` domain（需实测验证字段覆盖）、akshare 港股财务接口（company-fundamental-analysis 若要扩港股也是同一条路）。
- 无 provider 覆盖的 block 显式进 `missing`，并在工具描述里写明降级行为——**过渡期由 wind-mcp 补港股基本面**。

### 3.5 与其它工具/技能的边界

- **`stock_f10`：退役，不保留**。其五个 section 均为快照真子集或与其它工具重叠：profile/financial_analysis/shareholders 被快照覆盖；`latest_notice` 与 `stock_announcements` 重叠；`capital_structure` 的当前值（总股本/流通股/限售）并入快照 `meta`/`shareholders` 块，股本变动历史属低频数据直接放弃（需要时走 F10 原始页面或公告）。共存会让 agent 路由时误选单薄版本，比删除更有害。退役路径：P0 快照上线时标记 deprecated（工具描述注明"基本面分析用 stock_fundamental_snapshot"），确认无 skill/agent 引用后移除。
- `stock_financial_statements`：保留为"原始报表字段"工具（需要完整科目时才用）。
- `company-fundamental-analysis` 技能：快照上线后改为**薄封装**——数据源切到新接口，技能只保留分析框架、解读规则和 F-Score 脚本，消除两套取数逻辑漂移。
- `wind-alice` 一页纸/研报类：不变，作为深度研究升级路径。
- 明确不做的：市场规模/CAGR、客户供应商明细、一致预期、同业对比——这些属于研究层（iwencai industry/insresearch、wind、外部研究），快照只在 `missing` 里指路。

### 3.6 实施路径

- **P0（A 股快照）**：新工具 + §3.2 全 block；计算层移植 `company_fundamental_data.py`；iwencai business 接入 provider 池；同步把 `stock_f10` 标记 deprecated。
  - 验收：茅台一次调用七维度齐全，数值与 `company_fundamental_data.py --code 600519` 输出对拍一致；故意断单一 provider 验证块级降级。
- **P1（港股）**：00700.HK 至少返回 quote_valuation + profile + 基础财务块；修港股代码归一化报错体验。
  - 验收：腾讯一次调用，可用块有数据、不可用块在 `missing` 且附替代路径提示（wind-mcp）。
- **P2（增强，可选）**：构成多期趋势、F-Score block、客户/供应商集中度（iwencai business）、行业对比锚（iwencai industry）。

### 3.7 验收标准汇总

1. `stock_fundamental_snapshot("600519.SH")` 一次调用覆盖七个维度，无文本内嵌数字；
2. `stock_fundamental_snapshot("00700.HK")` 不报错，降级块显式标注；
3. 每次响应带 `providers`、`missing`、`notes`（口径），缺失字段为 `null` 而非省略或编造；
4. 单 provider 故障不影响其余 block 返回。
