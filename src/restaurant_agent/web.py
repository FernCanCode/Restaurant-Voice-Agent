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

        .voice-help {
            font-size: 0.8rem;
            color: var(--text-muted);
            line-height: 1.4;
        }

        .voice-settings {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            padding: 0.75rem 0 0;
        }

        .checkbox-row {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.9rem;
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

        select {
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid var(--border-glass);
            border-radius: 0.5rem;
            padding: 0.75rem;
            color: var(--text-main);
            font-family: inherit;
        }

        .order-item {
            padding: 0.5rem 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            font-size: 0.9rem;
        }

        .order-item-main {
            font-weight: 500;
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
                <div class="voice-help">
                    Voice input works best in Chrome or Chromium. If the microphone is blocked, open this page directly at localhost instead of an embedded preview and allow microphone access in site settings.
                </div>
                <div class="voice-help">
                    If Chrome misses the first attempt, wait until the status says “Listening... speak now.” before speaking.
                </div>
                <div class="voice-settings">
                    <label class="checkbox-row" for="auto-listen-toggle">
                        <input type="checkbox" id="auto-listen-toggle" onchange="handleAutoListenChange()">
                        <span>Auto-listen after agent responses</span>
                    </label>
                    <label for="voice-select" class="fallback-note">Preferred browser voice</label>
                    <select id="voice-select" onchange="handleVoiceSelectionChange()" aria-label="Preferred browser voice">
                        <option value="">Loading available English voices...</option>
                    </select>
                    <div id="voice-support-note" class="fallback-note"></div>
                    <div id="voice-live-status" class="fallback-note">
                        If recognition misses your words, check your operating system microphone input level and Chrome microphone permission. Browser speech recognition does not expose a sensitivity control.
                    </div>
                </div>
                
                <div class="fallback-controls">
                    <div class="fallback-note">
                        <strong>Typed fallback for debugging/accessibility</strong>: Use this text input if voice is unavailable. Voice remains the primary path.
                    </div>
                    <div class="input-group">
                        <input type="text" id="text-input" placeholder="Type fallback text here..." disabled onkeypress="handleKey(event)">
                        <button id="btn-send" onclick="sendText()" disabled>Send fallback text</button>
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
        let isSpeaking = false;
        let speechToken = 0;
        let recognitionStarting = false;
        let autoListenTimer = null;
        let recognition = null;
        let synthesis = window.speechSynthesis;
        let availableVoices = [];
        let selectedVoiceName = localStorage.getItem('preferredVoiceName') || '';
        let activeInputMode = 'voice';
        let autoListenEnabled = localStorage.getItem('autoListenEnabled') !== 'false';
        let currentOrderStatus = 'none';

        const speechRecognitionUnavailableMessage =
            'Speech recognition is not available in this browser. For voice input, use Chrome or Chromium. You can still use typed fallback for debugging/accessibility.';
        const microphonePermissionBlockedMessage =
            'Microphone access was blocked. Open this app directly in Chrome or Chromium at http://localhost:8000, click the site settings icon beside the address bar, and allow microphone access. Embedded previews may block microphone permissions. You can still use typed fallback for debugging/accessibility.';

        function formatMoney(amount) {
            return '$' + Number(amount || 0).toFixed(2);
        }

        function escapeHtml(text) {
            return String(text)
                .replaceAll('&', '&amp;')
                .replaceAll('<', '&lt;')
                .replaceAll('>', '&gt;')
                .replaceAll('"', '&quot;')
                .replaceAll("'", '&#39;');
        }

        function cleanTextForSpeech(text) {
            return String(text || '')
                .replace(/\\*\\*(.*?)\\*\\*/g, '$1')
                .replace(/\\*(.*?)\\*/g, '$1')
                .replace(/`([^`]+)`/g, '$1')
                .replace(/^[-\\*]\\s+/gm, '')
                .replace(/#{1,6}\\s+/g, '')
                .replace(/\\[(.*?)\\]\\((.*?)\\)/g, '$1')
                .replace(/\\s+/g, ' ')
                .trim();
        }

        function focusFallbackInput() {
            const input = document.getElementById('text-input');
            if (!input.disabled) {
                input.focus();
            }
        }

        function updateVoiceLiveStatus(message) {
            document.getElementById('voice-live-status').textContent = message;
        }

        function clearAutoListenTimer() {
            if (autoListenTimer) {
                window.clearTimeout(autoListenTimer);
                autoListenTimer = null;
            }
        }

        function normalizeCommandText(text) {
            return String(text || '')
                .toLowerCase()
                .replace(/[^\\w\\s']/g, ' ')
                .replace(/\\s+/g, ' ')
                .trim();
        }

        function shouldSubmitTranscript(text) {
            const normalized = normalizeCommandText(text);
            if (!normalized) {
                return false;
            }

            const shortCommands = new Set([
                'yes',
                'no',
                'confirm',
                'done',
                "that's all",
                'that is all',
                "that's it",
                'that is it',
            ]);
            if (shortCommands.has(normalized)) {
                return true;
            }

            const words = normalized
                .split(' ')
                .map((word) => word.trim())
                .filter((word) => word.length > 1 || /^\\d+$/.test(word));
            return words.length >= 2;
        }

        function handleAutoListenChange() {
            const toggle = document.getElementById('auto-listen-toggle');
            autoListenEnabled = Boolean(toggle.checked);
            localStorage.setItem('autoListenEnabled', autoListenEnabled ? 'true' : 'false');
            if (!autoListenEnabled) {
                focusFallbackInput();
            }
        }

        function syncAutoListenToggle() {
            document.getElementById('auto-listen-toggle').checked = autoListenEnabled;
        }

        function isConversationComplete() {
            return currentOrderStatus === 'confirmed' || currentOrderStatus === 'cancelled';
        }

        function shouldUseFallbackFocus() {
            return !recognition || !autoListenEnabled || isConversationComplete();
        }

        function maybeFocusFallbackInput() {
            if (shouldUseFallbackFocus()) {
                focusFallbackInput();
            }
        }

        function getEnglishVoices() {
            if (!synthesis || !synthesis.getVoices) return [];
            return synthesis.getVoices().filter((voice) => voice.lang && voice.lang.toLowerCase().startsWith('en'));
        }

        function voiceScore(voice) {
            const name = (voice.name || '').toLowerCase();
            let score = 0;
            if (name.includes('google')) score += 100;
            if (name.includes('natural')) score += 90;
            if (name.includes('neural')) score += 90;
            if (name.includes('microsoft')) score += 80;
            if (name.includes('samantha')) score += 70;
            if (name.includes('alex')) score += 70;
            if ((voice.lang || '').toLowerCase() === 'en-us') score += 15;
            if (voice.default) score += 10;
            return score;
        }

        function pickPreferredVoice(voices) {
            if (!voices.length) return null;
            if (selectedVoiceName) {
                const persisted = voices.find((voice) => voice.name === selectedVoiceName);
                if (persisted) return persisted;
            }
            return [...voices].sort((a, b) => voiceScore(b) - voiceScore(a))[0] || voices[0];
        }

        function handleVoiceSelectionChange() {
            const select = document.getElementById('voice-select');
            selectedVoiceName = select.value || '';
            if (selectedVoiceName) {
                localStorage.setItem('preferredVoiceName', selectedVoiceName);
            } else {
                localStorage.removeItem('preferredVoiceName');
            }
        }

        function populateVoiceSelector() {
            const select = document.getElementById('voice-select');
            availableVoices = getEnglishVoices();

            if (!availableVoices.length) {
                select.innerHTML = '<option value="">No English voices detected</option>';
                select.disabled = true;
                return;
            }

            const preferred = pickPreferredVoice(availableVoices);
            if (preferred) {
                selectedVoiceName = preferred.name;
                localStorage.setItem('preferredVoiceName', selectedVoiceName);
            }

            select.innerHTML = availableVoices
                .map((voice) => `<option value="${escapeHtml(voice.name)}">${escapeHtml(voice.name)} (${escapeHtml(voice.lang)})</option>`)
                .join('');
            select.disabled = false;
            select.value = selectedVoiceName;
        }

        function updateVoiceSupportMessage() {
            const note = document.getElementById('voice-support-note');
            if (!recognition) {
                note.textContent = speechRecognitionUnavailableMessage;
                return;
            }
            note.textContent = 'Voice input works best in Chrome or Chromium. If microphone access is blocked, open this page directly at localhost and allow microphone access in site settings.';
        }

        function updateConnectionStatus(text, pillClass = '') {
            const classes = ['status-pill'];
            if (pillClass) classes.push(pillClass);
            document.getElementById('connection-status').innerHTML =
                `<span class="${classes.join(' ')}">${escapeHtml(text)}</span>`;
        }

        function startListening(reason = 'manual') {
            if (!recognition || isListening || recognitionStarting || isConversationComplete()) {
                if (reason !== 'manual') {
                    maybeFocusFallbackInput();
                }
                return;
            }

            if (isSpeaking && synthesis) {
                speechToken += 1;
                isSpeaking = false;
                synthesis.cancel();
                window.setTimeout(() => startListening(reason), 450);
                return;
            }

            recognitionStarting = true;
            activeInputMode = 'voice';
            updateVoiceLiveStatus('Listening... speak now.');

            try {
                recognition.start();
            } catch (error) {
                console.error(error);
                recognitionStarting = false;
                isListening = false;
                appendMessage('system', 'Unable to start speech recognition. You can still use typed fallback for debugging/accessibility.');
                updateVoiceLiveStatus('Unable to start speech recognition. You can still use typed fallback.');
                maybeFocusFallbackInput();
            }
        }

        function maybeStartAutoListen() {
            clearAutoListenTimer();
            if (!autoListenEnabled || !recognition || isConversationComplete() || isSpeaking) {
                maybeFocusFallbackInput();
                return;
            }
            autoListenTimer = window.setTimeout(() => {
                startListening('auto');
            }, 450);
        }

        // Initialize Web Speech API
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = true;
            recognition.lang = 'en-US';
            recognition.maxAlternatives = 1;

            recognition.onstart = function() {
                recognitionStarting = false;
                isListening = true;
                const btnSpeak = document.getElementById('btn-speak');
                btnSpeak.textContent = 'Listening...';
                btnSpeak.classList.add('danger');
                updateConnectionStatus('Listening...', 'active');
                updateVoiceLiveStatus('Listening... speak now.');
            };

            recognition.onresult = function(event) {
                activeInputMode = 'voice';
                let interimText = '';
                let finalText = '';

                for (let i = event.resultIndex; i < event.results.length; i += 1) {
                    const result = event.results[i];
                    const transcript = result[0].transcript.trim();
                    if (!transcript) {
                        continue;
                    }
                    if (result.isFinal) {
                        finalText += (finalText ? ' ' : '') + transcript;
                    } else {
                        interimText += (interimText ? ' ' : '') + transcript;
                    }
                }

                if (interimText) {
                    updateVoiceLiveStatus(`Heard: ${interimText}`);
                }

                if (finalText) {
                    const cleanedFinalText = finalText.trim();
                    updateVoiceLiveStatus(`Heard: ${cleanedFinalText}`);
                    if (!shouldSubmitTranscript(cleanedFinalText)) {
                        appendMessage('system', 'I only caught part of that. Please try again.');
                        updateVoiceLiveStatus('I only caught part of that. Please try again.');
                        return;
                    }
                    sendTurn(cleanedFinalText);
                }
            };

            recognition.onspeechend = function() {
                updateVoiceLiveStatus('Processing speech...');
            };

            recognition.onerror = function(event) {
                console.error('Speech recognition error', event.error);
                recognitionStarting = false;
                if (event.error === 'not-allowed') {
                    appendMessage('system', microphonePermissionBlockedMessage);
                    updateVoiceLiveStatus('Microphone access was blocked.');
                } else if (event.error === 'no-speech') {
                    appendMessage('system', 'No speech detected. Try again or use typed fallback.');
                    updateVoiceLiveStatus('No speech detected. Try speaking closer to the microphone or check your system input volume.');
                } else if (event.error === 'audio-capture') {
                    appendMessage('system', 'No microphone was found. Check your system microphone connection and browser input device.');
                    updateVoiceLiveStatus('No microphone was found.');
                } else {
                    appendMessage('system', 'Microphone error: ' + event.error + '. You can still use typed fallback for debugging/accessibility.');
                    updateVoiceLiveStatus('Microphone error: ' + event.error);
                }
                stopListening();
                maybeFocusFallbackInput();
            };

            recognition.onend = function() {
                recognitionStarting = false;
                stopListening();
            };
        } else {
            appendMessage('system', speechRecognitionUnavailableMessage);
            updateVoiceLiveStatus(speechRecognitionUnavailableMessage);
        }

        if (synthesis && typeof synthesis.onvoiceschanged !== 'undefined') {
            synthesis.onvoiceschanged = populateVoiceSelector;
        }
        populateVoiceSelector();
        syncAutoListenToggle();
        updateVoiceSupportMessage();

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
                alert('Speech recognition is not available in this browser. For voice input, use Chrome or Chromium.');
                return;
            }
            if (isListening) {
                recognition.stop();
            } else {
                clearAutoListenTimer();
                if (isSpeaking && synthesis) {
                    updateVoiceLiveStatus('Preparing microphone...');
                    speechToken += 1;
                    isSpeaking = false;
                    synthesis.cancel();
                    window.setTimeout(() => startListening('manual'), 450);
                    return;
                }
                startListening('manual');
            }
        }

        function stopListening() {
            isListening = false;
            recognitionStarting = false;
            const btnSpeak = document.getElementById('btn-speak');
            btnSpeak.textContent = 'Speak';
            btnSpeak.classList.remove('danger');
        }

        function speakText(text, autoListenAfterSpeech = false) {
            const spokenText = cleanTextForSpeech(text);
            if (!spokenText) {
                if (autoListenAfterSpeech) {
                    maybeStartAutoListen();
                } else {
                    maybeFocusFallbackInput();
                }
                return;
            }

            if (!synthesis) {
                if (autoListenAfterSpeech) {
                    maybeStartAutoListen();
                } else {
                    maybeFocusFallbackInput();
                }
                return;
            }

            clearAutoListenTimer();
            speechToken += 1;
            const currentSpeechToken = speechToken;
            isSpeaking = true;
            synthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(spokenText);
            const selectedVoice = availableVoices.find((voice) => voice.name === selectedVoiceName) || pickPreferredVoice(getEnglishVoices());
            if (selectedVoice) {
                utterance.voice = selectedVoice;
                utterance.lang = selectedVoice.lang;
            }
            utterance.rate = 0.92;
            utterance.pitch = 1.0;
            utterance.volume = 1.0;
            utterance.onend = function() {
                if (currentSpeechToken !== speechToken) {
                    return;
                }
                isSpeaking = false;
                if (autoListenAfterSpeech) {
                    maybeStartAutoListen();
                } else {
                    maybeFocusFallbackInput();
                }
            };
            utterance.onerror = function() {
                if (currentSpeechToken !== speechToken) {
                    return;
                }
                isSpeaking = false;
                if (autoListenAfterSpeech) {
                    maybeStartAutoListen();
                } else {
                    maybeFocusFallbackInput();
                }
            };
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
            currentOrderStatus = data.order ? data.order.status : currentOrderStatus;
            document.getElementById('btn-speak').disabled = !recognition || isConversationComplete();
            document.getElementById('text-input').disabled = false;
            document.getElementById('btn-send').disabled = false;
            document.getElementById('btn-start').textContent = 'Restart Order';
            if (isConversationComplete()) {
                updateConnectionStatus('Conversation complete', currentOrderStatus);
                updateVoiceLiveStatus('Conversation complete.');
                clearAutoListenTimer();
                if (recognition && (isListening || recognitionStarting)) {
                    recognition.stop();
                }
            } else if (isListening) {
                updateConnectionStatus('Listening...', 'active');
            } else {
                updateConnectionStatus('Connected', 'active');
            }

            // Add agent message
            if (data.agent_text) {
                appendMessage('agent', data.agent_text);
                speakText(data.agent_text, autoListenEnabled && !isConversationComplete());
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

                        const lineAmount = Number(item.line_total || item.line_subtotal || 0);
                        const modLines = [];
                        if (item.known_modifications && item.known_modifications.length > 0) {
                            const pricedOptions = item.known_modifications
                                .map((mod) => `${escapeHtml(mod.name)} (${formatMoney(mod.price_delta)})`)
                                .join(', ');
                            modLines.push(`<div class="order-item-mods">Priced options: ${pricedOptions}</div>`);
                        }
                        if (item.special_instructions && item.special_instructions.length > 0) {
                            modLines.push(`<div class="order-item-mods">Special instructions: ${escapeHtml(item.special_instructions.join(', '))}</div>`);
                        }

                        itemDiv.innerHTML = `
                            <div>
                                <div class="order-item-main">${item.quantity}x ${escapeHtml(item.item_name)} — ${formatMoney(lineAmount)}</div>
                                ${modLines.join('')}
                            </div>
                        `;
                        itemsContainer.appendChild(itemDiv);
                    });
                } else {
                    itemsContainer.innerHTML = '<div class="message system">Cart is empty</div>';
                }
            }

            updateVoiceSupportMessage();
            if (activeInputMode === 'typed' || shouldUseFallbackFocus()) {
                focusFallbackInput();
            }
        }

        async function startCall() {
            document.getElementById('transcript').innerHTML = '';
            appendMessage('system', 'Starting session...');
            autoListenEnabled = true;
            syncAutoListenToggle();
            localStorage.setItem('autoListenEnabled', 'true');
            currentOrderStatus = 'active';
            updateConnectionStatus('Connecting...');
            
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
            
            if (recognition && (isListening || recognitionStarting)) {
                recognition.stop();
            }
            clearAutoListenTimer();
            appendMessage('user', text);
            updateConnectionStatus('Thinking...');
            updateVoiceLiveStatus('Processing speech...');

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
            activeInputMode = 'typed';
            sendTurn(text);
            focusFallbackInput();
        }
    </script>
</body>
</html>"""
