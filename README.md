# Adversiting

自动同步、合并并转换两个广告拦截上游，输出 Loon、Surge、Quantumult X、Mihomo（Clash.Meta）、sing-box、Xray 六种客户端格式。

上游：

- `https://raw.githubusercontent.com/rssvcn/qy-Ads-Rule/main/black.txt`
- `https://adaway.org/hosts.txt`

实际规则维护在 [`rules-sync`](https://github.com/Velaro14/Adversiting/tree/rules-sync) 分支；默认分支 `main` 保留 GitHub Actions 定时任务，因为 scheduled workflow 由默认分支读取。

## 订阅地址

| 客户端 | Raw URL |
|---|---|
| Loon | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Loon.list` |
| Surge | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Surge.list` |
| Quantumult X | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/QuanX.list` |
| Mihomo / Clash.Meta | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Clash.yaml` |
| sing-box | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/SingBox.json` |
| Xray | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Xray.json` |

## 转换语义

- 晴雅普通 `||domain^` 保持根域+子域后缀语义。
- `||*.domain^` 保持 wildcard，不再错误降级成包含根域的 `DOMAIN-SUFFIX`。
- AdAway hosts 保持**精确主机名**，不会扩大成域名后缀。
- 复杂 ABP wildcard 做 hostname projection：Mihomo 使用 `DOMAIN-REGEX`，sing-box/Xray 使用正则；Surge/QuanX 用原生 wildcard 并补足 `||` 的子域标签边界。
- Loon 没有域名级 wildcard/regex，22 条 wildcard 使用 HTTP(S) `URL-REGEX` 补偿，不宣称为所有协议上的完整等价。
- QuanX 暂不输出那 1 条“域名 + 目标端口”规则，避免将其扩大为整个域名拦截。
- 依赖 URL 路径/query/app modifier 的规则放入 `rules/unsupported.txt`，不做猜测式扩大。

当前审计后的详细规则数量、语义说明和客户端差异见 `rules-sync/metadata.json` 与 `rules-sync/README.md`。

## 自动更新与校验

`.github/workflows/sync-rules.yml` 每天约 **03:17（UTC+8）** checkout `rules-sync`，依次执行回归测试、双上游下载、完整性检查、转换和生成结果结构校验。转换器每次都会重新生成输出，因此生成文件若被误改/误删，下次运行可以自动修复；只有工作树真正变化时才会提交。

任一上游下载失败、规则数量异常或输出校验失败时，本次任务直接失败，不会用空集或残缺结果覆盖上一版有效规则。
