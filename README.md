# Adversiting

自动同步、合并并转换两个广告拦截上游，输出 Loon、Surge、Quantumult X、Mihomo（Clash.Meta）、sing-box、Xray 六种客户端格式。

上游：

- `https://raw.githubusercontent.com/rssvcn/qy-Ads-Rule/main/black.txt`
- `https://adaway.org/hosts.txt`

实际规则维护在 [`rules-sync`](https://github.com/Velaro14/Adversiting/tree/rules-sync) 分支；本分支保留 GitHub Actions 定时任务，因为 GitHub 的 scheduled workflow 只从默认分支执行。

## 订阅地址

| 客户端 | Raw URL |
|---|---|
| Loon | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Loon.list` |
| Surge | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Surge.list` |
| Quantumult X | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/QuanX.list` |
| Mihomo / Clash.Meta | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Clash.yaml` |
| sing-box | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/SingBox.json` |
| Xray | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Xray.json` |

## 合并规则

晴雅的 ABP 域名规则保持后缀/通配语义；AdAway hosts 文件中的域名保持**精确主机名**语义，不会擅自转换成 `DOMAIN-SUFFIX`。两边重复或已被晴雅后缀规则覆盖的 AdAway 精确域名会自动去重。

`Clash.yaml` 只针对现代 **Mihomo / Clash.Meta**，可使用 `DOMAIN-WILDCARD`、`DST-PORT` 与逻辑规则。Loon 的复杂 wildcard 使用 `URL-REGEX` 做 HTTP/HTTPS 补偿，因为 Loon 没有域名级 wildcard/regex 类型。

## 自动更新

`.github/workflows/sync-rules.yml` 每天约 **03:17（UTC+8）** 同时检查两个上游，并 checkout `rules-sync` 分支运行转换器。只有任一上游或转换器发生变化时才提交更新；如果任一上游下载失败，本次同步直接失败并保留上一版有效规则。

无法安全等价转换的晴雅 ABP 路径、modifier 等特殊规则保存在 `rules-sync/rules/unsupported.txt`，不会擅自扩大成整域名拦截。更多转换细节和覆盖统计见 `rules-sync/README.md` 与 `rules-sync/metadata.json`。
