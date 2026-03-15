import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/4.3.0/marked.min.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
<style>
    body { 
        margin: 0; 
        padding: 10px 10px 15px 10px; 
        font-family: "Microsoft YaHei", sans-serif; 
        background-color: transparent !important; 
        overflow: hidden; 
        box-sizing: border-box; 
    }
    
    #chat-container {
        position: relative;
        width: 100%;
        min-height: 80px; 
    }

    /* ====== 卡片核心样式：改为清新的护眼绿 ====== */
    .card {
        position: absolute;
        top: 0; 
        left: 0;
        width: 100%;
        /* 护眼浅绿色背景 */
        background: #f0fdf4; 
        /* 边框改为偏绿的过渡色 */
        border: 1px solid rgba(134, 239, 172, 0.6);
        border-radius: 14px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
        box-sizing: border-box;
        transition: transform 0.45s cubic-bezier(0.2, 0.9, 0.3, 1.1),
                    opacity 0.4s ease, filter 0.4s ease;
        transform-origin: top center;
        max-height: 320px;
        display: flex;
        flex-direction: column;
    }

    /* 卡片头部（问题部分）：稍微深一点的绿色区分层次 */
    .question-header {
        font-size: 13px;
        font-weight: 600;
        color: #166534; /* 深绿色字体 */
        background: #dcfce7; /* 稍深的薄荷绿底色 */
        padding: 10px 14px;
        border-radius: 14px 14px 0 0;
        border-bottom: 1px solid rgba(134, 239, 172, 0.4);
        white-space: nowrap;
        overflow-wrap: anywhere;
        word-break: break-word;
        overflow: hidden;
        text-overflow: ellipsis;
        flex-shrink: 0;
    }
    
    .card[data-active="true"] .question-header {
        white-space: normal;
    }

    /* AI回答主体 */
    .answer-body {
        font-size: 13px;
        line-height: 1.6;
        color: #333;
        padding: 12px 14px;
        overflow-y: auto;
        overflow-wrap: anywhere;
        word-break: break-word;
        flex-grow: 1;
    }
    
    .card[data-active="false"] .answer-body { display: none; }
    
    /* 滚动条也染成一点点绿色 */
    .answer-body::-webkit-scrollbar { width: 4px; }
    .answer-body::-webkit-scrollbar-thumb { background: rgba(34, 197, 94, 0.2); border-radius: 2px; }

    .answer-body p { margin: 0 0 8px 0; }
    .answer-body p:last-child { margin: 0; }
    .katex-display { overflow-x: auto; overflow-y: hidden; padding: 5px 0; margin: 0; }

    .plan-proposal {
        margin-top: 10px;
        padding-top: 10px;
        border-top: 1px dashed rgba(134, 239, 172, 0.7);
        font-size: 12px;
        color: #14532d;
    }
    .plan-title { font-weight: 700; margin-bottom: 4px; color: #166534; }
    .plan-summary { color: #166534; opacity: 0.85; margin-bottom: 6px; }
    .plan-meta { font-size: 11px; color: #166534; opacity: 0.75; margin-bottom: 6px; }
    .plan-list { padding-left: 14px; margin: 0 0 6px 0; }
    .plan-list li { margin: 0 0 4px 0; }
    .plan-actions { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }
    .plan-btn {
        border: 1px solid rgba(34, 197, 94, 0.5);
        background: #ecfdf3;
        color: #166534;
        border-radius: 10px;
        padding: 4px 8px;
        font-size: 11px;
        cursor: pointer;
    }
    .plan-btn[disabled] { opacity: 0.6; cursor: default; }
    .plan-status { font-size: 11px; color: #166534; opacity: 0.8; margin-top: 4px; }
    .plan-banner {
        display: none;
        margin-bottom: 8px;
        padding: 8px 10px;
        border-radius: 10px;
        background: #ecfdf3;
        border: 1px solid rgba(34, 197, 94, 0.4);
        color: #166534;
        font-size: 12px;
    }
    .plan-banner-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
    }
    .plan-banner-actions { display: flex; gap: 6px; flex-wrap: wrap; }
    .plan-actions { display: none; }
    .plan-banner-actions { display: none; }
</style>
</head>
<body>
    <div id="plan-status-banner" class="plan-banner">
        <div class="plan-banner-row">
            <span class="plan-banner-text"></span>
            <div class="plan-banner-actions"></div>
        </div>
    </div>
    <div id="chat-container"></div>
    <script>
        window.onload = function() {
            try { if (typeof marked !== 'undefined' && marked.setOptions) marked.setOptions({ breaks: true }); } catch (e) {}
        };

        let cards = []; 
        let activeIndex = -1; 
        
        function recalculateHeight() {
            if (cards.length === 0 || activeIndex < 0) return;
            const activeCard = cards[activeIndex];
            const visible_behind = Math.min(activeIndex, 4);
            const banner = document.getElementById('plan-status-banner');
            const bannerVisible = banner && banner.style.display !== 'none';
            const bannerHeight = bannerVisible ? (banner.offsetHeight + 8) : 0;
            const totalHeight = bannerHeight + (visible_behind * 35) + activeCard.offsetHeight + 10;

            document.getElementById('chat-container').style.height = totalHeight + 'px';
            document.title = "HEIGHT:" + totalHeight; 
        }

        window.renderMarkdownAndMath = function(text) {
            let html = text;
            try {
                // 👇 核心修复：过滤掉大模型的深度思考标签（如 <think>）及其内部的所有流式文字
                let temp = text.replace(/<(think|thought)>[\s\S]*?(<\/\1>|$)/gi, '').trim();

                let mathBlocks = [];
                temp = temp.replace(/(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\])/g, function(match) {
                    let content = match.startsWith('$$') ? match.slice(2, -2) : match.slice(2, -2);
                    mathBlocks.push({ display: true, math: content });
                    return '@@MATH_TOKEN_' + (mathBlocks.length - 1) + '@@';
                });
                temp = temp.replace(/(\$[^$\n]+?\$|\\\([\s\S]+?\\\))/g, function(match) {
                    let content = match.startsWith('$') ? match.slice(1, -1) : match.slice(2, -2);
                    mathBlocks.push({ display: false, math: content });
                    return '@@MATH_TOKEN_' + (mathBlocks.length - 1) + '@@';
                });
                if (typeof marked !== 'undefined') html = marked.parse(temp);
                else html = temp;
                mathBlocks.forEach((item, i) => {
                    let rendered = item.math;
                    if (typeof katex !== 'undefined') {
                        try { rendered = katex.renderToString(item.math, { displayMode: item.display, throwOnError: false }); } catch(e) {}
                    }
                    html = html.replace('@@MATH_TOKEN_' + i + '@@', item.display ? `<p>${rendered}</p>` : rendered);
                });
            } catch (error) { html = text; }
            return html;
        };

        function updateStack() {
            if (cards.length === 0) return;
            if (activeIndex < 0) activeIndex = 0;
            if (activeIndex >= cards.length) activeIndex = cards.length - 1;

            const visible_behind = Math.min(activeIndex, 4); 

            cards.forEach((card, i) => {
                let dist = activeIndex - i; 

                if (dist === 0) {
                    card.style.transform = `translateY(${visible_behind * 35}px) scale(1)`;
                    card.style.zIndex = 30;
                    card.style.opacity = 1;
                    card.style.filter = 'brightness(1)';
                    card.setAttribute('data-active', 'true');
                } else if (dist > 0 && dist <= 4) {
                    let posIndex = visible_behind - dist; 
                    let scale = 1 - (dist * 0.04);
                    card.style.transform = `translateY(${posIndex * 35}px) scale(${scale})`;
                    card.style.zIndex = 30 - dist;
                    card.style.opacity = 1;
                    card.style.filter = `brightness(${1 - dist * 0.06})`;
                    card.setAttribute('data-active', 'false');
                } else if (dist < 0) {
                    card.style.transform = `translateY(150%) scale(1.05)`;
                    card.style.zIndex = 40; 
                    card.style.opacity = 0;
                    card.setAttribute('data-active', 'false');
                } else {
                    card.style.transform = `translateY(-30px) scale(0.8)`;
                    card.style.opacity = 0;
                }
            });
            setTimeout(recalculateHeight, 50); 
        }

        let wheelTimer = null;
        window.addEventListener('wheel', (e) => {
            if (cards.length <= 1) return;
            
            const activeCard = cards[activeIndex];
            if (activeCard && activeCard.contains(e.target)) {
                const body = activeCard.querySelector('.answer-body');
                if (body && body.scrollHeight > body.clientHeight) {
                    if (e.deltaY > 0 && body.scrollTop + body.clientHeight < body.scrollHeight - 1) return;
                    if (e.deltaY < 0 && body.scrollTop > 0) return;
                }
            }
            
            if (wheelTimer) return;
            
            if (e.deltaY < -15) {
                if (activeIndex > 0) {
                    activeIndex--;
                    updateStack();
                    wheelTimer = setTimeout(() => wheelTimer = null, 350);
                }
            } else if (e.deltaY > 15) {
                if (activeIndex < cards.length - 1) {
                    activeIndex++;
                    updateStack();
                    wheelTimer = setTimeout(() => wheelTimer = null, 350);
                }
            }
        });

        window._createMessageRow = function(text, isUser, messageId) {
            const container = document.getElementById('chat-container');

            if (isUser) {
                // 全局记录下用户最后一次发送的提问文本
                window._lastUserQuestion = text;

                const card = document.createElement('div');
                card.className = 'card';
                card.innerHTML = `
                    <div class="question-header">🤔 ${text}</div>
                    <div class="answer-body" data-node="pending"><span style="color:#22c55e; font-style:italic;">💭 意图识别中...</span></div>
                `;
                
                if (cards.length >= 5) {
                    let old = cards.shift();
                    if (old && old.parentNode) old.parentNode.removeChild(old);
                    activeIndex--; 
                }
                
                container.appendChild(card);
                cards.push(card);
                activeIndex = cards.length - 1; 
                updateStack();
            } else {
                if (cards.length === 0) return;
                const activeCard = cards[cards.length - 1]; 
                let aDiv = activeCard.querySelector('.answer-body');
                if (messageId) activeCard.setAttribute('data-id', messageId);
                if (text) {
                    aDiv.innerHTML = window.renderMarkdownAndMath(text);
                    aDiv.setAttribute('data-raw', text);
                } else {
                    aDiv.innerHTML = ''; 
                }
            }
        };

        window.startAssistantMessage = function(messageId) {
            // 尝试复用最后一张卡片（也就是用户刚刚提问生成的那张）
            if (cards.length > 0) {
                const lastCard = cards[cards.length - 1];
                // 如果最后一张卡片还没有绑定 data-id，说明它正是等待回答的提问卡片
                if (!lastCard.hasAttribute('data-id')) {
                    if (messageId) lastCard.setAttribute('data-id', messageId);
                    return; // 成功复用，直接退出，不再生成多余的新卡片
                }
            }

            // 保底逻辑：只有在特殊情况（没有旧卡片）时，才创建新卡片
            const card = document.createElement('div');
            card.className = 'card';
            
            // 获取刚才记录的用户问题（如果没有记录到，则保底显示 'AI 回答'）
            const questionTitle = window._lastUserQuestion || 'AI 回答';

            card.innerHTML = `
                <div class="question-header">💬 ${questionTitle}</div>
                <div class="answer-body" data-node="waiting"><span style="color:#22c55e; font-style:italic;">💭 处理中...</span></div>
            `;

            const container = document.getElementById('chat-container');
            if (cards.length >= 5) {
                let old = cards.shift();
                if (old && old.parentNode) old.parentNode.removeChild(old);
            }

            container.appendChild(card);
            cards.push(card);
            if (messageId) card.setAttribute('data-id', messageId);
            
            activeIndex = cards.length - 1;
            
            updateStack();
        };

        window.clearChat = function() {
            cards = [];
            activeIndex = -1;
            const container = document.getElementById('chat-container');
            if (container) container.innerHTML = '';
            recalculateHeight();
        };

        window.appendAssistantDelta = function(messageId, chunk) {
            const card = document.querySelector(`.card[data-id="${messageId}"]`) || cards[cards.length - 1];
            if (!card) return;
            const aDiv = card.querySelector('.answer-body');
            const nextRaw = (aDiv.getAttribute('data-raw') || '') + (chunk || '');
            aDiv.setAttribute('data-raw', nextRaw);
            aDiv.innerHTML = window.renderMarkdownAndMath(nextRaw);
            // 清除 node 状态标记，因为已经开始显示内容了
            aDiv.removeAttribute('data-node');
            recalculateHeight();
        };

        window.updateNodeStatus = function(messageId, nodeName) {
            // 只更新 AI 卡片（通过 messageId 查找），不更新用户卡片
            let card = null;

            if (messageId) {
                card = document.querySelector(`.card[data-id="${messageId}"]`);
            }

            if (!card) {
                for (let i = cards.length - 1; i >= 0; i--) {
                    if (cards[i].hasAttribute('data-id')) {
                        card = cards[i];
                        break;
                    }
                }
            }

            if (!card) {
                card = cards[cards.length - 1];
            }

            if (!card) return;
            const aDiv = card.querySelector('.answer-body');
            if (!aDiv) return;

            // 将 node_name 转换为中文显示名称
            const nodeNames = {
                'tutor_answer': '📚 答疑',
                'judge': '⚖️ 评审',
                'inquiry': '🔍 探究',
                'summary': '📝 总结',
                'plan': '📋 计划',
                'concluding': '👋 结语'
            };

            const displayName = nodeNames[nodeName] || nodeName;
            aDiv.setAttribute('data-node', nodeName);
            aDiv.innerHTML = `<span style="color:#22c55e; font-style:italic;">💭 ${displayName} 正在思考...</span>`;
            recalculateHeight();
        };

        window.finishAssistantMessage = function(messageId) {
            const card = document.querySelector(`.card[data-id="${messageId}"]`) || cards[cards.length - 1];
            if (!card) return;
            const aDiv = card.querySelector('.answer-body');
            aDiv.innerHTML = window.renderMarkdownAndMath(aDiv.getAttribute('data-raw') || '');
            recalculateHeight();
        };

        window.updateIntentStatus = function(intentText) {
            // 更新最新用户卡片的意图识别结果显示，并持久化保持
            const userCard = cards[cards.length - 1];
            if (!userCard) return;
            const aDiv = userCard.querySelector('.answer-body');
            if (!aDiv) return;

            // 将模块名转换为中文显示
            const moduleNames = {
                'tutor_answer': '📚 答疑',
                'judge': '⚖️ 评审',
                'inquiry': '🔍 探究',
                'summary': '📝 总结',
                'plan': '📋 计划',
                'concluding': '👋 结语',
                '闲聊': '💬 闲聊'
            };

            // 解析模块列表并转换
            let displayText = intentText;
            const modules = intentText.split(' + ');
            const converted = modules.map(m => moduleNames[m] || m);
            displayText = converted.join(' + ');

            // 设置为最终状态，不再被覆盖
            aDiv.setAttribute('data-node', 'intent_done');
            aDiv.innerHTML = `<span style="color:#22c55e; font-weight:600;">✅ ${displayText}</span>`;
            recalculateHeight();
        };
        function findAssistantCard(messageId) {
            if (messageId) {
                const byId = document.querySelector(`.card[data-id="${messageId}"]`);
                if (byId) return byId;
            }
            for (let i = cards.length - 1; i >= 0; i--) {
                if (cards[i].hasAttribute('data-id')) return cards[i];
            }
            return cards[cards.length - 1] || null;
        }

        function renderPlanStatus(status) {
            if (!status) return "";
            const statusMap = {
                "await_confirm": "计划待确认",
                "await_plan_confirm": "计划待确认",
                "collecting": "计划调整中",
                "paused": "计划已挂起"
            };
            return statusMap[status] || status;
        }

        window.updatePlanStatusBanner = function(status) {
            const banner = document.getElementById('plan-status-banner');
            if (!banner) return;
            const textEl = banner.querySelector('.plan-banner-text');
            const actionsEl = banner.querySelector('.plan-banner-actions');
            if (!textEl || !actionsEl) return;

            if (!status || status === "idle") {
                banner.style.display = "none";
                textEl.textContent = "";
                actionsEl.innerHTML = "";
                recalculateHeight();
                return;
            }

            let text = "";
            const actions = [];
            if (status === "paused") {
                text = "计划已挂起，可继续调整或结束计划。";
                actions.push(`<button class="plan-btn" onclick="window._petPlanAction('resume', this)">继续调整</button>`);
                actions.push(`<button class="plan-btn" onclick="window._petPlanAction('exit', this)">结束计划</button>`);
            } else if (status === "await_confirm" || status === "await_plan_confirm" || status === "collecting") {
                text = "当前处于计划调整中，可随时结束计划。";
                actions.push(`<button class="plan-btn" onclick="window._petPlanAction('exit', this)">结束计划</button>`);
            } else {
                text = `计划状态：${renderPlanStatus(status)}`;
            }

            textEl.textContent = text;
            actionsEl.innerHTML = actions.join("");
            banner.style.display = "block";
            recalculateHeight();
        };

        window.updatePlanStatus = function(status, messageId) {
            const card = findAssistantCard(messageId);
            if (!card) return;
            const wrap = card.querySelector('.plan-proposal');
            if (!wrap) return;
            const statusEl = wrap.querySelector('.plan-status');
            if (!statusEl) return;
            const label = renderPlanStatus(status);
            statusEl.textContent = label ? `状态：${label}` : "";
            recalculateHeight();
        };

        window.updatePlanConfirmState = function(ok, errorText, messageId) {
            const card = findAssistantCard(messageId);
            if (!card) return;
            const wrap = card.querySelector('.plan-proposal');
            if (!wrap) return;
            const btn = wrap.querySelector('[data-action="confirm"]');
            const msg = wrap.querySelector('.plan-confirm-msg');
            if (ok) {
                if (btn) btn.setAttribute('disabled', 'true');
                if (msg) msg.textContent = "已更新";
            } else {
                if (btn) btn.removeAttribute('disabled');
                if (msg) msg.textContent = errorText ? String(errorText) : "更新失败";
            }
            recalculateHeight();
        };

        window._petPlanAction = function(action, btn) {
            const card = btn ? btn.closest('.card') : findAssistantCard();
            const messageId = card ? (card.getAttribute('data-id') || "") : "";
            if (action === "confirm" && btn) {
                btn.setAttribute('disabled', 'true');
                const msg = card ? card.querySelector('.plan-confirm-msg') : null;
                if (msg) msg.textContent = "更新中...";
            }
            const mid = messageId ? `?mid=${encodeURIComponent(messageId)}` : "";
            window.location.href = `pet://plan/${action}${mid}`;
        };

        window.updatePlanCard = function(plan, status, messageId) {
            const card = findAssistantCard(messageId);
            if (!card) return;
            if (messageId) {
                card.setAttribute('data-id', messageId);
            } else if (!card.getAttribute('data-id')) {
                card.setAttribute('data-id', `plan-${Date.now()}`);
            }
            const aDiv = card.querySelector('.answer-body');
            if (!aDiv) return;

            let wrap = aDiv.querySelector('.plan-proposal');
            if (!wrap) {
                wrap = document.createElement('div');
                wrap.className = 'plan-proposal';
                aDiv.appendChild(wrap);
            }

            const hasPlan = plan && typeof plan === 'object';
            const stepsRaw = hasPlan ? plan.plan : null;
            let steps = [];
            if (Array.isArray(stepsRaw)) {
                steps = stepsRaw.map((i) => String(i)).filter((i) => i.trim());
            } else if (typeof stepsRaw === 'string') {
                steps = stepsRaw.split(/\r?\n|[；;]+/).map((i) => i.trim()).filter(Boolean);
            }

            const title = hasPlan ? (plan.taskTitle || "学习计划") : "学习计划";
            const summary = hasPlan ? (plan.overallSummary || "") : "";
            const totalDays = hasPlan && plan.totalDays ? `${plan.totalDays} 天` : "";
            const totalHours = hasPlan && plan.totalHours ? `${plan.totalHours} 小时` : "";
            const meta = [totalDays, totalHours].filter(Boolean).join(" · ");
            const statusLabel = renderPlanStatus(status);

            const listHtml = steps.length
                ? `<ul class="plan-list">${steps.map((s) => `<li>• ${s}</li>`).join("")}</ul>`
                : "";

            const actions = [];
            if (hasPlan) {
                actions.push(`<button class="plan-btn" data-action="confirm" onclick="window._petPlanAction('confirm', this)">确认更新</button>`);
            }
            if (status === "paused") {
                actions.push(`<button class="plan-btn" onclick="window._petPlanAction('resume', this)">继续调整</button>`);
                actions.push(`<button class="plan-btn" onclick="window._petPlanAction('exit', this)">结束计划</button>`);
            } else if (status === "await_confirm" || status === "await_plan_confirm" || status === "collecting") {
                actions.push(`<button class="plan-btn" onclick="window._petPlanAction('exit', this)">结束计划</button>`);
            }

            wrap.innerHTML = `
                <div class="plan-title">${title}</div>
                ${summary ? `<div class="plan-summary">${summary}</div>` : ""}
                ${meta ? `<div class="plan-meta">${meta}</div>` : ""}
                ${listHtml}
                <div class="plan-actions">${actions.join("")}</div>
                <div class="plan-status">${statusLabel ? `状态：${statusLabel}` : ""}</div>
                <div class="plan-confirm-msg" style="font-size:11px;color:#166534;opacity:0.8;"></div>
            `;
            recalculateHeight();
        };
    </script>
</body>
</html>
"""
