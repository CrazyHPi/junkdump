// ==UserScript==
// @name         抖音直播间净化器（可视化开关版）
// @namespace    http://tampermonkey.net/
// @version      3.2
// @author       CrazyH & dsv4
// @description  半透明毛玻璃面板，支持折叠/展开、拖拽移动，独立控制顶部、底部、礼物特效。
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
        PANEL_VISIBLE: 'douyin_clean_panel_visible',
        PANEL_COLLAPSED: 'douyin_clean_panel_collapsed',
        PANEL_POSITION: 'douyin_clean_panel_position'
    };
    const DEFAULTS = {
        [STORAGE_KEYS.HIDE_TOP]: true,
        [STORAGE_KEYS.HIDE_BOTTOM]: true,
        [STORAGE_KEYS.HIDE_GIFT_EFFECT]: true,
        [STORAGE_KEYS.PANEL_VISIBLE]: true,
        [STORAGE_KEYS.PANEL_COLLAPSED]: false,
        [STORAGE_KEYS.PANEL_POSITION]: { right: '20px', bottom: '20px' }
    };

    // 读取存储的开关状态
    function getConfig() {
        return {
            hideTop: GM_getValue(STORAGE_KEYS.HIDE_TOP, DEFAULTS[STORAGE_KEYS.HIDE_TOP]),
            hideBottom: GM_getValue(STORAGE_KEYS.HIDE_BOTTOM, DEFAULTS[STORAGE_KEYS.HIDE_BOTTOM]),
            hideGiftEffect: GM_getValue(STORAGE_KEYS.HIDE_GIFT_EFFECT, DEFAULTS[STORAGE_KEYS.HIDE_GIFT_EFFECT])
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
            /* 消除播放器容器多余 Padding */
            div[id^="living_player_container"] {
                padding: 0 !important;
                margin: 0 !important;
            }
            .luP71X7i, .gZxYAuQb {
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
            #BottomLayout {
                display: none !important;
            }
            #BottomLayout div:has([data-e2e="gifts-container"]),
            #BottomLayout div:has([data-e2e="recharge-btn"]),
            #BottomLayout div:has([data-e2e="gifts-switch"]),
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

    // 保存面板位置
    function savePanelPosition() {
        if (!panelElement) return;
        const style = window.getComputedStyle(panelElement);
        const position = {
            right: style.right,
            bottom: style.bottom,
            left: style.left,
            top: style.top
        };
        if (position.right !== 'auto' && position.bottom !== 'auto') {
            GM_setValue(STORAGE_KEYS.PANEL_POSITION, { right: position.right, bottom: position.bottom });
        } else if (position.left !== 'auto' && position.top !== 'auto') {
            GM_setValue(STORAGE_KEYS.PANEL_POSITION, { left: position.left, top: position.top });
        }
    }

    // 恢复面板位置
    function restorePanelPosition(panel) {
        const savedPos = GM_getValue(STORAGE_KEYS.PANEL_POSITION, DEFAULTS[STORAGE_KEYS.PANEL_POSITION]);
        if (savedPos.right && savedPos.bottom) {
            panel.style.right = savedPos.right;
            panel.style.bottom = savedPos.bottom;
            panel.style.left = 'auto';
            panel.style.top = 'auto';
        } else if (savedPos.left && savedPos.top) {
            panel.style.left = savedPos.left;
            panel.style.top = savedPos.top;
            panel.style.right = 'auto';
            panel.style.bottom = 'auto';
        } else {
            panel.style.right = '20px';
            panel.style.bottom = '20px';
        }
    }

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
        header.innerHTML = `<span class="panel-title">🎛️ 直播间净化器</span>
                            <button class="panel-collapse" id="dy-panel-collapse-btn">${isCollapsed ? '+' : '−'}</button>
                            <button class="panel-close" id="dy-panel-close-btn">✕</button>`;

        const content = document.createElement('div');
        content.className = 'panel-content';
        content.innerHTML = `
            <div class="switch-item">
                <span class="switch-label">📡 顶部信息栏</span>
                <label class="switch">
                    <input type="checkbox" id="switch-top" ${config.hideTop ? 'checked' : ''}>
                    <span class="slider"></span>
                </label>
            </div>
            <div class="switch-item">
                <span class="switch-label">🎁 底部礼物/充值区</span>
                <label class="switch">
                    <input type="checkbox" id="switch-bottom" ${config.hideBottom ? 'checked' : ''}>
                    <span class="slider"></span>
                </label>
            </div>
            <div class="switch-item">
                <span class="switch-label">✨ 礼物飘屏特效</span>
                <label class="switch">
                    <input type="checkbox" id="switch-effect" ${config.hideGiftEffect ? 'checked' : ''}>
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
        GM_registerMenuCommand('🖥️ 显示/隐藏净化面板', () => {
            togglePanelVisibility();
        });

        GM_registerMenuCommand('📋 查看当前净化状态', () => {
            const cfg = getConfig();
            const status = `当前净化设置：
- 顶部信息栏：${cfg.hideTop ? '隐藏 ✓' : '显示'}
- 底部礼物/充值区：${cfg.hideBottom ? '隐藏 ✓' : '显示'}
- 礼物飘屏特效：${cfg.hideGiftEffect ? '隐藏 ✓' : '显示'}
━━━━━━━━━━━━━━
💡 提示：也可使用页面右下角的半透明面板进行调整`;
            alert(status);
        });
    }

    // ========== 初始化 ==========
    function init() {
        applyStyle();
        createControlPanel();
        registerMenuCommands();
        console.log('抖音直播间净化器 v3.2 已启动 — 半透明毛玻璃面板，支持折叠/拖拽');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();