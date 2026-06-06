// ==UserScript==
// @name         LeetCode|力扣 原生计时器手动启动
// @namespace    http://tampermonkey.net/
// @version      1.0.0
// @description  阻止力扣题目页右上角原生计时器自动计时，只有手动点击计时器后才允许计时
// @author       0xff
// @match        *://leetcode.cn/problems/*
// @grant        none
// @license      MIT
// ==/UserScript==

(function () {
    'use strict';

    let currentPath = location.pathname;
    let userAllowedTimer = false;
    let checking = false;
    let observer = null;
    let loopTimer = null;

    const TIME_RE = /\b\d{1,2}:\d{2}(?::\d{2})?\b/;

    function isProblemPage() {
        return location.pathname.startsWith('/problems/');
    }

    function getTimeSeconds(text) {
        const match = text.match(TIME_RE);
        if (!match) return null;

        const parts = match[0].split(':').map(Number);

        if (parts.length === 2) {
            return parts[0] * 60 + parts[1];
        }

        if (parts.length === 3) {
            return parts[0] * 3600 + parts[1] * 60 + parts[2];
        }

        return null;
    }

    function isVisible(el) {
        if (!el) return false;

        const rect = el.getBoundingClientRect();

        return (
            rect.width > 0 &&
            rect.height > 0 &&
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.top < window.innerHeight &&
            rect.left < window.innerWidth
        );
    }

    function findNativeTimerButton() {
        const candidates = Array.from(document.querySelectorAll(`
            button,
            [role="button"],
            div[class*="timer"],
            div[class*="Timer"],
            span[class*="timer"],
            span[class*="Timer"]
        `));

        const timerCandidates = candidates.filter(el => {
            if (!isVisible(el)) return false;

            const text = el.innerText || el.textContent || '';
            if (!TIME_RE.test(text)) return false;

            const rect = el.getBoundingClientRect();

            return (
                rect.top < 120 &&
                rect.left > window.innerWidth * 0.45
            );
        });

        if (timerCandidates.length === 0) return null;

        timerCandidates.sort((a, b) => {
            const ar = a.getBoundingClientRect();
            const br = b.getBoundingClientRect();

            return br.left - ar.left;
        });

        let el = timerCandidates[0];

        const clickable = el.closest('button, [role="button"]');
        return clickable || el;
    }

    function nativeClick(el) {
        if (!el) return;

        el.dispatchEvent(new MouseEvent('mousedown', {
            bubbles: true,
            cancelable: true,
            view: window
        }));

        el.dispatchEvent(new MouseEvent('mouseup', {
            bubbles: true,
            cancelable: true,
            view: window
        }));

        el.dispatchEvent(new MouseEvent('click', {
            bubbles: true,
            cancelable: true,
            view: window
        }));
    }

    async function pauseIfNativeTimerRunning() {
        if (!isProblemPage()) return;
        if (userAllowedTimer) return;
        if (checking) return;

        const btn = findNativeTimerButton();
        if (!btn) return;

        const text1 = btn.innerText || btn.textContent || '';
        const t1 = getTimeSeconds(text1);

        if (t1 === null) return;

        checking = true;

        await new Promise(resolve => setTimeout(resolve, 1300));

        if (!isProblemPage() || userAllowedTimer) {
            checking = false;
            return;
        }

        const btn2 = findNativeTimerButton();
        if (!btn2) {
            checking = false;
            return;
        }

        const text2 = btn2.innerText || btn2.textContent || '';
        const t2 = getTimeSeconds(text2);

        if (t2 !== null && t2 > t1) {
            nativeClick(btn2);
        }

        checking = false;
    }

    function bindUserClickDetector() {
        document.addEventListener('click', e => {
            const btn = findNativeTimerButton();
            if (!btn) return;

            if (btn === e.target || btn.contains(e.target)) {
                userAllowedTimer = true;
            }
        }, true);
    }

    function startWatcher() {
        stopWatcher();

        observer = new MutationObserver(() => {
            pauseIfNativeTimerRunning();
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
            characterData: true
        });

        loopTimer = setInterval(() => {
            pauseIfNativeTimerRunning();

            if (location.pathname !== currentPath) {
                currentPath = location.pathname;
                userAllowedTimer = false;
                checking = false;

                setTimeout(() => {
                    pauseIfNativeTimerRunning();
                }, 800);
            }
        }, 1000);

        setTimeout(() => {
            pauseIfNativeTimerRunning();
        }, 800);

        setTimeout(() => {
            pauseIfNativeTimerRunning();
        }, 2000);
    }

    function stopWatcher() {
        if (observer) {
            observer.disconnect();
            observer = null;
        }

        if (loopTimer) {
            clearInterval(loopTimer);
            loopTimer = null;
        }
    }

    bindUserClickDetector();
    startWatcher();

})();