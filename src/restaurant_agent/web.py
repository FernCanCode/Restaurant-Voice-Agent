"""Browser UI module for the restaurant voice ordering agent."""


def render_browser_ui() -> str:
    """Render the simple browser UI for voice ordering."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Restaurant Voice Ordering Agent</title>
    <style>
        :root {
            --bg-dark: #0f172a;
            --bg-glass: rgba(30, 41, 59, 0.7);
            --border-glass: rgba(255, 255, 255, 0.1);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #3b82f6;
            --accent-hover: #60a5fa;
            --danger: #ef4444;
            --success: #10b981;
        }

        body {
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: linear-gradient(135deg, #020617 0%, #0f172a 100%);
            color: var(--text-main);
            margin: 0;
            padding: 2rem;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .container {
            width: 100%;
            max-width: 1000px;
            display: grid;
            grid-template-columns: 1fr 350px;
            gap: 1.5rem;
        }

        @media (max-width: 768px) {
            .container {
                grid-template-columns: 1fr;
            }
        }

        .panel {
            background: var(--bg-glass);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border-glass);
            border-radius: 1rem;
            padding: 1.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }

        .header {
            grid-column: 1 / -1;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }

        h1 {
            font-size: 1.5rem;
            font-weight: 600;
            margin: 0;
            background: linear-gradient(to right, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        h2 {
            font-size: 1.1rem;
            font-weight: 500;
            margin-top: 0;
            margin-bottom: 1rem;
            color: var(--text-muted);
            border-bottom: 1px solid var(--border-glass);
            padding-bottom: 0.5rem;
        }

        button {
            background-color: var(--accent);
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 0.5rem;
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.3);
        }

        button:hover {
            background-color: var(--accent-hover);
            transform: translateY(-1px);
            box-shadow: 0 0 20px rgba(59, 130, 246, 0.5);
        }

        button:disabled {
            background-color: var(--text-muted);
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        button.danger {
            background-color: var(--danger);
            box-shadow: 0 0 15px rgba(239, 68, 68, 0.3);
        }

        button.danger:hover {
            background-color: #f87171;
            box-shadow: 0 0 20px rgba(239, 68, 68, 0.5);
        }

        .transcript {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            height: 400px;
            overflow-y: auto;
            padding-right: 0.5rem;
            margin-bottom: 1rem;
        }

        /* Scrollbar styles */
        ::-webkit-scrollbar {
            width: 6px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb {
            background: var(--text-muted);
            border-radius: 4px;
        }

        .message {
            max-width: 80%;
            padding: 0.75rem 1rem;
            border-radius: 1rem;
            font-size: 0.95rem;
            line-height: 1.4;
            animation: fadeIn 0.3s ease-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.user {
            align-self: flex-end;
            background-color: var(--accent);
            border-bottom-right-radius: 0.25rem;
        }

        .message.agent {
            align-self: flex-start;
            background-color: rgba(255, 255, 255, 0.1);
            border-bottom-left-radius: 0.25rem;
        }

        .message.system {
            align-self: center;
            background-color: transparent;
            color: var(--text-muted);
            font-size: 0.85rem;
            font-style: italic;
        }

        .controls {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            margin-top: 1rem;
        }

        .voice-controls {
            display: flex;
            gap: 1rem;
        }

        .fallback-controls {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            padding-top: 1rem;
            border-top: 1px dashed var(--border-glass);
        }

        .fallback-note {
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        .input-group {
            display: flex;
            gap: 0.5rem;
        }

        input[type="text"] {
            flex-grow: 1;
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid var(--border-glass);
            border-radius: 0.5rem;
            padding: 0.75rem;
            color: var(--text-main);
            font-family: inherit;
        }

        input[type="text"]:focus {
            outline: none;
            border-color: var(--accent);
        }

        .order-item {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            font-size: 0.9rem;
        }
        
        .order-item-mods {
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
        }

        .summary-row {
            display: flex;
            justify-content: space-between;
            padding: 0.25rem 0;
            font-size: 0.9rem;
            color: var(--text-muted);
        }

        .summary-row.total {
            color: var(--text-main);
            font-weight: 600;
            font-size: 1.1rem;
            margin-top: 0.5rem;
            padding-top: 0.5rem;
            border-top: 1px solid var(--border-glass);
        }

        .status-pill {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 1rem;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            background: rgba(255, 255, 255, 0.1);
        }
        
        .status-pill.active { background: rgba(59, 130, 246, 0.2); color: #93c5fd; }
        .status-pill.confirmed { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
        .status-pill.cancelled { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }

        .meta-info {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 1rem;
            word-break: break-all;
        }
    </style>
</head>
<body>

    <div class="container">
        <div class="header">
            <h1>Restaurant Voice Ordering Agent</h1>
            <div id="connection-status">
                <span class="status-pill">Ready</span>
            </div>
        </div>

        <div class="panel main-panel">
            <h2>Conversation</h2>
            <div class="transcript" id="transcript">
                <div class="message system">Click "Start Voice Order" to begin a session.</div>
            </div>

            <div class="controls">
                <div class="voice-controls">
                    <button id="btn-start" onclick="startCall()">Start Voice Order</button>
                    <button id="btn-speak" onclick="toggleListening()" disabled>Speak</button>
                </div>
                
                <div class="fallback-controls">
                    <div class="fallback-note">
                        ⚠️ <strong>Fallback/Debug/Accessibility</strong>: Use this text input if voice is unavailable. This is not the primary voice path.
                    </div>
                    <div class="input-group">
                        <input type="text" id="text-input" placeholder="Type your message here..." disabled onkeypress="handleKey(event)">
                        <button id="btn-send" onclick="sendText()" disabled>Send</button>
                    </div>
                </div>
            </div>
        </div>

        <div class="panel side-panel">
            <h2>Order Details</h2>
            
            <div style="margin-bottom: 1rem;">
                <div class="summary-row">
                    <span>Status</span>
                    <span id="ui-order-status" class="status-pill">None</span>
                </div>
                <div class="summary-row">
                    <span>Name</span>
                    <span id="ui-customer-name">--</span>
                </div>
                <div class="summary-row">
                    <span>Conf ID</span>
                    <span id="ui-conf-id">--</span>
                </div>
            </div>

            <div id="ui-order-items" style="margin-bottom: 1rem; min-height: 100px;">
                <div class="message system">Cart is empty</div>
            </div>

            <div class="order-summary">
                <div class="summary-row">
                    <span>Subtotal</span>
                    <span id="ui-subtotal">$0.00</span>
                </div>
                <div class="summary-row">
                    <span>Tax</span>
                    <span id="ui-tax">$0.00</span>
                </div>
                <div class="summary-row">
                    <span>Fees</span>
                    <span id="ui-fees">$0.00</span>
                </div>
                <div class="summary-row total">
                    <span>Total</span>
                    <span id="ui-total">$0.00</span>
                </div>
            </div>

            <div class="meta-info">
                <div><strong>Session ID:</strong> <span id="ui-session-id">--</span></div>
                <div><strong>Request ID:</strong> <span id="ui-request-id">--</span></div>
            </div>
        </div>
    </div>

    <script>
        let sessionId = null;
        let isListening = false;
        let recognition = null;
        let synthesis = window.speechSynthesis;

        // Initialize Web Speech API
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = 'en-US';

            recognition.onstart = function() {
                isListening = true;
                const btnSpeak = document.getElementById('btn-speak');
                btnSpeak.textContent = 'Listening...';
                btnSpeak.classList.add('danger');
            };

            recognition.onresult = function(event) {
                const transcript = event.results[0][0].transcript;
                sendTurn(transcript);
            };

            recognition.onerror = function(event) {
                console.error('Speech recognition error', event.error);
                appendMessage('system', 'Microphone error: ' + event.error + '. You can use the fallback text input.');
                stopListening();
            };

            recognition.onend = function() {
                stopListening();
            };
        } else {
            appendMessage('system', 'Browser Speech Recognition API is not supported in this browser. Please use the fallback text input.');
        }

        function appendMessage(role, text) {
            const transcriptDiv = document.getElementById('transcript');
            const msgDiv = document.createElement('div');
            msgDiv.className = 'message ' + role;
            msgDiv.textContent = text;
            transcriptDiv.appendChild(msgDiv);
            transcriptDiv.scrollTop = transcriptDiv.scrollHeight;
        }

        function toggleListening() {
            if (!recognition) {
                alert('Speech recognition not available. Please use the fallback text input.');
                return;
            }
            if (isListening) {
                recognition.stop();
            } else {
                // Cancel any ongoing speech synthesis before listening
                if (synthesis) synthesis.cancel();
                try {
                    recognition.start();
                } catch (e) {
                    console.error(e);
                }
            }
        }

        function stopListening() {
            isListening = false;
            const btnSpeak = document.getElementById('btn-speak');
            btnSpeak.textContent = 'Speak';
            btnSpeak.classList.remove('danger');
        }

        function speakText(text) {
            if (!synthesis) return;
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 1.0;
            synthesis.speak(utterance);
        }

        function updateUI(data) {
            // Update Meta
            if (data.session_id) {
                sessionId = data.session_id;
                document.getElementById('ui-session-id').textContent = sessionId;
            }
            if (data.request_id) document.getElementById('ui-request-id').textContent = data.request_id;
            
            // Enable controls
            document.getElementById('btn-speak').disabled = false;
            document.getElementById('text-input').disabled = false;
            document.getElementById('btn-send').disabled = false;
            document.getElementById('btn-start').textContent = 'Restart Order';
            document.getElementById('connection-status').innerHTML = '<span class="status-pill active">Connected</span>';

            // Add agent message
            if (data.agent_text) {
                appendMessage('agent', data.agent_text);
                // We don't auto-speak during automated tests
                speakText(data.agent_text);
            }

            // Update Order Panel
            if (data.order) {
                const order = data.order;
                
                // Status
                const statusEl = document.getElementById('ui-order-status');
                statusEl.textContent = order.status;
                statusEl.className = 'status-pill ' + order.status;

                // Name & Conf
                document.getElementById('ui-customer-name').textContent = order.customer_name || '--';
                document.getElementById('ui-conf-id').textContent = order.confirmation_id || '--';

                // Totals
                document.getElementById('ui-subtotal').textContent = '$' + order.subtotal.toFixed(2);
                document.getElementById('ui-tax').textContent = '$' + order.tax.toFixed(2);
                document.getElementById('ui-fees').textContent = '$' + order.fees.toFixed(2);
                document.getElementById('ui-total').textContent = '$' + order.total.toFixed(2);

                // Items
                const itemsContainer = document.getElementById('ui-order-items');
                if (order.items && order.items.length > 0) {
                    itemsContainer.innerHTML = '';
                    order.items.forEach(item => {
                        const itemDiv = document.createElement('div');
                        itemDiv.className = 'order-item';
                        
                        let modsHtml = '';
                        if (item.special_instructions && item.special_instructions.length > 0) {
                            modsHtml = `<div class="order-item-mods">Note: ${item.special_instructions.join(', ')}</div>`;
                        }

                        itemDiv.innerHTML = `
                            <div>
                                <div>${item.quantity}x ${item.item_id}</div>
                                ${modsHtml}
                            </div>
                        `;
                        itemsContainer.appendChild(itemDiv);
                    });
                } else {
                    itemsContainer.innerHTML = '<div class="message system">Cart is empty</div>';
                }
            }
        }

        async function startCall() {
            document.getElementById('transcript').innerHTML = '';
            appendMessage('system', 'Starting session...');
            
            try {
                const response = await fetch('/api/browser/start-call', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
                
                if (!response.ok) throw new Error('Failed to start call');
                const data = await response.json();
                updateUI(data);
            } catch (error) {
                console.error(error);
                appendMessage('system', 'Error starting call: ' + error.message);
                document.getElementById('connection-status').innerHTML = '<span class="status-pill cancelled">Error</span>';
            }
        }

        async function sendTurn(text) {
            if (!text.trim() || !sessionId) return;
            
            appendMessage('user', text);
            document.getElementById('connection-status').innerHTML = '<span class="status-pill">Thinking...</span>';

            try {
                const response = await fetch('/api/browser/voice-turn', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: sessionId,
                        utterance: text,
                        channel: 'browser'
                    })
                });

                if (!response.ok) throw new Error('Turn failed');
                const data = await response.json();
                updateUI(data);
            } catch (error) {
                console.error(error);
                appendMessage('system', 'Error processing turn: ' + error.message);
                document.getElementById('connection-status').innerHTML = '<span class="status-pill cancelled">Error</span>';
            }
        }

        function handleKey(event) {
            if (event.key === 'Enter') {
                sendText();
            }
        }

        function sendText() {
            const input = document.getElementById('text-input');
            const text = input.value;
            input.value = '';
            sendTurn(text);
        }
    </script>
</body>
</html>"""
