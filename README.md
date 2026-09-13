# Adversiting

自动同步并转换 **晴雅广告拦截规则**，输出 Loon、Surge、Quantumult X、Mihomo（Clash.Meta）、sing-box、Xray 六种客户端格式。

上游：`https://raw.githubusercontent.com/rssvcn/qy-Ads-Rule/main/black.txt`

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

## 兼容性说明

`Clash.yaml` 以现代 **Mihomo / Clash.Meta** 为目标，不再兼容旧 Dreamacro Clash 内核，因此可使用 `DOMAIN-WILDCARD`、`DST-PORT` 与逻辑规则完整表达当前上游可移植规则。

Loon 原生没有域名级 wildcard/regex 类型：普通域名与端口条件使用原生规则精确转换；复杂 wildcard 额外使用 `URL-REGEX` 补偿 HTTP/HTTPS 请求，但这部分不等同于域名层 100% 语义覆盖。

## 自动更新

`.github/workflows/sync-rules.yml` 每天检查一次上游，并 checkout `rules-sync` 分支运行转换器。仅当上游内容或转换器代码发生变化时才提交更新，避免无意义的每日 commit。

格式依据各项目官方示例/文档实现；无法安全等价转换的 ABP 路径、modifier 等特殊规则保存在 `rules-sync/rules/unsupported.txt`，不会擅自扩大成整域名拦截。

更多转换细节、官方格式参考和兼容性说明请查看 `rules-sync` 分支的 README。
