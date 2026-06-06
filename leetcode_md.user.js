// ==UserScript==
// @name         LeetCode|力扣 题单多功能目录插件
// @license MIT
// @namespace    http://tampermonkey.net/
// @version      1.0.2
// @description  自动生成题单目录+一键跳转+自动标记已做题目+自动跳转到上一次浏览位置+题目标题一键复制
// @author       0xff (Fixed by Assistant)
// @match        *://leetcode.cn/discuss/*
// @match        *://leetcode.cn/problems/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=leetcode.cn
// @grant        none
// @downloadURL https://update.greasyfork.org/scripts/562330/LeetCode%7C%E5%8A%9B%E6%89%A3%20%E9%A2%98%E5%8D%95%E5%A4%9A%E5%8A%9F%E8%83%BD%E7%9B%AE%E5%BD%95%E6%8F%92%E4%BB%B6.user.js
// @updateURL https://update.greasyfork.org/scripts/562330/LeetCode%7C%E5%8A%9B%E6%89%A3%20%E9%A2%98%E5%8D%95%E5%A4%9A%E5%8A%9F%E8%83%BD%E7%9B%AE%E5%BD%95%E6%8F%92%E4%BB%B6.meta.js
// ==/UserScript==

(function() {
    'use strict';

    // === 全局状态变量 ===
    let tocContainer = null;      // 目录容器DOM
    let currentPath = location.pathname; // 当前路径
    let checkContentTimer = null; // 内容检测定时器
    let refreshTimer = null;      // 自动刷新定时器

    // === 配置参数 (动态获取) ===
    const getConfig = () => ({
        title: "大纲目录",
        width: 240,
        indent: 20,
        bgColor: "#ffffff",
        textColor: "#37352f",
        hoverColor: "#f0f0f0",
        // 关键：keyPrefix 必须是个函数或动态获取，确保SPA跳转后key能变
        keyPrefix: "tm_toc_save_" + location.pathname,
        refreshInterval: 5 * 60 * 1000 // 5分钟
    });

    // === 辅助函数：存取本地数据 ===
    const Storage = {
        get: (key, def) => {
            const config = getConfig();
            const val = localStorage.getItem(config.keyPrefix + key);
            return val ? JSON.parse(val) : def;
        },
        set: (key, val) => {
            const config = getConfig();
            localStorage.setItem(config.keyPrefix + key, JSON.stringify(val));
        }
    };

    // ==========================================
    // Feature 1: 题目页面 - 复制标题按钮
    // ==========================================
    function renderCopyButton() {
        // 1. 仅在题目页面运行
        if (!location.pathname.startsWith('/problems/')) return false;

        // 2. 防止重复添加
        if (document.getElementById('tm-lc-copy-btn')) return true;

        // 3. 寻找标题元素
        const titleContainer = document.querySelector('.text-title-large');
        const titleLink = titleContainer ? titleContainer.querySelector('a') : null;

        if (!titleContainer || !titleLink) return false; // 还没加载出来

        // 4. 创建复制按钮
        const btn = document.createElement('div');
        btn.id = 'tm-lc-copy-btn';
        btn.style.cssText = `
            display: inline-flex; align-items: center; justify-content: center;
            margin-left: 8px; cursor: pointer; color: #9ca3af;
            width: 24px; height: 24px; border-radius: 4px; transition: all 0.2s;
            vertical-align: middle;
        `;
        // SVG 图标 (复制图标)
        const copyIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
        const checkIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;

        btn.innerHTML = copyIcon;
        btn.title = "复制 Markdown (标题+链接图标)";

        // 5. 悬停效果
        btn.onmouseenter = () => { btn.style.backgroundColor = 'rgba(0,0,0,0.05)'; btn.style.color = '#333'; };
        btn.onmouseleave = () => { btn.style.backgroundColor = 'transparent'; btn.style.color = '#9ca3af'; };

        // 6. 点击事件
        btn.onclick = (e) => {
            e.preventDefault();
            e.stopPropagation();

            let text = titleLink.innerText.trim();
            // 去除开头的数字和点 (如 "1749. " -> "")
            text = text.replace(/^\d+\.\s*/, '');

            const url = titleLink.href;

            // --- 核心修改：**标题** [🔗](链接) ---
            const markdown = `**${text}** [🔗](${url})`;

            navigator.clipboard.writeText(markdown).then(() => {
                btn.innerHTML = checkIcon;
                setTimeout(() => {
                    btn.innerHTML = copyIcon;
                }, 2000);
            }).catch(err => {
                console.error('复制失败:', err);
                alert('复制失败，请手动复制');
            });
        };

        // 7. 插入到标题后面
        titleContainer.appendChild(btn);

        return true;
    }


    // ==========================================
    // Feature 2: 讨论区/题单 - 目录渲染逻辑
    // ==========================================

    function removeTOC() {
        if (tocContainer && tocContainer.parentNode) {
            tocContainer.parentNode.removeChild(tocContainer);
        }
        tocContainer = null;
    }

    function renderTOC() {
        // 如果不是讨论区或没有标题，直接返回
        const headings = document.querySelectorAll('h2, h3');
        if (headings.length === 0) return false;

        // 先清理旧的
        removeTOC();

        const config = getConfig();
        const savedPos = Storage.get('pos', { top: 100, left: 20 });
        const savedState = Storage.get('expanded', true);

        // 注入样式 (移除固定写死的top和left，改用内联样式，以防SPA跳转时跳回首次位置)
        if (!document.getElementById('tm-toc-style')) {
            const css = `
                #tm-toc-container {
                    position: fixed;
                    width: ${config.width}px; max-height: 80vh; background: ${config.bgColor};
                    box-shadow: rgba(15, 15, 15, 0.05) 0px 0px 0px 1px, rgba(15, 15, 15, 0.1) 0px 3px 6px, rgba(15, 15, 15, 0.2) 0px 9px 24px;
                    border-radius: 8px; z-index: 9999;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                    color: ${config.textColor}; overflow: hidden; display: flex; flex-direction: column;
                    font-size: 14px; transition: opacity 0.2s;
                }
                #tm-toc-header {
                    padding: 12px 16px; font-weight: 600; border-bottom: 1px solid rgba(55, 53, 47, 0.09);
                    cursor: move; user-select: none; display: flex; justify-content: space-between; align-items: center;
                    background: #fbfbfa;
                }
                #tm-toc-toggle { cursor: pointer; color: #999; font-size: 12px; padding: 4px; }
                #tm-toc-toggle:hover { color: #333; }
                #tm-toc-content {
                    overflow-y: auto; padding: 8px 0; flex: 1;
                    display: ${savedState ? 'block' : 'none'};
                }
                #tm-toc-content::-webkit-scrollbar { width: 6px; }
                #tm-toc-content::-webkit-scrollbar-thumb { background: #e0e0e0; border-radius: 3px; }
                .tm-toc-item {
                    padding: 6px 16px; cursor: pointer; white-space: nowrap; overflow: hidden;
                    text-overflow: ellipsis; line-height: 1.5; text-decoration: none; display: block; color: inherit;
                }
                .tm-toc-item:hover { background-color: ${config.hoverColor}; }
                .tm-toc-h2 { font-weight: 500; }
                .tm-toc-h3 { font-weight: 400; padding-left: ${16 + config.indent}px; color: #666; font-size: 0.95em; }
            `;
            if (typeof GM_addStyle !== 'undefined') {
                GM_addStyle(css);
            } else {
                const style = document.createElement('style');
                style.id = 'tm-toc-style';
                style.innerHTML = css;
                document.head.appendChild(style);
            }
        }

        // 构建DOM
        const container = document.createElement('div');
        container.id = 'tm-toc-container';

        // --- 修复：防止初始化位置超出当前窗口大小 ---
        const maxSafeTop = Math.max(0, window.innerHeight - 40);
        const maxSafeLeft = Math.max(0, window.innerWidth - config.width);
        container.style.top = `${Math.max(0, Math.min(savedPos.top, maxSafeTop))}px`;
        container.style.left = `${Math.max(0, Math.min(savedPos.left, maxSafeLeft))}px`;

        tocContainer = container;

        const header = document.createElement('div');
        header.id = 'tm-toc-header';
        header.innerHTML = `<span>${config.title}</span><span id="tm-toc-toggle">${savedState ? '▼' : '◀'}</span>`;
        container.appendChild(header);

        const contentBox = document.createElement('div');
        contentBox.id = 'tm-toc-content';

        headings.forEach((node, index) => {
            if (!node.id) node.id = 'tm-toc-heading-' + index;
            const link = document.createElement('div');
            link.className = `tm-toc-item tm-toc-${node.tagName.toLowerCase()}`;
            link.innerText = node.innerText.replace(/^§/, '');
            link.title = node.innerText;
            link.addEventListener('click', (e) => {
                e.preventDefault();
                Storage.set('scrollY', window.scrollY);
                node.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
            contentBox.appendChild(link);
        });

        container.appendChild(contentBox);
        document.body.appendChild(container);

        // 绑定事件
        bindEvents(container, header, contentBox);

        // 恢复上次阅读位置
        setTimeout(() => {
            const lastScrollY = Storage.get('scrollY', 0);
            if (lastScrollY > 0) window.scrollTo(0, lastScrollY);
        }, 300);

        return true;
    }

    function bindEvents(container, header, contentBox) {
        // 拖拽
        let isDragging = false, startX, startY, initialLeft, initialTop;
        header.addEventListener('mousedown', (e) => {
            if(e.target.id === 'tm-toc-toggle') return;
            isDragging = true;
            startX = e.clientX; startY = e.clientY;
            const rect = container.getBoundingClientRect();
            initialLeft = rect.left; initialTop = rect.top;
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });
        function onMouseMove(e) {
            if (!isDragging) return;
            let newLeft = initialLeft + (e.clientX - startX);
            let newTop = initialTop + (e.clientY - startY);

            // --- 修复：限制拖拽边界，防止移出可视区域 ---
            const minLeft = 0;
            const minTop = 0;
            const maxLeft = Math.max(0, window.innerWidth - container.offsetWidth);
            const maxTop = Math.max(0, window.innerHeight - header.offsetHeight);

            newLeft = Math.max(minLeft, Math.min(newLeft, maxLeft));
            newTop = Math.max(minTop, Math.min(newTop, maxTop));

            container.style.left = `${newLeft}px`;
            container.style.top = `${newTop}px`;
        }
        function onMouseUp() {
            isDragging = false;
            const rect = container.getBoundingClientRect();
            Storage.set('pos', { top: rect.top, left: rect.left });
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        }

        // 折叠
        const toggleBtn = header.querySelector('#tm-toc-toggle');
        let isExpanded = contentBox.style.display !== 'none';
        toggleBtn.addEventListener('click', () => {
            if (isExpanded) {
                contentBox.style.display = 'none'; toggleBtn.innerText = '◀'; container.style.height = 'auto';
            } else {
                contentBox.style.display = 'block'; toggleBtn.innerText = '▼';
            }
            isExpanded = !isExpanded;
            Storage.set('expanded', isExpanded);
        });
    }

    // ==========================================
    // Core: SPA 监听与生命周期管理
    // ==========================================

    function init() {
        console.log('[LeetCode助手] 正在初始化...');

        let attempts = 0;
        if (checkContentTimer) clearInterval(checkContentTimer);

        // 轮询检测内容是否加载完毕
        checkContentTimer = setInterval(() => {
            attempts++;
            let isReady = false;

            if (location.pathname.startsWith('/problems/')) {
                // 如果是题目页，尝试渲染复制按钮
                if (renderCopyButton()) isReady = true;
            } else {
                // 如果是其他页（如discuss），尝试渲染目录
                if (renderTOC()) isReady = true;
            }

            // 如果成功渲染 或者 尝试超过10秒(20*500ms)，停止轮询
            if (isReady || attempts > 20) {
                clearInterval(checkContentTimer);
            }
        }, 500);
    }

    // 监听 URL 变化 (SPA 核心逻辑)
    setInterval(() => {
        if (location.pathname !== currentPath) {
            console.log(`[LeetCode助手] 页面跳转: ${currentPath} -> ${location.pathname}`);
            currentPath = location.pathname;
            removeTOC();
            init();
        }
    }, 1000);

    // 启动
    init();

    // ==========================================
    // Core 3: 自动刷新 & 位置保存
    // ==========================================

    window.addEventListener('beforeunload', () => {
        Storage.set('scrollY', window.scrollY);
    });

    function handleVisibilityChange() {
        const config = getConfig();
        if (document.hidden) {
            // 只有在discuss页面才考虑自动刷新
            if (location.pathname.includes('/discuss/')) {
                 refreshTimer = setTimeout(() => {
                     location.reload();
                 }, config.refreshInterval);
            }
        } else {
            if (refreshTimer) {
                clearTimeout(refreshTimer);
                refreshTimer = null;
            }
        }
    }
    document.addEventListener("visibilitychange", handleVisibilityChange);
    if (document.hidden) handleVisibilityChange();

})();