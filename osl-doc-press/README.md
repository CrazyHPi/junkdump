# osl-doc-press

OSL（Minecraft 1.12.2）API 参考文档的 VitePress 站点。内容来自 `../_osl_doc/` 的各章分册（22 个模块章 + 2 个附录）。

## 目录结构

```
osl-doc-press/
├─ docs/
│  ├─ index.md                     首页
│  ├─ guide/intro.md               介绍与总览（模块表、依赖层次、引入方式）
│  ├─ modules/<module>.md          22 个模块章（core … text-components）
│  ├─ appendix/notes.md            附录 A　注意事项与已知缺陷
│  ├─ appendix/types.md            附录 B　公开类型索引（按包）
│  └─ .vitepress/
│     ├─ config.mts                站点配置（导航、侧边栏、本地搜索）
│     └─ theme/                    默认主题 + 少量样式调整
├─ serve.mjs                       零依赖静态服务器（预览 dist）
└─ package.json
```

## 常用命令

```bash
npm install --cache ./.npm-cache --ignore-scripts   # 首次安装（缓存放项目内）
npm run dev                                         # 开发服务器 http://localhost:5173
npm run build                                       # 构建到 docs/.vitepress/dist
npm run preview                                     # 官方预览（需要能启动 esbuild）
npm run preview:dist                                # 零依赖预览已构建的 dist（http://127.0.0.1:5178）
```

> **关于受限环境**：VitePress 的构建/预览链路依赖 esbuild，esbuild 需要 `spawn` 子进程并通过管道通信。在禁止管道 stdio 的沙箱里 `npm run dev` / `npm run build` 会报 `spawn EPERM`，请在普通终端（沙箱外）执行；`npm run preview:dist` 只用 Node 内置模块，不受影响。

## 部署

1. `npm run build` 生成静态站点。
2. 把 `docs/.vitepress/dist/` 整个目录上传到静态主机（GitHub Pages / Nginx / Cloudflare Pages 均可）。
3. 若部署在子路径（如 `https://example.com/osl-doc/`），把 `docs/.vitepress/config.mts` 里的 `base` 改成 `'/osl-doc/'` 后重新构建。

## 内容维护

正文源文件在 `../_osl_doc/`，改完后重新同步：

```bash
# 例：把某一章同步到站点
cp ../_osl_doc/08-commands.md docs/modules/commands.md
```

同步时需要保留/补上每页开头的 frontmatter（`---\ntitle: …\n---`），否则浏览器标签标题会取正文 H1。
