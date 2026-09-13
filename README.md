# Adversiting

将上游 **晴雅广告拦截规则** 自动转换为多客户端原生规则格式。

上游：`https://raw.githubusercontent.com/rssvcn/qy-Ads-Rule/main/black.txt`

## 输出

| 客户端 | 文件 | Raw URL |
|---|---|---|
| Loon | `rules/Loon.list` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Loon.list` |
| Surge | `rules/Surge.list` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Surge.list` |
| Quantumult X | `rules/QuanX.list` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/QuanX.list` |
| Clash | `rules/Clash.yaml` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Clash.yaml` |
| sing-box | `rules/SingBox.json` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/SingBox.json` |
| Xray | `rules/Xray.json` | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Xray.json` |

`upstream/black.txt` 保存最近一次同步的原始规则；`metadata.json` 保存上游版本、SHA256、同步时间和转换统计；`rules/unsupported.txt` 保存无法在所有目标客户端中安全等价转换的 ABP 特殊规则。

## 转换原则

- `||example.com^` → 域名后缀匹配，例如 Loon/Surge 的 `DOMAIN-SUFFIX,example.com`、QuanX 的 `host-suffix, example.com, reject`、Xray 的 `domain:example.com`。
- `||*.example.com^` 会归一化为域名后缀规则。
- 可安全表达的通配域名使用 Surge `DOMAIN-WILDCARD`、QuanX `host-wildcard`、sing-box `domain_regex`、Xray `regexp:`。
- Clash 使用官方 classical rule-provider 形式；原版 Clash 无法安全等价表示的复杂通配规则不会被扩大成整站拦截。
- 端口限定规则仅在能够同时表达域名与端口条件的格式中生成；其他客户端会记录到兼容性说明中，不做危险的扩大匹配。
- 带 URL 路径或 ABP modifier（如 `$app=`）的规则不会被粗暴转换成整域名拦截，避免误杀。

## 官方格式参考

- Loon：`https://github.com/Loon0x00/LoonExampleConfig/blob/master/Rule/ExampleRule.list`
- Surge：`https://manual.nssurge.com/rules/ruleset.html`
- Quantumult X：`https://github.com/crossutility/Quantumult-X/blob/master/filter.snippet`
- Clash：`https://github.com/Dreamacro/clash/wiki/Clash-Premium-Features#rule-providers`
- sing-box：`https://sing-box.sagernet.org/configuration/rule-set/source-format/`
- Xray：`https://xtls.github.io/config/routing.html`

## 自动同步

默认分支 `main` 中的 GitHub Actions workflow 每天检查一次上游。工作流会 checkout `rules-sync` 分支，执行 `scripts/convert_rules.py`，只有当**上游内容或转换脚本发生变化**时才重新生成并提交规则，因此不会每天制造无意义提交。

Xray 输出默认使用 `outboundTag: "block"`，你的 Xray 主配置中需要存在同名的 blackhole outbound；若你的标签不同，请自行替换该字段。
