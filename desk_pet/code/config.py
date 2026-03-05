# desk_pet/code/config.py
import os

# 基础路径：由于 config.py 在 code 文件夹内，需要回退一级才能指向 desk_pet 文件夹
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdn.staticfile.net/marked/12.0.1/marked.min.js"></script>
<link rel="stylesheet" href="https://cdn.staticfile.net/KaTeX/0.16.9/katex.min.css">
<script src="https://cdn.staticfile.net/KaTeX/0.16.9/katex.min.js"></script>
<style>
    body { margin: 0; padding: 10px; font-family: "Microsoft YaHei", sans-serif; background-color: transparent !important; display: flex; flex-direction: column; overflow-x: hidden; overflow-y: auto; min-height: calc(100vh - 20px); box-sizing: border-box; }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.15); border-radius: 3px; }
    #chat-container { display: flex; flex-direction: column; gap: 12px; flex: 1; justify-content: flex-end; }
    .msg-row { display: flex; width: 100%; transition: opacity 0.4s ease-in-out; }
    .msg-row.user { justify-content: flex-end; }
    .msg-row.ai { justify-content: flex-start; }
    .bubble { max-width: 88%; padding: 10px 14px; border-radius: 12px; font-size: 13px; line-height: 1.6; color: #333; word-wrap: break-word; overflow-x: auto; }
    .msg-row.user .bubble { background-color: #95ec69; }
    .msg-row.ai .bubble { background-color: #ffffff; border: 1px solid #e0e0e0; }
    .bubble p { margin: 0 0 8px 0; }
    .bubble p:last-child { margin: 0; }
    .katex-display { overflow-x: auto; overflow-y: hidden; padding: 5px 0; margin: 0; }
    body:not(.hovered) .msg-row.old-4 { opacity: 0.05; }
    body:not(.hovered) .msg-row.old-3 { opacity: 0.25; }
    body:not(.hovered) .msg-row.old-2 { opacity: 0.70; }
    body:not(.hovered) .msg-row.old-1 { opacity: 1.0; }
    body:not(.hovered) .msg-row.too-old { opacity: 0; display: none; }
</style>
</head>
<body>
    <div id="chat-container"></div>
    <script>
        marked.setOptions({ breaks: true });

        function renderMarkdownAndMath(text) {
            let mathBlocks = [];
            
            // 1. 提取块级公式
            let temp = text.replace(/(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\])/g, function(match) {
                let content = match.startsWith('$$') ? match.slice(2, -2) : match.slice(2, -2);
                mathBlocks.push({ display: true, math: content });
                return '@@MATH_TOKEN_' + (mathBlocks.length - 1) + '@@';
            });
            
            // 2. 提取行内公式
            temp = temp.replace(/(\$[^$\n]+?\$|\\\( [\s\S]+?\\\))/g, function(match) {
                let content = match.startsWith('$') ? match.slice(1, -1) : match.slice(2, -2);
                mathBlocks.push({ display: false, math: content });
                return '@@MATH_TOKEN_' + (mathBlocks.length - 1) + '@@';
            });
            
            // 3. 解析 Markdown
            let html = marked.parse(temp);
            
            // 4. KaTeX 渲染并还原
            mathBlocks.forEach((item, i) => {
                let rendered = "";
                try {
                    rendered = katex.renderToString(item.math, {
                        displayMode: item.display,
                        throwOnError: false
                    });
                } catch(e) {
                    rendered = item.math;
                }
                
                const token = '@@MATH_TOKEN_' + i + '@@';
                if (item.display) {
                    html = html.replace('<p>' + token + '</p>', rendered);
                }
                html = html.replace(token, rendered);
            });
            
            return html;
        }

        function _createMessageRow(text, isUser, messageId) {
            const container = document.getElementById('chat-container');
            const row = document.createElement('div');
            row.className = 'msg-row ' + (isUser ? 'user' : 'ai');
            if (messageId) row.setAttribute('data-id', messageId);
            const bubble = document.createElement('div');
            bubble.className = 'bubble';
            if(isUser) bubble.innerText = text; else bubble.innerHTML = renderMarkdownAndMath(text);
            row.appendChild(bubble);
            container.appendChild(row);
            updateOpacities();
            setTimeout(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }), 50);
            return row;
        }

        function addMessage(text, isUser) {
            _createMessageRow(text, isUser, null);
        }

        function startAssistantMessage(messageId) {
            _createMessageRow('', false, messageId);
        }

        function appendAssistantDelta(messageId, chunk) {
            const row = document.querySelector(`.msg-row[data-id="${messageId}"]`);
            if (!row) return;
            const bubble = row.querySelector('.bubble');
            if (!bubble) return;
            const prevRaw = bubble.getAttribute('data-raw') || '';
            const nextRaw = prevRaw + (chunk || '');
            bubble.setAttribute('data-raw', nextRaw);
            bubble.innerHTML = renderMarkdownAndMath(nextRaw);
            setTimeout(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }), 20);
        }

        function finishAssistantMessage(messageId) {
            const row = document.querySelector(`.msg-row[data-id="${messageId}"]`);
            if (!row) return;
            const bubble = row.querySelector('.bubble');
            if (!bubble) return;
            const raw = bubble.getAttribute('data-raw') || '';
            bubble.innerHTML = renderMarkdownAndMath(raw);
        }

        function updateOpacities() {
            const rows = document.querySelectorAll('.msg-row');
            const len = rows.length;
            rows.forEach((row, i) => {
                row.classList.remove('old-1', 'old-2', 'old-3', 'old-4', 'too-old');
                const reverseIndex = len - 1 - i;
                if (reverseIndex === 0) row.classList.add('old-1');
                else if (reverseIndex === 1) row.classList.add('old-2');
                else if (reverseIndex === 2) row.classList.add('old-3');
                else if (reverseIndex === 3) row.classList.add('old-4');
                else row.classList.add('too-old');
            });
        }

        function setHover(isHover) {
            if(isHover) document.body.classList.add('hovered'); else document.body.classList.remove('hovered');
            window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
        }
    </script>
</body>
</html>
"""