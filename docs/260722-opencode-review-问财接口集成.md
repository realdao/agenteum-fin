# iwencai 集成代码审查报告

## 发现列表（按严重程度排序）

### Blocker
未发现。改动可编译、`ruff check` 通过、live smoke 14/14 已跑通，无阻断性缺陷。

### Major

**[major] src/services/iwencai_service.py:31,55 + src/api/mcp_full.py:218,268 - `call_type="retry"` 在生产路径中不可达，与 guide §6 文档矛盾 -** guide §6（`iwencai-query-guide.md`）与 `_empty_data_tip`（service.py:182-183）均承诺"重试请求由服务端自动使用 retry call-type 标记（X-Claw-Call-Type: retry）"。但 `IwencaiService.query/search` 的 `call_type` 参数仅默认 `"normal"`，唯一生产调用方 MCP 工具（mcp_full.py:218/268）从不传 `call_type`；`run_with_retries` 重试时复用同一 `call_type`（始终 normal）。因此 `call_type="retry"` 是死代码，仅单测可达。空数据重试由 agent 再次调用工具触发，服务端无法识别为 retry，网关会把重试当作全新查询计费/计次。建议：要么让 `run_with_retries` 的第 2+ 次尝试自动传 `call_type="retry"`，要么在 MCP 层为空数据重试暴露标记机制；并同步修正 guide §6 与 `_empty_data_tip` 措辞使之与实现一致。

**[major] src/api/mcp_full.py:219-220,269-270,211-215,261-265 + src/schemas.py:34-37 - HTTP 层错误响应缺失 `source: "同花顺问财"`，违反"每条响应（含错误）必须带 source"硬要求 -** timeout/network/5xx/auth/4xx/config_error/provider_unavailable 全部经共享 `_provider_error_response`/`_provider_unavailable_response` 返回 `ToolErrorResponse`，而 `ToolErrorResponse`（schemas.py:34-37）只有 `status/error/fallbacks`，无 `source`。对照网关业务错误信封（service.py:80,150 经 `base` 带 source）成功响应（service.py:80）均带 source，唯独 HTTP 错误路径丢source。建议：iwencai 的 HTTP 错误改走带 `source` 的信封，或在 `_provider_error_response` 之外为 iwencai 包一层注入 `source`。

**[major] src/services/iwencai_service.py:48,71 - 网关业务错误（含 quota_exhausted）被记为 `status="ok"`，在可观测性中被淹没 -** `_log(..., status="ok")` 仅在抛 `ProviderError` 时记 error（46/69）。网关 200-但无-datas 的业务错误不抛异常、直接走 `_query_envelope`→`_gateway_error_envelope` 返回 `status:"error"` 信封，但日志记 `status="ok"` 且无 `error_type`。这与"网关业务错误不淹没"的精神相悖，监控按 `status=error` 告警会漏掉额度耗尽/限流。建议：在构造完信封后按 `envelope["status"]` 决定日志 status，或在 `_gateway_error_envelope` 路径补记一次 warning 日志含 `error_type`。

**[major] src/services/iwencai_service.py:148-158 vs src/api/mcp_full.py:280-302 - 同一工具的两条错误路径产生两种不兼容信封形状 -** 网关错误信封 = `{status, source, query, domain/channel, trace_id, error, gateway_response}`（无 `fallbacks`）；HTTP 错误 = `ToolErrorResponse` `{status, error, fallbacks}`（无 `source/query/trace_id/gateway_response`）。消费端 `result["fallbacks"]` 在网关错误上会 KeyError，`result["source"]` 在 HTTP 错误上会 KeyError。建议统一一种错误信封（推荐网关错误也补 `fallbacks:[]`，HTTP 错误也补 `source`）。

### Minor

**[minor] src/services/iwencai_service.py:18,201 - 网关错误关键词归类存在重叠误判 -** `_QUOTA_KEYWORDS` 含"超限"，且先于 `_RATE_LIMIT_KEYWORDS` 判定。限流类消息如"请求频率超限"含"超限"会被判为 `quota_exhausted` 而非 `rate_limited`；"请求次数过多"（中文）命中"次数"→quota，而英文"too many requests"命中"too many"→rate_limited，同类错误因语言归类不一致。建议：把"超限"移出 quota 或在 quota 判定中排除同时含"频率/限流"的文本，并补相应单测。

**[minor] src/providers/iwencai/client.py:158,166,174 + src/errors.py:55-67 - `redact_payload(response.text)` 对字符串仅截断、不脱敏，命名具误导性 -** `redact_payload` 的 `str` 分支只做 500 字符截断，不会扫描/抹除字符串内嵌的 API key 值。若 4xx/5xx 响应体（字符串形态）回显了 `Authorization: Bearer <key>`，截断后 key 仍在。当前因 `payload` 不进响应信封、网关一般不回显 header，实际风险低，但与"redact"语义不符。建议对字符串输入也按 key 值做掩码，或改传解析后的 dict 再 redact。

**[minor] src/services/iwencai_service.py:157,136 - `gateway_response`/`raw_response` 透传字段未过 `redact_payload` -** 任务书明确提示关注该字段。当前 200 业务错误体与 search 成功体原样透传，若网关返回体含 `token`/`authorization` 等 SECRET_KEYS 命名字段会泄漏。受"原样透传不改写"设计约束，不建议改写数据，但建议在文档/注释中声明契约保证不回显密钥，或对透传体做一次 `redact_payload`（dict 分支仅掩密钥名，不破坏数据结构）。

**[minor] src/services/iwencai_service.py:91-109,130-140 - 成功信封为裸 dict，偏离 `BaseToolResponse` 约定 -** 既有 stock_* 工具返回 `BaseToolResponse`（含 `provider/provider_status/fetched_at/fallbacks`），iwencai 成功信封用 `source` 代替 `provider`、无 `fetched_at/provider_status/fallbacks`，且非 pydantic 模型。作为"灵活查询层"可接受，但应在 guide/README 显式声明该信封为独立约定，避免消费端按统一模型解析。

**[minor] src/errors.py:31-37 + src/services/iwencai_service.py:155 - `RATE_LIMITED` 被标为不可重试 -** `RATE_LIMITED` 不在 `RECOVERABLE_ERRORS`，故 `retryable=false`。限流类错误通常应可退避重试；guide §8 仅明确"额度与次数类错误 retryable=false"，限流是否同样不可重试存疑。建议确认意图，若需可重试则加入 `RECOVERABLE_ERRORS`。

### Nit

**[nit] src/api/mcp_full.py:293 - `def _provider_error_response(...) -> ToolErrorResponse:    return ToolErrorResponse(` 把 `return` 压在 `def` 同一行 -** 系手工编辑残留（同胞函数 `_provider_unavailable_response` 是分行写法）。语法合法、ruff 通过，但可读性差。建议把 `return` 移到下一行。

**[nit] src/providers/iwencai/client.py:77,99 - `DOMAIN_SKILL_IDS[domain]`/`CHANNEL_SKILL_IDS[channel]` 对非法值抛裸 `KeyError` -** MCP 经 schema 校验不可达，但 client 直调会得到不清晰错误。建议映射为 `ProviderError(INVALID_REQUEST)`。

**[nit] src/providers/iwencai/client.py:105 - search 的 `size` 以 int 发送，而 query 的 `page/limit` 以 str 发送 -** 符合两端点契约（live 已验证），但建议加注释说明非对称是有意为之。

**[nit] src/provider_factory.py `_iwencai_service` - 缺返回类型注解（返回 `IwencaiService | None`）-** 补 `-> IwencaiService | None`。

**[nit] src/services/iwencai_service.py:124 - `json_list` 时 `raw_response` 为合成 `{"data": [...]}` 而非真实原始体 -** 字段名 `raw_response` 略具误导，建议改名或注释。

**[nit] src/services/iwencai_service.py:89 - `code_count` 缺失时回退 `len(datas)`，使 `has_more` 几乎恒 False -** 依赖网关必返 `code_count`，契约脆弱，建议注释标注。

## 测试质量

- 覆盖较好：header 构造、domain/channel→skill-id 映射、payload 形态、HTTP 错误分类、分页 `has_more`、空数据、网关错误透传、retry 策略、config_error、provider_unavailable 均有覆盖。
- 遗漏：
  - 无用例断言 HTTP 错误响应是否含/缺 `source`——前述 major 不被测试捕获。
  - 无用例经 MCP 验证 `call_type="retry"`（因不可达），恰印证死代码问题。
  - `test_mcp_iwencai_query_config_error_when_api_key_missing` 未断言调用次数/CONFIG_ERROR 不被重试，回归到"重试 CONFIG_ERROR"不会被捕获（隐式依赖默认 `RetryPolicy(attempts=1)`）。
  - 关键词归类边界（如"请求频率超限"误判、`rate_limited`/`provider_error` fallback 分类）无单测；`_gateway_message` 多候选 key 仅测 `message`。
  - search 缺少 missing-key（config_error）路径用例（仅 query 测了）。
  - live smoke 用 `has_more == (code_count > page*limit)` 自洽重推，未跨页验证真实分页行为。
  - fixture `iwencai_search_news.json` 假设 `{"data":[...]}` 形态，未覆盖裸 list 形态的 fixture（仅合成测试覆盖）。

## 文档准确性

- README 参数名/默认值/11 domain/3 channel/禁用开关、resource URI、`.env.example` 回退说明均与实现一致。
- **不一致**：guide §6 与 `_empty_data_tip` 关于"服务端自动 retry call-type"的描述与实现不符（见首条 major）。
- guide §8 未说明网关错误信封与 HTTP 错误信封形状不同（含/缺 `fallbacks`、`source`），易误导消费端。

## 安全（API key 泄漏专项）

- API key 直接泄漏进日志/异常消息/响应 payload：**未发现**。`_log` 不记 header/payload；HTTP 错误 message 仅含状态码；`Authorization` 仅在请求 header，不进响应体。
- 残留风险见前述 minor：`redact_payload` 对字符串仅截断、`gateway_response`/`raw_response` 未脱敏——均为低概率边界，建议加固。

## 总体结论

**需修改后合并。** 功能契约（14 技能映射、header、payload、分页、网关错误透传）实现正确且 live 验证通过；但存在 3 项 major：`call_type="retry"` 死代码与文档矛盾、HTTP 错误缺 `source` 违反硬要求、网关业务错误日志被淹没为 ok——建议至少处理 source 一致性与 call_type 文档/实现对齐后再合并，其余 minor/nit 可后续跟进。

---

