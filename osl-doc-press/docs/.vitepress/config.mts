import { defineConfig } from 'vitepress'

// 部署到子路径（如 GitHub Pages 的 /osl-doc/）时改成 '/osl-doc/'，并保持末尾斜杠
const base = '/'

export default defineConfig({
  base,
  lang: 'zh-CN',
  title: 'OSL API 参考',
  description: 'Ornithe Standard Libraries — Minecraft 1.12.2 的模块与 API 手册',

  cleanUrls: true,
  lastUpdated: false,
  head: [
    ['meta', { name: 'theme-color', content: '#3c8772' }],
    ['meta', { name: 'viewport', content: 'width=device-width,initial-scale=1' }]
  ],

  markdown: {
    theme: { light: 'github-light', dark: 'github-dark' },
    lineNumbers: false
  },

  themeConfig: {
    outline: { level: [2, 3], label: '本页目录' },
    nav: [
      { text: '指南', link: '/guide/intro' },
      { text: '模块', link: '/modules/core', activeMatch: '^/modules/' },
      { text: '附录', link: '/appendix/notes', activeMatch: '^/appendix/' },
      { text: '变更历史', link: '/changelog', activeMatch: '^/changelog' }
    ],
    sidebar: [
      {
        text: '开始',
        items: [
          { text: '介绍与总览', link: '/guide/intro' }
        ]
      },
      {
        text: '模块参考',
        collapsed: false,
        items: [
        { text: '01 core', link: '/modules/core' },
        { text: '02 biomes', link: '/modules/biomes' },
        { text: '03 blocks', link: '/modules/blocks' },
        { text: '04 blockstates', link: '/modules/blockstates' },
        { text: '05 blockentities', link: '/modules/blockentities' },
        { text: '06 blockentities-rendering', link: '/modules/blockentities-rendering' },
        { text: '07 branding', link: '/modules/branding' },
        { text: '08 commands', link: '/modules/commands' },
        { text: '09 config', link: '/modules/config' },
        { text: '10 crash-reports', link: '/modules/crash-reports' },
        { text: '11 entities', link: '/modules/entities' },
        { text: '12 entities-rendering', link: '/modules/entities-rendering' },
        { text: '13 entrypoints', link: '/modules/entrypoints' },
        { text: '14 executors', link: '/modules/executors' },
        { text: '15 items', link: '/modules/items' },
        { text: '16 keybinds', link: '/modules/keybinds' },
        { text: '17 lifecycle-events', link: '/modules/lifecycle-events' },
        { text: '18 localization', link: '/modules/localization' },
        { text: '19 networking', link: '/modules/networking' },
        { text: '20 registries', link: '/modules/registries' },
        { text: '21 resource-loader', link: '/modules/resource-loader' },
        { text: '22 text-components', link: '/modules/text-components' }
        ]
      },
      {
        text: '附录',
        items: [
          { text: '附录 A　注意事项与已知缺陷', link: '/appendix/notes' },
          { text: '附录 B　公开类型索引', link: '/appendix/types' }
        ]
      },
      {
        text: '项目',
        items: [
          { text: '变更历史', link: '/changelog' }
        ]
      }
    ],
    search: {
      provider: 'local',
      options: {
        translations: {
          button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' },
          modal: {
            noResultsText: '没有找到结果',
            resetButtonTitle: '清除',
            footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' }
          }
        }
      }
    },
    docFooter: { prev: '上一章', next: '下一章' },
    darkModeSwitchLabel: '主题',
    sidebarMenuLabel: '目录',
    returnToTopLabel: '回到顶部',
    langMenuLabel: '语言',
    footer: {
      message: '基于 Ornithe Standard Libraries 0.24.0（MC 1.12.2）源码整理',
      copyright: 'Apache-2.0'
    }
  }
})
