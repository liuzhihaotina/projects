// ==UserScript==
// @name         LeetCode|力扣 题单多功能目录插件
// @license MIT
// @namespace    http://tampermonkey.net/
// @version      1.0.3
// @description  自动生成题单目录+一键跳转+自动标记已做题目+自动跳转到上一次浏览位置+题目标题一键复制
// @author       0xff (Fixed by Assistant)
// @match        *://leetcode.cn/discuss/*
// @match        *://leetcode.cn/problems/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=leetcode.cn
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    let tocContainer = null;
    let currentPath = location.pathname;
    let checkContentTimer = null;
    let refreshTimer = null;

    const getConfig = () => ({
        title: "大纲目录",
        width: 240,
        indent: 20,
        bgColor: "#ffffff",
        textColor: "#37352f",
        hoverColor: "#f0f0f0",
        keyPrefix: "tm_toc_save_" + location.pathname,
        refreshInterval: 5 * 60 * 1000
    });

    const getDefaultPos = () => {
        const config = getConfig();
        return {
            top: 100,
            left: Math.max(20, window.innerWidth - config.width - 20)
        };
    };

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

    function renderCopyButton() {
        if (!location.pathname.startsWith('/problems/')) return false;
        if (document.getElementById('tm-lc-copy-btn')) return true;

        const titleContainer = document.querySelector('.text-title-large');
        const titleLink = titleContainer ? titleContainer.querySelector('a') : null;

        if (!titleContainer || !titleLink) return false;

        const btn = document.createElement('div');
        btn.id = 'tm-lc-copy-btn';
        btn.style.cssText = `
            display: inline-flex; align-items: center; justify-content: center;
            margin-left: 8px; cursor: pointer; color: #9ca3af;
            width: 24px; height: 24px; border-radius: 4px; transition: all 0.2s;
            vertical-align: middle;
        `;

        const copyIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
        const checkIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;

        btn.innerHTML = copyIcon;
        btn.title = "复制 Markdown (标题+链接图标)";

        btn.onmouseenter = () => {
            btn.style.backgroundColor = 'rgba(0,0,0,0.05)';
            btn.style.color = '#333';
        };

        btn.onmouseleave = () => {
            btn.style.backgroundColor = 'transparent';
            btn.style.color = '#9ca3af';
        };

        btn.onclick = (e) => {
            e.preventDefault();
            e.stopPropagation();

            let text = titleLink.innerText.trim();
            text = text.replace(/^\d+\.\s*/, '');

            const url = titleLink.href;
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

        titleContainer.appendChild(btn);
        return true;
    }

    function removeTOC() {
        if (tocContainer && tocContainer.parentNode) {
            tocContainer.parentNode.removeChild(tocContainer);
        }
        tocContainer = null;
    }

    function renderTOC() {
        const headings = document.querySelectorAll('h2, h3');
        if (headings.length === 0) return false;

        removeTOC();

        const config = getConfig();
        const savedPos = Storage.get('pos', getDefaultPos());
        const savedState = Storage.get('expanded', true);

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

            const style = document.createElement('style');
            style.id = 'tm-toc-style';
            style.innerHTML = css;
            document.head.appendChild(style);
        }

        const container = document.createElement('div');
        container.id = 'tm-toc-container';

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

        bindEvents(container, header, contentBox);

        setTimeout(() => {
            const lastScrollY = Storage.get('scrollY', 0);
            if (lastScrollY > 0) window.scrollTo(0, lastScrollY);
        }, 300);

        return true;
    }

    function bindEvents(container, header, contentBox) {
        let isDragging = false, startX, startY, initialLeft, initialTop;

        header.addEventListener('mousedown', (e) => {
            if (e.target.id === 'tm-toc-toggle') return;

            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;

            const rect = container.getBoundingClientRect();
            initialLeft = rect.left;
            initialTop = rect.top;

            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });

        function onMouseMove(e) {
            if (!isDragging) return;

            let newLeft = initialLeft + (e.clientX - startX);
            let newTop = initialTop + (e.clientY - startY);

            const maxLeft = Math.max(0, window.innerWidth - container.offsetWidth);
            const maxTop = Math.max(0, window.innerHeight - header.offsetHeight);

            newLeft = Math.max(0, Math.min(newLeft, maxLeft));
            newTop = Math.max(0, Math.min(newTop, maxTop));

            container.style.left = `${newLeft}px`;
            container.style.top = `${newTop}px`;
        }

        function onMouseUp() {
            isDragging = false;

            const rect = container.getBoundingClientRect();
            Storage.set('pos', {
                top: rect.top,
                left: rect.left
            });

            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        }

        const toggleBtn = header.querySelector('#tm-toc-toggle');
        let isExpanded = contentBox.style.display !== 'none';

        toggleBtn.addEventListener('click', () => {
            if (isExpanded) {
                contentBox.style.display = 'none';
                toggleBtn.innerText = '◀';
                container.style.height = 'auto';
            } else {
                contentBox.style.display = 'block';
                toggleBtn.innerText = '▼';
            }

            isExpanded = !isExpanded;
            Storage.set('expanded', isExpanded);
        });
    }

    function init() {
        console.log('[LeetCode助手] 正在初始化...');

        let attempts = 0;
        if (checkContentTimer) clearInterval(checkContentTimer);

        checkContentTimer = setInterval(() => {
            attempts++;
            let isReady = false;

            if (location.pathname.startsWith('/problems/')) {
                if (renderCopyButton()) isReady = true;
            } else {
                if (renderTOC()) isReady = true;
            }

            if (isReady || attempts > 20) {
                clearInterval(checkContentTimer);
            }
        }, 500);
    }

    setInterval(() => {
        if (location.pathname !== currentPath) {
            console.log(`[LeetCode助手] 页面跳转: ${currentPath} -> ${location.pathname}`);
            currentPath = location.pathname;
            removeTOC();
            init();
        }
    }, 1000);

    init();

    window.addEventListener('beforeunload', () => {
        Storage.set('scrollY', window.scrollY);
    });

    function handleVisibilityChange() {
        const config = getConfig();

        if (document.hidden) {
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