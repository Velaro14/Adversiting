# Adversiting

自动同步并转换 **晴雅广告拦截规则**，输出 Loon、Surge、Quantumult X、Clash、sing-box、Xray 六种客户端格式。

上游：`https://raw.githubusercontent.com/rssvcn/qy-Ads-Rule/main/black.txt`

实际规则维护在 [`rules-sync`](https://github.com/Velaro14/Adversiting/tree/rules-sync) 分支；本分支保留 GitHub Actions 定时任务，因为 GitHub 的 scheduled workflow 只从默认分支执行。

## 订阅地址

| 客户端 | Raw URL |
|---|---|
| Loon | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Loon.list` |
| Surge | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Surge.list` |
| Quantumult X | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/QuanX.list` |
| Clash | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Clash.yaml` |
| sing-box | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/SingBox.json` |
| Xray | `https://raw.githubusercontent.com/Velaro14/Adversiting/rules-sync/rules/Xray.json` |

## 自动更新

`.github/workflows/sync-rules.yml` 每天检查一次上游，并 checkout `rules-sync` 分支运行转换器。仅当上游内容或转换器代码发生变化时才提交更新，避免无意义的每日 commit。

格式依据各项目官方示例/文档实现；无法安全等价转换的 ABP 路径、modifier 等特殊规则保存在 `rules-sync/rules/unsupported.txt`，不会擅自扩大成整域名拦截。

更多转换细节、官方格式参考和兼容性说明请查看 `rules-sync` 分支的 README。
