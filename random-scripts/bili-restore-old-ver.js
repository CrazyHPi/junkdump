// ==UserScript==
// @name         B站旧版动态恢复
// @namespace    http://tampermonkey.net/
// @version      1.2
// @description  当访问B站旧版动态时，强制替换为旧版HTML内容。v1.2: 修复与Bilibili-Evolved同时启用时图片无法加载的问题。
// @author       caycy01 % deepseek_v4
// @include      *://t.bilibili.com/?*
// @include      *://t.bilibili.com/
// @run-at       document-start
// @grant        none
// ==/UserScript==

(function() {
    'use strict';
    // 用户提供的旧版页面完整HTML内容
    const oldPageHTML = `<!DOCTYPE html>
<html>
<meta>
<title>动态首页-哔哩哔哩</title>
<meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
<meta name="format-detection" content="telephone=no, email=no">
<meta http-equiv="Content-Type" content="text/html" charset="utf-8">
<meta name="spm_prefix" content="444.41">
<meta name="referrer" content="no-referrer-when-downgrade">
<meta name="renderer" content="webkit">
<meta name="keywords"
  content="Bilibili,哔哩哔哩,哔哩哔哩动画,哔哩哔哩弹幕网,弹幕视频,B站,弹幕,字幕,AMV,MAD,MTV,ANIME,动漫,动漫音乐,游戏,游戏解说,二次元,游戏视频,ACG,galgame,动画,番组,新番,初音,洛天依,vocaloid,日本动漫,国产动漫,手机游戏,网络游戏,电子竞技,ACG燃曲,ACG神曲,追新番,新番动漫,新番吐槽,巡音,镜音双子,千本樱,初音MIKU,舞蹈MMD,MIKUMIKUDANCE,洛天依原创曲,洛天依翻唱曲,洛天依投食歌,洛天依MMD,vocaloid家族,OST,BGM,动漫歌曲,日本动漫音乐,宫崎骏动漫音乐,动漫音乐推荐,燃系mad,治愈系mad,MAD MOVIE,MAD高燃">
<meta name="application-name" content="哔哩哔哩">
<meta name="theme-color" content="#4393E2">
<meta name="apple-mobile-web-app-capable" content="#yes">
<meta name="theme-color" content="black">
<meta name="apple-mobile-web-app-status-bar-style" content="#4393E2">
<link rel="dns-prefetch" href="https://s1.hdslb.com/">
<link rel="apple-touch-icon" href="https://static.hdslb.com/mobile/img/512.png">
<link rel="shortcut icon" href="https://www.bilibili.com/favicon.ico">
<script type="text/javascript"
  src="https://s1.hdslb.com/bfs/static/jinkela/long/js/sentry/sentry-5.7.1.min.js"></script>
<script type="text/javascript"
  src="https://s1.hdslb.com/bfs/static/jinkela/long/js/sentry/sentry-5.7.1.vue.min.js"></script>
<script type="text/javascript" src="https://s1.hdslb.com/bfs/seed/laputa-header/bili-header.umd.js"></script>
<script type="text/javascript" src="https://s1.hdslb.com/bfs/cm/cm-sdk/static/js/bili-collect.js"></script>
<script id="abtest" type="text/javascript">window.abtest = {
    "in_new_ab": true, "ab_version": {
      "for_new_version": "NEW",
      "for_new_opus_version": "NEW",
      "in_theme_version": "CLOSE",
      "enable_search_trending": "ENABLE",
      "can_go_old": "ENABLED"
    }
  }</script>
</body>
<link
  href="https://s1.hdslb.com/bfs/static/stone-free/dyn-home/css/dyn-home.1.42ec289551f1963fe66e6777823ef1b2f210f540.css"
  rel="stylesheet">
<link
  href="https://s1.hdslb.com/bfs/static/stone-free/dyn-home/css/dyn-home.0.42ec289551f1963fe66e6777823ef1b2f210f540.css"
  rel="stylesheet">
<script>window.reportMsgObj = {}, window.reportConfig = { sample: 1, scrollTracker: !1, msgObjects: "reportMsgObj" }</script>

<body>
  <div class="z-top-container" id="bili-header-container"></div>
  <div id="dyn-home-app"></div>
  <script>var el = document.getElementById("bili-header-container"), header = new BiliHeader({ config: { disableChannelEntry: !1, disableSticky: !0 } }); header.init(el)</script>
  <script src="https://s1.hdslb.com/bfs/seed/log/report/log-reporter.js"></script>
  <script type="text/javascript"
    src="https://s1.hdslb.com/bfs/static/stone-free/dyn-home/1.dyn-home.42ec289551f1963fe66e6777823ef1b2f210f540.js"></script>
  <script type="text/javascript"
    src="https://s1.hdslb.com/bfs/static/stone-free/dyn-home/dyn-home.42ec289551f1963fe66e6777823ef1b2f210f540.js"></script>
</body>

</html>
`;

    // 使用document.open/write完全替换当前页面内容
    document.open();
    document.write(oldPageHTML);
    document.close();

    // 修复与 Bilibili-Evolved 同时启用时图片无法加载的问题：
    // Chrome 预加载扫描器在 document-start 就已将新版 JS/CSS 加入加载队列，
    // 导致新旧两版资源同时加载。新版 CSS 可能覆盖旧版图片样式。
    // 这里注入 !important 保护规则，并在新版 CSS 加载后立即移除。
    const fixStyle = document.createElement('style');
    fixStyle.id = 'bili-old-ver-image-fix';
    fixStyle.textContent = [
        'img[src*="hdslb.com/bfs/face"],',
        'img[src*="hdslb.com/bfs/archive"],',
        'img[src*="hdslb.com/bfs/vc/"],',
        'img[src*="hdslb.com/bfs/space/"],',
        '#dyn-home-app img,',
        '.card-pic img, .preview img, .imagesbox img,',
        '.bili-dyn-list__item__cover img, .bili-dyn-list__item__face img',
        '{ display: revert !important; visibility: visible !important; opacity: 1 !important; }',
    ].join('\n');
    document.head.appendChild(fixStyle);

    // 移除 Chrome 预加载扫描器加载的新版资源
    // 使用已废弃但同步触发的 DOMNodeInserted 事件确保在 CSS 生效前拦截
    document.addEventListener('DOMNodeInserted', function(e) {
        var target = e.target;
        if (!target || !target.tagName) return;
        var tag = target.tagName.toLowerCase();
        if (tag === 'script' || tag === 'link') {
            var url = (target.src || target.href || '').toLowerCase();
            if (url.indexOf('2233-monorepo') !== -1) {
                target.remove();
            }
        }
    });
})();