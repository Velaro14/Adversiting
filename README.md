# Adversiting

自动同步并合并两个广告拦截上游，转换为 Loon、Surge、Quantumult X、Mihomo（Clash.Meta）、sing-box、Xray 六种客户端格式。

上游：

- 晴雅广告拦截规则：`https://raw.githubusercontent.com/rssvcn/qy-Ads-Rule/main/black.txt`
- AdAway default blocklist：`https://adaway.org/hosts.txt`

原始上游分别保存在 `upstream/black.txt` 与 `upstream/adaway-hosts.txt`；`metadata.json` 保存两个上游的 SHA256、解析数量、去重数量、同步时间与覆盖统计。

## 输出

| 客户端 | 文件 | Raw URL |
|---|---|---|
| Loon | `rules/Loon.list` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Loon.list` |
| Surge | `rules/Surge.list` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Surge.list` |
| Quantumult X | `rules/QuanX.list` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/QuanX.list` |
| Mihomo / Clash.Meta | `rules/Clash.yaml` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Clash.yaml` |
| sing-box | `rules/SingBox.json` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/SingBox.json` |
| Xray | `rules/Xray.json` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Xray.json` |

## 语义转换原则

- 晴雅 `||example.com^` 保持“根域 + 子域”语义：Loon/Surge/Mihomo 使用 `DOMAIN-SUFFIX`，QuanX 使用 `host-suffix`，sing-box 使用 `domain_suffix`，Xray 使用 `domain:`。
- `||*.example.com^` **不会**降级成 `DOMAIN-SUFFIX,example.com`，因为那样会额外匹配根域 `example.com`。这类规则保持 wildcard/regex 语义。
- AdAway hosts 条目（例如 `127.0.0.1 ads.example.com`）保持**精确主机名**语义，不扩大成后缀：Loon/Surge/Mihomo 使用 `DOMAIN`，QuanX 使用 `host`，sing-box 使用 `domain`，Xray 使用 `full:`。
- AdAway 中已被晴雅普通后缀规则覆盖的精确域名会去重；只有确定被后缀规则完整覆盖时才删除重复项。
- 晴雅复杂 wildcard 的转换以 **hostname projection** 为目标：保留 ABP `||` 可从任意域名标签边界开始匹配的行为。
  - Mihomo：`DOMAIN-REGEX`
  - sing-box：`domain_regex`
  - Xray：`regexp:`
  - Surge / QuanX：使用原生 wildcard；固定前缀模式会同时生成基础形式和 `*.` 子域形式，避免漏掉更深层子域。
  - Loon：没有域名级 wildcard/regex 类型，只能用 `URL-REGEX` 对 HTTP/HTTPS 做补偿，因此不能视为 TCP/UDP 等所有协议上的完整等价。
- 晴雅 `||ad.wx.com:12638^` 这类“域名 + 端口”规则在 Loon、Surge、Mihomo、sing-box、Xray 中保持 AND 条件；QuanX 没有使用未被官方示例/文档明确支持的域名+目标端口 AND 写法，因此这 1 条不做危险扩大。
- 带 URL 路径、query 或 ABP modifier（例如 `$app=`）的规则不会被粗暴扩大为整域名拦截，统一保存在 `rules/unsupported.txt`。

### 关于 ABP wildcard 的边界

ABP 的 `*` 从形式上可以继续匹配 URL 的其他部分，而大部分代理客户端的路由规则只能看到 hostname / port。因此这里对 wildcard 做的是**尽可能等价的 hostname 投影**，不是声称所有客户端都能 100% 重现 ABP 的完整 URL 层语义。当前上游中明确依赖 URL 路径或 app modifier 的规则会直接进入 `unsupported.txt`，而不是猜测转换。

## 当前审计结果

当前版本经过语义审计后，`metadata.json` 中的合并结果为：

- AdAway：6540 个精确域名；其中 50 个被晴雅普通后缀规则完整覆盖，合并后保留 6490 个精确域名。
- 晴雅：545 条普通域名后缀、1 条域名关键词、22 条 wildcard、1 条域名+端口、3 条不可安全统一转换的 URL/app 特殊规则。
- 合并后可做 hostname/port 投影的逻辑规则共 7059 条。
- Surge / Mihomo / sing-box / Xray：7059 条 hostname/port 逻辑均有对应表达。
- QuanX：7058 条，缺少 1 条域名+目标端口 AND。
- Loon：7037 条为原生 hostname/port 表达；22 条 wildcard 用 HTTP(S) `URL-REGEX` 补偿。

## 自动校验与故障保护

每次 GitHub Actions 同步都会按以下顺序执行：

1. 运行 `scripts/test_converter.py` 的回归测试，覆盖 `*.` 根域边界、ABP `||` 子域边界、`?` 误判、路径/modifier、不扩大 AdAway、后缀去重等关键语义。
2. 同时抓取两个上游；网络失败会自动有限重试。
3. 对上游做完整性检查：晴雅标题与最低规则数量、AdAway 最低有效域名数量均必须通过，否则直接失败，不会提交空集/残缺规则。
4. 每次都重新生成全部输出，因此即使某个生成文件被误改或误删，也能在下一次运行自动恢复。
5. 对生成结果进行 JSON/结构/数量校验。
6. 只有工作树真正产生差异时才提交；没有变化不会制造空 commit。

## 格式参考

- Loon：`https://github.com/Loon0x00/LoonManual`
- Surge：`https://manual.nssurge.com/rules/ruleset.html`
- Quantumult X：`https://github.com/crossutility/Quantumult-X`
- Mihomo：`https://wiki.metacubex.one/config/rules/`
- sing-box：`https://sing-box.sagernet.org/configuration/rule-set/source-format/`
- Xray：`https://xtls.github.io/config/routing.html`

## 自动同步

默认分支 `main` 的 `.github/workflows/sync-rules.yml` 每天约 **03:17（UTC+8）** 运行，checkout `rules-sync` 后先测试、再同步、转换、验证和按需提交。两个上游必须都通过下载与完整性校验才会生成可提交结果。

AdAway 上游文件声明为 CC Attribution 3.0；相关来源与项目归属保留在上游文件和本 README 中。

Xray 输出默认使用 `outboundTag: "block"`，主配置需要存在同名 blackhole outbound；若你的标签不同，请自行替换。
