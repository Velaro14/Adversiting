# Adversiting

自动同步并合并两个广告拦截上游，转换为多客户端原生规则格式：

- 晴雅广告拦截规则：`https://raw.githubusercontent.com/rssvcn/qy-Ads-Rule/main/black.txt`
- AdAway default blocklist：`https://adaway.org/hosts.txt`

## 输出

| 客户端 | 文件 | Raw URL |
|---|---|---|
| Loon | `rules/Loon.list` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Loon.list` |
| Surge | `rules/Surge.list` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Surge.list` |
| Quantumult X | `rules/QuanX.list` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/QuanX.list` |
| Mihomo / Clash.Meta | `rules/Clash.yaml` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Clash.yaml` |
| sing-box | `rules/SingBox.json` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/SingBox.json` |
| Xray | `rules/Xray.json` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Xray.json` |

原始上游分别保存为 `upstream/black.txt` 与 `upstream/adaway-hosts.txt`。`metadata.json` 记录两个上游各自 SHA256、解析数量、去重数量、同步时间与各客户端覆盖统计。

## 转换原则

- 晴雅 `||example.com^` 保持域名后缀语义：Loon/Surge/Mihomo 使用 `DOMAIN-SUFFIX`，QuanX 使用 `host-suffix`，sing-box 使用 `domain_suffix`，Xray 使用 `domain:`。
- AdAway hosts 条目（例如 `127.0.0.1 ads.example.com`）保持**精确主机名**语义，不扩大成后缀：Loon/Surge/Mihomo 使用 `DOMAIN`，QuanX 使用 `host`，sing-box 使用 `domain`，Xray 使用 `full:`。
- AdAway 中被晴雅后缀规则已经覆盖的精确域名会去重，避免重复输出。
- Mihomo / Clash.Meta 使用现代 `DOMAIN-WILDCARD`、`DST-PORT` 与逻辑规则，不兼容旧 Dreamacro Clash。
- Loon 没有域名级 wildcard/regex；复杂 wildcard 用 `URL-REGEX` 补偿 HTTP/HTTPS，请勿视为完整域名层等价。
- 带 URL 路径或 ABP modifier（例如 `$app=`）的晴雅规则不会被粗暴扩大成整域名拦截，而是保存在 `rules/unsupported.txt`。
- 两个上游必须都成功下载后才会生成新结果；任一下载失败，本次同步失败并保留上一次有效规则。

## 当前格式参考

- Loon：`https://github.com/Loon0x00/LoonManual`
- Surge：`https://manual.nssurge.com/rules/ruleset.html`
- Quantumult X：`https://github.com/crossutility/Quantumult-X`
- Mihomo：`https://wiki.metacubex.one/config/rules/`
- sing-box：`https://sing-box.sagernet.org/configuration/rule-set/source-format/`
- Xray：`https://xtls.github.io/config/routing.html`

## 自动同步

默认分支 `main` 中的 GitHub Actions workflow 每天约在 **03:17（UTC+8）** 检查两个上游。工作流 checkout `rules-sync`，执行 `scripts/convert_rules.py`，仅当任一上游或转换器发生变化时提交更新。

AdAway 上游文件声明为 CC Attribution 3.0；相关来源与项目归属保留在上游文件及本 README 中。

Xray 输出默认使用 `outboundTag: "block"`，主配置需要存在同名 blackhole outbound；若标签不同，请自行替换。
