# Iwencai Query Guide（同花顺问财灵活查询层）

`iwencai_query` 与 `iwencai_search` 是同花顺问财（Iwencai）OpenAPI 的灵活查询层，用自然语言覆盖 stock_* 结构化工具之外的查询场景。

## 1. 用途与路由规则

三层路由规则：

- **已知 symbol，要 K 线 / 三表 / F10 / 公告** → 用 `stock_kline`、`stock_financial_statements`、`stock_f10`、`stock_announcements`。
- **选股筛选、排名、跨截面比较、宏观、行业、指数** → 用 `iwencai_query`，按场景选择 domain。
- **主题关键词搜资讯 / 研报 / 公告（含个股新闻、个股研报）** → 用 `iwencai_search`，按内容类型选择 channel；个股新闻用 `news` channel、个股研报用 `report` channel，query 带公司名或代码。

`iwencai_query` 参数：`query`（自然语言）、`domain`（11 选 1）、`page`（默认 1）、`limit`（默认 10）、`is_retry`（默认 `false`，放宽条件重试时置 `true`）。

`iwencai_search` 参数：`query`（主题关键词）、`channel`（`news` / `report` / `announcement`）、`size`（默认 10）、`is_retry`（默认 `false`，同 `iwencai_query`）。

> 信封约定：两个工具的信封为独立约定（含 `source` / `query` / `datas` / `data` 等动态字段），**不遵循** stock_* 工具的 `BaseToolResponse` 模型（无 `provider` / `provider_status` / `fetched_at` 字段）。

## 2. Query 改写规则

将用户问句适当改写为标准的金融查询问句，保持原意不变：

- 保留用户核心意图（如：营业收入、净利润、ROE、负债率等）
- 将口语化表达转为标准金融术语
- 适当简化过于复杂的复合条件
- 改写后需保持原意不变

**常用查询改写示例：**

| 用户原始问句 | 改写后查询 |
|-------------|-----------|
| 同花顺赚了多少钱 | 同花顺营业收入 净利润 |
| 哪家公司ROE最高 | ROE最高的股票 |
| 茅台的负债情况 | 贵州茅台负债率 |
| 最近一期毛利率排名 | 毛利率排名 |
| 同花顺今天多少钱 | 同花顺最新价格 |
| 今年GDP多少 | 2024年中国GDP |
| 最近CPI怎么样 | 最近一期CPI |
| LPR利率是多少 | LPR利率 |
| M2增速如何 | M2增速 |

**实战提示（来自真实踩坑）：**

- 查公司数据时**公司名必须完整明确**（如 `恒邦股份`，不要只写"该公司"或省略主体）。问财语义解析在主体缺失或跨实体条件（自有矿山、储量、资源自给率）叠加时，可能把数据错配到同行业其他公司（如把恒邦股份的储量查询解析成紫金矿业）。返回后先核对 `股票简称` 字段是否为目标公司。
- business 域查主营业务构成/产品分项时**带上报告期**（如 `恒邦股份2025年年报主营业务构成`），避免网关按多期分页返回看似重复的行。
- 涉及毛利率等**口径敏感指标**时，注意区分产品口径、公司整体口径与行业口径；跨口径比较前先确认字段定义，不要直接对比。

## 3. 十一个 domain

### finance — 财务数据

覆盖：盈利指标（营业收入、净利润、毛利率、净利率）、回报指标（ROE、ROA）、偿债能力（负债率、资产负债结构）、现金流指标、估值指标（市盈率、市净率、市销率）。

示例 query：

- `同花顺营业收入`
- `ROE最高的股票`
- `负债率最低的行业`
- `毛利率排名`
- 同行对比：`恒邦股份、山东黄金、紫金矿业的ROE、毛利率、净利润对比`（一次查询拿到多公司同指标截面）

### market — 行情数据

覆盖：股票实时价格、涨跌幅、涨跌额、成交量、成交额、换手率、主力资金流向、大单小单、技术指标（MACD、KDJ、RSI、布林线）、ETF 行情、指数行情。

示例 query：

- `同花顺最新价格`
- `主力资金流向`
- `上证指数行情`

### macro — 宏观数据

覆盖：GDP、CPI、PPI 等国民经济核算指标；利率、汇率、社融等金融指标；PMI、工业增加值、消费、投资、进出口等经济运行指标。

示例 query：

- `2024年中国GDP`
- `最近一期CPI`
- `LPR利率`

### industry — 行业数据

覆盖：行业估值、行业财务、行业盈利、行业行情、板块排名。

示例 query：

- `A股行业估值排名`
- `银行业盈利数据`
- `新能源板块行情`

### business — 公司经营数据

覆盖：主营业务构成、主要客户、供应商、参控股公司、股权投资、重大合同。

示例 query：

- `同花顺主营业务构成`
- `主要客户`
- `参控股公司`

### management — 股东股本数据

覆盖：股本结构、股权结构、股东户数、前十大股东/流通股东、主要持有人、实控人、股权质押。

示例 query：

- `同花顺股本结构`
- `前十大股东`
- `实控人信息`

### insresearch — 机构研究与评级

覆盖：研报评级、业绩预测、ESG 评级、信用评级、主体评级、基金评级、券商金股。**分析师一致预期（共识 EPS/净利润/目标价）走这里**，比从研报正文人工提取高效得多。

示例 query：

- `同花顺研报评级`
- `恒邦股份2026年业绩预测`（一致预期 EPS/净利润）
- `恒邦股份目标价`
- `券商金股`

### astock — A 股选股

覆盖：行情指标、技术形态、财务指标、行业概念等多条件组合筛选 A 股。

示例 query：

- `今日涨跌幅超过5%的A股有哪些？`
- `科技股有哪些`
- `银行股`

### hkstock — 港股选股

覆盖：行情指标、财务指标、行业概念、陆港通等多条件组合筛选港股。

示例 query：

- `港股科技股有哪些？`
- `港股银行股`
- `北向资金增持的港股`

### sector — 板块筛选

覆盖：行业估值、资金流向、涨跌幅、板块类型等多条件组合筛选市场板块。

示例 query：

- `今日涨幅最大的板块有哪些？`
- `资金净流入的板块`
- `科技板块`

### index — 指数数据

覆盖：上证指数、沪深300、创业板指、恒生指数、纳斯达克指数等指数的点位、涨跌幅、成交量。

示例 query：

- `上证指数涨跌幅`
- `沪深300最新点位`
- `创业板指成交量`

## 3.1 常用研究场景速查

| 场景 | 工具与参数 | 示例 |
|------|-----------|------|
| 分析师一致预期（共识 EPS/净利润/目标价） | `iwencai_query` domain=`insresearch` | `恒邦股份2026年业绩预测` |
| 同行估值/财务对比 | `iwencai_query` domain=`finance`，query 列多家公司 | `恒邦股份、山东黄金、紫金矿业的市盈率、ROE对比` |
| 板块整体表现参照 | `iwencai_query` domain=`sector` 或 `industry` | `贵金属板块今日涨跌幅` |
| 指数行情参照 | `iwencai_query` domain=`index` | `上证指数涨跌幅` |
| 主力资金流向（日级） | `iwencai_query` domain=`market` | `恒邦股份主力资金流向` |
| 个股最新研报正文 | `iwencai_search` channel=`report` | `恒邦股份研究报告` |
| 个股新闻动态 | `iwencai_search` channel=`news` | `恒邦股份最新消息` |
| 股东结构/前十大股东 | `iwencai_query` domain=`management` | `恒邦股份前十大股东` |

## 4. 三个 search channel

### news — 财经资讯搜索

财经领域为主的资讯搜索引擎，覆盖官媒、主流财经媒体、垂直行业网站、知名上市公司/非上市公司官网，适合了解最新财经事件、政策动态、行业革新、企业业务进展。

示例 query：`人工智能`、`最近人工智能行业有什么新政策`、`特斯拉最近的业务进展`

### report — 研报搜索

收录主流投研机构发布的研究报告，适合获取专业、深度的分析逻辑、投资评级、目标价等投研决策信息。

示例 query：`人工智能行业研究报告`、`芯片行业`、`新能源汽车`

### announcement — 公告搜索

支持 A 股、港股、基金、ETF 等金融标的公告查询，公告类型包括不限于定期财务报告、分红派息、回购增持、资产重组等。

示例 query：`贵州茅台分红公告`、`回购增持公告`、`资产重组最新公告`

## 5. 分页 playbook

`iwencai_query` 成功响应包含 `code_count`（符合条件的总条数）、`returned_count`（本次返回条数）、`page`、`limit`、`has_more`。

- `has_more = code_count > page * limit`。
- `has_more` 为 `true` 时响应附带 `pagination_tip`，提示使用 `page` 参数翻页获取更多数据。
- 默认每页 10 条；需要更多数据时用 `page=2, 3, ...` 翻页，或调大 `limit`。

## 6. 空数据重试 playbook

`datas` / `data` 为空时 `status` 仍为 `ok`，响应附带 `empty_data_tip`：

1. 放宽或简化查询条件后重试，**最多重试 2 次**。重试时请将工具的 `is_retry` 参数置为 `true`，服务端会以 `X-Claw-Call-Type: retry` 标记该请求，让网关把它识别为重试而非全新查询。
2. 逐步放宽：先去掉最严格的条件（如精确数值阈值），再简化复合条件为单一条件。
3. transport 层的自动重试（timeout / network / provider_5xx，受 `AGENTEUM_FIN_RETRY_ATTEMPTS` 控制）在第 2 次及以后的尝试也会自动以 `retry` call-type 标记，无需 agent 干预。
4. 仍无数据时，引导用户访问同花顺问财官网：https://www.iwencai.com/unifiedwap/chat

## 7. 来源标注义务

两个工具的所有数据均来源于**同花顺问财**（https://www.iwencai.com/unifiedwap/chat）。每条响应（含错误响应）都带 `"source": "同花顺问财"` 字段；基于这些数据回答用户时必须标注数据来源为同花顺问财。

## 8. 错误处理

所有错误响应（HTTP 层与网关业务层）统一为同一信封形状：`status` / `source` / `error`（`type` / `message` / `provider` / `retryable`）/ `fallbacks`；网关业务错误额外携带 `gateway_response` 透传字段。消费端可按统一形状解析。

- **config_error（缺少 API 密钥）**：首次使用需配置密钥。打开 https://www.iwencai.com/skillhub → 登录 → 点击 Skill → 安装方式-Agent用户 → 复制 `IWENCAI_API_KEY`，然后设置环境变量 `AGENTEUM_FIN_IWENCAI_API_KEY`（或技能生态惯例的 `IWENCAI_API_KEY`），重启服务。
- **provider_unavailable**：`AGENTEUM_FIN_IWENCAI_PROVIDER=none` 时工具被禁用，返回此错误。
- **网关业务错误（额度不足、次数超限等）**：HTTP 200 但不含 `datas` 的网关响应会**原样透传**在 `gateway_response` 字段中（仅对密钥命名字段做脱敏掩码，不改写数据结构），`fallbacks` 为 `[]`。`error.type` 为 `quota_exhausted` / `rate_limited` / `provider_error`。
- **retryable 策略**：`rate_limited`（限流）标记为 `retryable=true`，可退避后重试；`quota_exhausted`（额度/次数类）与 `provider_error` 标记为 `retryable=false`，重试无意义。
- **HTTP 层错误（timeout / network / provider_5xx）**：同样的信封形状（带 `source: "同花顺问财"`），可被服务端重试策略自动重试（`AGENTEUM_FIN_RETRY_ATTEMPTS`），第 2 次及以后的尝试自动以 `retry` call-type 标记。
