// ==UserScript==
// @name         抖音直播间净化器（可视化开关版）
// @namespace    http://tampermonkey.net/
// @version      3.4
// @author       CrazyH & dsv4
// @description  半透明毛玻璃面板，支持折叠/展开、拖拽移动，独立控制顶部、底部、礼物特效，并自动切换最高清晰度、屏蔽送礼信息与福袋口令。
// @match        https://live.douyin.com/*
// @match        https://www.douyin.com/*
// @grant        GM_addStyle
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_registerMenuCommand
// @run-at       document-start
// ==/UserScript==

(function() {
    'use strict';

    // ========== 配置项（存储 key 及默认值）==========
    const STORAGE_KEYS = {
        HIDE_TOP: 'douyin_clean_hide_top',
        HIDE_BOTTOM: 'douyin_clean_hide_bottom',
        HIDE_GIFT_EFFECT: 'douyin_clean_hide_gift_effect',
        AUTO_HD: 'douyin_clean_auto_hd',
        BLOCK_GIFT_MSG: 'douyin_clean_block_gift_msg',
        BLOCK_FUDAI: 'douyin_clean_block_fudai',
        PANEL_VISIBLE: 'douyin_clean_panel_visible',
        PANEL_COLLAPSED: 'douyin_clean_panel_collapsed',
        PANEL_POSITION: 'douyin_clean_panel_position'
    };
    const DEFAULTS = {
        [STORAGE_KEYS.HIDE_TOP]: true,
        [STORAGE_KEYS.HIDE_BOTTOM]: true,
        [STORAGE_KEYS.HIDE_GIFT_EFFECT]: true,
        [STORAGE_KEYS.AUTO_HD]: true,
        [STORAGE_KEYS.BLOCK_GIFT_MSG]: true,
        [STORAGE_KEYS.BLOCK_FUDAI]: true,
        [STORAGE_KEYS.PANEL_VISIBLE]: true,
        [STORAGE_KEYS.PANEL_COLLAPSED]: false,
        [STORAGE_KEYS.PANEL_POSITION]: { right: '20px', bottom: '20px' }
    };

    // 读取存储的开关状态
    function getConfig() {
        return {
            hideTop: GM_getValue(STORAGE_KEYS.HIDE_TOP, DEFAULTS[STORAGE_KEYS.HIDE_TOP]),
            hideBottom: GM_getValue(STORAGE_KEYS.HIDE_BOTTOM, DEFAULTS[STORAGE_KEYS.HIDE_BOTTOM]),
            hideGiftEffect: GM_getValue(STORAGE_KEYS.HIDE_GIFT_EFFECT, DEFAULTS[STORAGE_KEYS.HIDE_GIFT_EFFECT]),
            autoHd: GM_getValue(STORAGE_KEYS.AUTO_HD, DEFAULTS[STORAGE_KEYS.AUTO_HD]),
            blockGiftMsg: GM_getValue(STORAGE_KEYS.BLOCK_GIFT_MSG, DEFAULTS[STORAGE_KEYS.BLOCK_GIFT_MSG]),
            blockFudai: GM_getValue(STORAGE_KEYS.BLOCK_FUDAI, DEFAULTS[STORAGE_KEYS.BLOCK_FUDAI])
        };
    }

    // 保存单个开关
    function setConfig(key, value) {
        GM_setValue(key, value);
    }

    // ========== 动态生成 CSS（根据当前开关状态）==========
    function buildStyle(config) {
        const { hideTop, hideBottom, hideGiftEffect } = config;

        // 始终启用的样式：播放器容器 padding 重置（消除黑边/留白）
        const alwaysCss = `
            /* 消除播放器容器多余 Padding（用稳定的 id 前缀，不再依赖构建期哈希类名） */
            div[id^="living_player_container"] {
                padding: 0 !important;
                margin: 0 !important;
            }
        `;

        // 顶部区域屏蔽
        const topCss = hideTop ? `
            #HeaderLayout {
                display: none !important;
                height: 0 !important;
                padding: 0 !important;
            }
        ` : '';

        // 底部礼物/充值区域屏蔽
        const bottomCss = hideBottom ? `
            /* 只在确认是礼物栏、且底部容器里没有聊天输入时才整块隐藏，避免误伤其他布局 */
            #BottomLayout:has([data-e2e="gifts-container"]):not(:has(textarea, [contenteditable="true"], [data-e2e*="chat"])) {
                display: none !important;
            }
            /* 兜底：无论容器结构如何，礼物/充值相关节点一律隐藏 */
            [data-e2e="gifts-container"],
            [data-e2e="recharge-btn"],
            [data-e2e="gifts-switch"],
            [class*="gitBarOptimizeEnabled"] {
                display: none !important;
                height: 0 !important;
            }
        ` : '';

        // 礼物特效屏蔽
        const effectCss = hideGiftEffect ? `
            #GiftEffectLayout, #GiftTrayLayout {
                display: none !important;
                pointer-events: none !important;
            }
        ` : '';

        return alwaysCss + topCss + bottomCss + effectCss;
    }

    // ========== 样式注入与更新 ==========
    let currentStyleElement = null;

    function removeOldStyle() {
        if (currentStyleElement && currentStyleElement.parentNode) {
            currentStyleElement.parentNode.removeChild(currentStyleElement);
        }
        const oldStyle = document.getElementById('douyin-live-cleaner-style');
        if (oldStyle) oldStyle.remove();
    }

    function applyStyle() {
        const config = getConfig();
        const cssText = buildStyle(config);
        removeOldStyle();
        const style = document.createElement('style');
        style.id = 'douyin-live-cleaner-style';
        style.textContent = cssText;
        const insertStyle = () => {
            if (document.head) {
                document.head.appendChild(style);
                currentStyleElement = style;
                console.log('[抖音净化器] 样式已更新，当前状态：', config);
            } else {
                setTimeout(insertStyle, 10);
            }
        };
        insertStyle();
    }

    // ========== 可视化开关面板（支持折叠、拖拽、显示/隐藏）==========
    let panelElement = null;
    let isDragging = false;
    let dragStartX, dragStartY, panelStartLeft, panelStartTop;

    // 面板样式（使用 GM_addStyle 注入）- 已改为半透明背景
    GM_addStyle(`
        #dy-cleaner-panel {
            position: fixed;
            z-index: 999999;
            /* 半透明背景：深色但透明度较高，毛玻璃效果更明显 */
            background: rgba(0, 0, 0, 0.55);
            backdrop-filter: blur(12px);
            border-radius: 14px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
            font-size: 13px;
            user-select: none;
            min-width: 180px;
            border: 1px solid rgba(255,255,255,0.2);
            transition: width 0.2s, height 0.2s;
            overflow: hidden;
        }
        #dy-cleaner-panel.collapsed .panel-content {
            display: none;
        }
        #dy-cleaner-panel.collapsed {
            min-width: auto;
            width: auto;
        }
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            background: rgba(0,0,0,0.25);
            cursor: move;
            border-bottom: 1px solid rgba(255,255,255,0.15);
            gap: 8px;
        }
        .panel-title {
            font-weight: 600;
            color: #ffffff;
            font-size: 12px;
            letter-spacing: 0.5px;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
            flex: 1;
        }
        .panel-collapse, .panel-close {
            cursor: pointer;
            font-size: 16px;
            color: #ddd;
            line-height: 1;
            transition: color 0.2s, background 0.2s;
            background: rgba(255,255,255,0.1);
            border: none;
            border-radius: 6px;
            padding: 0 6px;
            width: 24px;
            height: 24px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }
        .panel-collapse:hover {
            background: rgba(255,255,255,0.2);
            color: #ffd966;
        }
        .panel-close:hover {
            background: rgba(255,255,255,0.2);
            color: #ff5e5e;
        }
        .panel-content {
            padding: 12px;
        }
        .switch-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
            color: #f0f0f0;
            text-shadow: 0 1px 1px rgba(0,0,0,0.3);
        }
        .switch-item:last-child {
            margin-bottom: 0;
        }
        .switch-label {
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
        }
        /* iOS 风格开关 */
        .switch {
            position: relative;
            display: inline-block;
            width: 40px;
            height: 22px;
        }
        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(100,100,100,0.8);
            transition: 0.2s;
            border-radius: 34px;
        }
        .slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 2px;
            bottom: 2px;
            background-color: white;
            transition: 0.2s;
            border-radius: 50%;
        }
        input:checked + .slider {
            background-color: #4caf50;
        }
        input:checked + .slider:before {
            transform: translateX(18px);
        }
    `);

    // 保存面板位置：直接读实际渲染出的 left/top（视口坐标），避免 right/bottom 计算歧义
    function savePanelPosition() {
        if (!panelElement) return;
        const rect = panelElement.getBoundingClientRect();
        if (rect.width === 0 && rect.height === 0) return; // 面板隐藏时不保存
        GM_setValue(STORAGE_KEYS.PANEL_POSITION, {
            left: Math.round(rect.left) + 'px',
            top: Math.round(rect.top) + 'px'
        });
    }

    // 把面板位置夹进当前窗口可视区，避免"窗口变形后跑到屏幕外"
    function clampPanelIntoView(panel) {
        if (!panel || panel.style.display === 'none') return;
        const rect = panel.getBoundingClientRect();
        const w = rect.width || panel.offsetWidth || 186;
        const h = rect.height || panel.offsetHeight || 160;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const margin = 10;
        const maxLeft = Math.max(margin, vw - w - margin);
        const maxTop = Math.max(margin, vh - h - margin);
        const left = Math.min(Math.max(margin, rect.left), maxLeft);
        const top = Math.min(Math.max(margin, rect.top), maxTop);
        panel.style.left = left + 'px';
        panel.style.top = top + 'px';
        panel.style.right = 'auto';
        panel.style.bottom = 'auto';
    }

    // 恢复面板位置（兼容旧版存下的 right/bottom），并强制夹进当前窗口
    function restorePanelPosition(panel) {
        const savedPos = GM_getValue(STORAGE_KEYS.PANEL_POSITION, DEFAULTS[STORAGE_KEYS.PANEL_POSITION]);
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const w = panel.offsetWidth || 186;
        const h = panel.offsetHeight || 160;
        const margin = 10;

        let left, top;
        if (savedPos && savedPos.left != null && savedPos.top != null) {
            left = parseFloat(savedPos.left);
            top = parseFloat(savedPos.top);
        } else if (savedPos && savedPos.right != null && savedPos.bottom != null) {
            // 旧版存档是 right/bottom：换算成 left/top
            left = vw - parseFloat(savedPos.right) - w;
            top = vh - parseFloat(savedPos.bottom) - h;
        } else {
            left = vw - 20 - w;
            top = vh - 20 - h;
        }

        // 关键：夹进当前窗口，修复「只在窗口最大化时才看得到」的问题
        const maxLeft = Math.max(margin, vw - w - margin);
        const maxTop = Math.max(margin, vh - h - margin);
        left = Math.min(Math.max(margin, left), maxLeft);
        top = Math.min(Math.max(margin, top), maxTop);

        panel.style.left = left + 'px';
        panel.style.top = top + 'px';
        panel.style.right = 'auto';
        panel.style.bottom = 'auto';
    }

    // 窗口尺寸变化时，把面板拉回可视区
    window.addEventListener('resize', () => clampPanelIntoView(panelElement));

    // 拖拽逻辑
    function initDrag(header, panel) {
        header.addEventListener('mousedown', (e) => {
            if (e.target.closest('.panel-collapse') || e.target.closest('.panel-close')) return;
            isDragging = true;
            dragStartX = e.clientX;
            dragStartY = e.clientY;

            const left = parseInt(panel.style.left);
            const top = parseInt(panel.style.top);
            const right = parseInt(panel.style.right);
            const bottom = parseInt(panel.style.bottom);

            if (!isNaN(left) && !isNaN(top)) {
                panelStartLeft = left;
                panelStartTop = top;
                panel.style.right = 'auto';
                panel.style.bottom = 'auto';
            } else if (!isNaN(right) && !isNaN(bottom)) {
                const rect = panel.getBoundingClientRect();
                panelStartLeft = rect.left;
                panelStartTop = rect.top;
                panel.style.left = rect.left + 'px';
                panel.style.top = rect.top + 'px';
                panel.style.right = 'auto';
                panel.style.bottom = 'auto';
            } else {
                const rect = panel.getBoundingClientRect();
                panelStartLeft = rect.left;
                panelStartTop = rect.top;
                panel.style.left = rect.left + 'px';
                panel.style.top = rect.top + 'px';
            }
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            let newLeft = panelStartLeft + (e.clientX - dragStartX);
            let newTop = panelStartTop + (e.clientY - dragStartY);
            newLeft = Math.min(window.innerWidth - panel.offsetWidth - 10, Math.max(10, newLeft));
            newTop = Math.min(window.innerHeight - panel.offsetHeight - 10, Math.max(10, newTop));
            panel.style.left = newLeft + 'px';
            panel.style.top = newTop + 'px';
            e.preventDefault();
        });

        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                savePanelPosition();
            }
        });
    }

    // 折叠/展开切换
    function toggleCollapse(panel, collapseBtn) {
        const isCollapsed = panel.classList.contains('collapsed');
        if (isCollapsed) {
            panel.classList.remove('collapsed');
            collapseBtn.textContent = '−';
            GM_setValue(STORAGE_KEYS.PANEL_COLLAPSED, false);
        } else {
            panel.classList.add('collapsed');
            collapseBtn.textContent = '+';
            GM_setValue(STORAGE_KEYS.PANEL_COLLAPSED, true);
        }
        savePanelPosition();
    }

    // 创建控制面板
    function createControlPanel() {
        if (panelElement) {
            panelElement.remove();
            panelElement = null;
        }

        const config = getConfig();
        const isCollapsed = GM_getValue(STORAGE_KEYS.PANEL_COLLAPSED, DEFAULTS[STORAGE_KEYS.PANEL_COLLAPSED]);

        const panel = document.createElement('div');
        panel.id = 'dy-cleaner-panel';
        if (isCollapsed) panel.classList.add('collapsed');

        const header = document.createElement('div');
        header.className = 'panel-header';
        header.innerHTML = `<span class="panel-title">直播间净化器</span>
                            <button class="panel-collapse" id="dy-panel-collapse-btn">${isCollapsed ? '+' : '−'}</button>
                            <button class="panel-close" id="dy-panel-close-btn">✕</button>`;

        const content = document.createElement('div');
        content.className = 'panel-content';
        content.innerHTML = `
            <div class="switch-item">
                <span class="switch-label">顶部信息栏</span>
                <label class="switch">
                    <input type="checkbox" id="switch-top" ${config.hideTop ? 'checked' : ''}>
                    <span class="slider"></span>
                </label>
            </div>
            <div class="switch-item">
                <span class="switch-label">底部礼物/充值区</span>
                <label class="switch">
                    <input type="checkbox" id="switch-bottom" ${config.hideBottom ? 'checked' : ''}>
                    <span class="slider"></span>
                </label>
            </div>
            <div class="switch-item">
                <span class="switch-label">礼物飘屏特效</span>
                <label class="switch">
                    <input type="checkbox" id="switch-effect" ${config.hideGiftEffect ? 'checked' : ''}>
                    <span class="slider"></span>
                </label>
            </div>
            <div class="switch-item">
                <span class="switch-label">自动最高清晰度</span>
                <label class="switch">
                    <input type="checkbox" id="switch-hd" ${config.autoHd ? 'checked' : ''}>
                    <span class="slider"></span>
                </label>
            </div>
            <div class="switch-item">
                <span class="switch-label">屏蔽送礼信息</span>
                <label class="switch">
                    <input type="checkbox" id="switch-giftmsg" ${config.blockGiftMsg ? 'checked' : ''}>
                    <span class="slider"></span>
                </label>
            </div>
            <div class="switch-item">
                <span class="switch-label">屏蔽福袋口令</span>
                <label class="switch">
                    <input type="checkbox" id="switch-fudai" ${config.blockFudai ? 'checked' : ''}>
                    <span class="slider"></span>
                </label>
            </div>
        `;

        panel.appendChild(header);
        panel.appendChild(content);
        document.body.appendChild(panel);

        restorePanelPosition(panel);

        // 绑定开关事件
        const topSwitch = content.querySelector('#switch-top');
        const bottomSwitch = content.querySelector('#switch-bottom');
        const effectSwitch = content.querySelector('#switch-effect');

        topSwitch.addEventListener('change', (e) => {
            const newVal = e.target.checked;
            setConfig(STORAGE_KEYS.HIDE_TOP, newVal);
            applyStyle();
            console.log(`[抖音净化器] 顶部信息栏 ${newVal ? '已隐藏' : '已显示'}`);
        });

        bottomSwitch.addEventListener('change', (e) => {
            const newVal = e.target.checked;
            setConfig(STORAGE_KEYS.HIDE_BOTTOM, newVal);
            applyStyle();
            console.log(`[抖音净化器] 底部礼物区 ${newVal ? '已隐藏' : '已显示'}`);
        });

        effectSwitch.addEventListener('change', (e) => {
            const newVal = e.target.checked;
            setConfig(STORAGE_KEYS.HIDE_GIFT_EFFECT, newVal);
            applyStyle();
            console.log(`[抖音净化器] 礼物特效 ${newVal ? '已隐藏' : '已显示'}`);
        });

        const hdSwitch = content.querySelector('#switch-hd');
        hdSwitch.addEventListener('change', (e) => {
            setConfig(STORAGE_KEYS.AUTO_HD, e.target.checked);
            resetLiveEngine();
            console.log(`[抖音净化器] 自动最高清晰度 ${e.target.checked ? '已开启' : '已关闭'}`);
        });

        const giftMsgSwitch = content.querySelector('#switch-giftmsg');
        giftMsgSwitch.addEventListener('change', (e) => {
            setConfig(STORAGE_KEYS.BLOCK_GIFT_MSG, e.target.checked);
            resetLiveEngine();
            console.log(`[抖音净化器] 屏蔽送礼信息 ${e.target.checked ? '已开启' : '已关闭'}`);
        });

        const fudaiSwitch = content.querySelector('#switch-fudai');
        fudaiSwitch.addEventListener('change', (e) => {
            setConfig(STORAGE_KEYS.BLOCK_FUDAI, e.target.checked);
            resetLiveEngine();
            console.log(`[抖音净化器] 屏蔽福袋口令 ${e.target.checked ? '已开启' : '已关闭'}`);
        });

        const collapseBtn = header.querySelector('#dy-panel-collapse-btn');
        collapseBtn.addEventListener('click', () => {
            toggleCollapse(panel, collapseBtn);
        });

        const closeBtn = header.querySelector('#dy-panel-close-btn');
        closeBtn.addEventListener('click', () => {
            panel.style.display = 'none';
            GM_setValue(STORAGE_KEYS.PANEL_VISIBLE, false);
            console.log('[抖音净化器] 控制面板已隐藏');
        });

        initDrag(header, panel);

        panelElement = panel;

        const isVisible = GM_getValue(STORAGE_KEYS.PANEL_VISIBLE, DEFAULTS[STORAGE_KEYS.PANEL_VISIBLE]);
        if (!isVisible) {
            panel.style.display = 'none';
        } else {
            panel.style.display = 'block';
        }
    }

    // 显示/隐藏面板（供菜单调用）
    function togglePanelVisibility() {
        if (!panelElement) {
            createControlPanel();
        } else {
            const isVisible = panelElement.style.display !== 'none';
            if (isVisible) {
                panelElement.style.display = 'none';
                GM_setValue(STORAGE_KEYS.PANEL_VISIBLE, false);
                console.log('[抖音净化器] 控制面板已隐藏');
            } else {
                panelElement.style.display = 'block';
                GM_setValue(STORAGE_KEYS.PANEL_VISIBLE, true);
                console.log('[抖音净化器] 控制面板已显示');
            }
        }
    }

    // ========== 油猴菜单命令 ==========
    function registerMenuCommands() {
        GM_registerMenuCommand('显示/隐藏净化面板', () => {
            togglePanelVisibility();
        });

        GM_registerMenuCommand('查看当前净化状态', () => {
            const cfg = getConfig();
            const status = `当前净化设置：
- 顶部信息栏：${cfg.hideTop ? '隐藏 ✓' : '显示'}
- 底部礼物/充值区：${cfg.hideBottom ? '隐藏 ✓' : '显示'}
- 礼物飘屏特效：${cfg.hideGiftEffect ? '隐藏 ✓' : '显示'}
- 自动最高清晰度：${cfg.autoHd ? '开启 ✓' : '关闭'}
- 屏蔽送礼信息：${cfg.blockGiftMsg ? '开启 ✓' : '关闭'}
- 屏蔽福袋口令：${cfg.blockFudai ? '开启 ✓' : '关闭'}
━━━━━━━━━━━━━━
提示：也可使用页面右下角的半透明面板进行调整`;
            alert(status);
        });
    }

    // ========== 直播间增强引擎（自动最高清晰度 / 屏蔽送礼信息 / 屏蔽福袋口令）==========
    const liveState = {
        roomKey: null,
        settingsKey: '',
        triedQuality: false,
        triedDanmaku: false,
        danmakuInFlight: false,
        timer: null
    };

    function sleep(ms) {
        return new Promise((resolve) => window.setTimeout(resolve, ms));
    }

    function dispatchMouseEvent(el, type, x, y) {
        if (!el) return;
        try {
            el.dispatchEvent(new MouseEvent(type, {
                view: window, bubbles: true, cancelable: true,
                clientX: x || 0, clientY: y || 0
            }));
        } catch (e) { /* ignore */ }
    }

    function simulateClick(el) {
        if (!el) return;
        const rect = el.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;
        ['mouseenter', 'mouseover', 'mousemove', 'mousedown', 'mouseup', 'click'].forEach((t) => {
            dispatchMouseEvent(el, t, x, y);
        });
    }

    async function waitForElement(selector, timeoutMs) {
        const deadline = Date.now() + timeoutMs;
        while (Date.now() < deadline) {
            const el = document.querySelector(selector);
            if (el) return el;
            await sleep(100);
        }
        return null;
    }

    function activatePlayer(player) {
        if (!player) return;
        player.classList.remove('douyin-player-inactive');
        player.classList.add('douyin-player-active', 'douyin-player-focus');
        const rect = player.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;
        dispatchMouseEvent(document, 'mousemove', x, y);
        dispatchMouseEvent(player, 'mousemove', x, y);
    }

    // ---- 自动最高清晰度：悬停清晰度菜单，选择当前可用的最高档 ----
    async function trySetHighestQuality() {
        if (liveState.triedQuality) return;
        if (!getConfig().autoHd) { liveState.triedQuality = true; return; }
        const plugin = document.querySelector('.QualitySwitchNewPlugin');
        if (!plugin) return; // 还没渲染好，下次再试
        activatePlayer(document.querySelector('.F5Mbv3g1'));
        const pr = plugin.getBoundingClientRect();
        ['mouseenter', 'mouseover', 'mousemove'].forEach((t) => {
            dispatchMouseEvent(plugin, t, pr.left + pr.width / 2, pr.top + pr.height / 2);
        });
        await sleep(250);
        const rows = [...plugin.querySelectorAll('.tmNdnn5Q')];
        if (!rows.length) return;
        const rowText = (el) => (el.innerText || el.textContent || '').trim();
        const order = ['原画', '蓝光', '超清', '高清', '标清'];
        const current = (document.querySelector('[data-e2e="quality"]')?.innerText || '').trim();
        let target = null;
        for (const label of order) {
            const row = rows.find((el) => rowText(el).includes(label));
            if (!row) continue;
            if (rowText(row).includes('登录即享')) continue; // 未登录不可选
            target = { row, label };
            break;
        }
        if (!target) {
            const row = rows.find((el) => rowText(el).includes('原画'));
            if (row) target = { row, label: '原画' };
        }
        if (!target) return;
        const rankOf = (text) => {
            for (let i = 0; i < order.length; i++) {
                if (text.includes(order[i])) return order.length - i;
            }
            return 0; // 智能 / 未知
        };
        // 只升不降：已经不低于目标档位就不动（避免误把清晰度调低）
        if (rankOf(target.label) <= rankOf(current)) { liveState.triedQuality = true; return; }
        simulateClick(target.row);
        await sleep(300);
        liveState.triedQuality = true;
        console.log('[抖音净化器] 已尝试切换到清晰度：', target.label);
    }

    // ---- 弹幕设置：关闭“送礼信息” / “福袋口令” ----
    function isSwitchChecked(el) {
        if (!el) return false;
        const attrOwner = el.matches('[aria-checked], [data-state]') ? el : el.querySelector('[aria-checked], [data-state]');
        const aria = attrOwner?.getAttribute('aria-checked');
        if (aria === 'true') return true;
        if (aria === 'false') return false;
        const state = attrOwner?.getAttribute('data-state');
        if (state === 'checked' || state === 'on' || state === 'open') return true;
        if (state === 'unchecked' || state === 'off' || state === 'closed') return false;
        const input = el.matches('input') ? el : el.querySelector('input[type="checkbox"]');
        if (input) return input.checked;
        return el.classList.contains('SpsbqNUm');
    }

    function findToggleByLabel(panel, labelText) {
        const normalize = (s) => (s || '').replace(/\s+/g, '');
        for (const label of panel.querySelectorAll('*')) {
            if (label.children.length > 0) continue;
            if (!normalize(label.textContent).includes(labelText)) continue;
            let row = label.parentElement;
            while (row && row !== panel) {
                const toggle = row.querySelector('.dNuSIvAp');
                if (toggle) return toggle;
                row = row.parentElement;
            }
        }
        return null;
    }

    async function setNamedToggle(panel, label, desiredOn) {
        const toggle = findToggleByLabel(panel, label);
        if (!toggle) return 'missing';
        if (isSwitchChecked(toggle) === desiredOn) return 'settled';
        simulateClick(toggle);
        for (let i = 0; i < 6; i++) {
            await sleep(100);
            if (isSwitchChecked(toggle) === desiredOn) return 'changed';
        }
        return 'missing';
    }

    async function openDanmakuPanel(player) {
        activatePlayer(player);
        await sleep(250);
        const btn = document.querySelector('[data-e2e="danmaku-setting-icon"]');
        if (!btn) return null;
        const br = btn.getBoundingClientRect();
        dispatchMouseEvent(document, 'mousemove', br.left + br.width / 2, br.top + br.height / 2);
        dispatchMouseEvent(player, 'mousemove', br.left + br.width / 2, br.top + br.height / 2);
        await sleep(120);
        simulateClick(btn);
        let panel = await waitForElement('.UMXOdhRc', 1500);
        if (!panel) {
            // 兜底：按文案定位弹幕设置面板
            panel = [...document.querySelectorAll('div')].find((el) => {
                const t = el.innerText || '';
                return t.includes('弹幕设置') && t.includes('恢复默认') && el.querySelector('.dNuSIvAp');
            }) || null;
        }
        if (panel) panel.style.removeProperty('display');
        return panel;
    }

    async function applyDanmakuSettings() {
        if (liveState.triedDanmaku || liveState.danmakuInFlight) return;
        const cfg = getConfig();
        if (!cfg.blockGiftMsg && !cfg.blockFudai) { liveState.triedDanmaku = true; return; }
        const player = document.querySelector('.F5Mbv3g1');
        if (!player) return; // 播放器还没出来，下次再试
        liveState.danmakuInFlight = true;
        try {
            const panel = await openDanmakuPanel(player);
            if (!panel) return; // 面板没打开，下次再试
            try {
                if (cfg.blockGiftMsg) await setNamedToggle(panel, '送礼信息', false);
                if (cfg.blockFudai) await setNamedToggle(panel, '福袋口令', false);
            } finally {
                await sleep(150);
                panel.style.display = 'none';
            }
            liveState.triedDanmaku = true;
            console.log('[抖音净化器] 已应用弹幕设置（送礼信息/福袋口令）');
        } finally {
            liveState.danmakuInFlight = false;
        }
    }

    function syncLiveState() {
        const cfg = getConfig();
        const roomKey = location.pathname;
        const settingsKey = [cfg.autoHd, cfg.blockGiftMsg, cfg.blockFudai].join(':');
        if (roomKey === liveState.roomKey && settingsKey === liveState.settingsKey) return;
        liveState.roomKey = roomKey;
        liveState.settingsKey = settingsKey;
        liveState.triedQuality = false;
        liveState.triedDanmaku = false;
    }

    function liveTick() {
        syncLiveState();
        trySetHighestQuality();
        applyDanmakuSettings();
    }

    function resetLiveEngine() {
        liveState.triedQuality = false;
        liveState.triedDanmaku = false;
        liveState.settingsKey = '';
        if (liveState.timer !== null) liveTick();
    }

    function startLiveEngine() {
        if (liveState.timer !== null) return;
        liveState.timer = window.setInterval(liveTick, 2000);
        window.setTimeout(() => trySetHighestQuality(), 5000);
        liveTick();
    }

    // ========== 初始化 ==========
    // 只在真正的直播间里创建面板；首页/普通视频页不显示这块用不上的面板
    function isLiveRoomPresent() {
        return !!document.querySelector('div[id^="living_player_container"], #BottomLayout, #chatroom');
    }

    function whenLiveRoomReady(cb) {
        if (isLiveRoomPresent()) { cb(); return; }
        let done = false;
        const obs = new MutationObserver(() => {
            if (done) return;
            if (isLiveRoomPresent()) {
                done = true;
                obs.disconnect();
                cb();
            }
        });
        try {
            obs.observe(document.documentElement, { childList: true, subtree: true });
        } catch (e) {
            // 极端情况下退回定时轮询
            const timer = setInterval(() => {
                if (isLiveRoomPresent()) { clearInterval(timer); cb(); }
            }, 500);
            return;
        }
        // 兜底：长时间没有直播间就停止观察（避免一直空转）
        setTimeout(() => { if (!done) obs.disconnect(); }, 45000);
    }

    function init() {
        applyStyle();
        registerMenuCommands();
        whenLiveRoomReady(() => {
            createControlPanel();
            startLiveEngine();
        });
        console.log('抖音直播间净化器 v3.4 已启动 — 毛玻璃面板 + 自动清晰度/屏蔽送礼·福袋');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();