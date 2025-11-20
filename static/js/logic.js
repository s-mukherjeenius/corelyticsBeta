/*
 * =========================================
 * CORELYTICS - LOGIC (CHATBOT) SCRIPT
 * =========================================
 */

document.addEventListener('DOMContentLoaded', function () {

    // --- DOM Elements ---
    const chatMessages = document.getElementById('chatMessages');
    const chatInput = document.getElementById('chatInput');
    const sendMessageBtn = document.getElementById('sendMessageBtn');
    const typingIndicator = document.getElementById('typingIndicator');
    const newChatBtn = document.getElementById('newChatBtn'); // NEW: For the New Chat button

    // Voice and settings elements
    const voiceControlBtn = document.getElementById('voiceControlBtn');
    const ttsToggleBtn = document.getElementById('ttsToggleBtn');
    const ttsIcon = document.getElementById('ttsIcon');
    const continuousListenToggleBtn = document.getElementById('continuousListenToggleBtn');
    const continuousListenIcon = document.getElementById('continuousListenIcon');
    const voiceSettingsModalEl = document.getElementById('voiceSettingsModal');
    const voiceSettingsModal = voiceSettingsModalEl ? new bootstrap.Modal(voiceSettingsModalEl) : null;
    const voiceSelector = document.getElementById('voiceSelector');
    const voiceRate = document.getElementById('voiceRate');
    const rateValue = document.getElementById('rateValue');
    const saveVoiceSettingsBtn = document.getElementById('saveVoiceSettingsBtn');

    // --- State Variables ---
    let isTtsEnabled = true;
    let isRecording = false;
    let isContinuousListening = false;
    let isBotSpeaking = false;
    let currentUtterance = null;
    let voices = [];
    let currentWordSpan = null;
    let lastSpeechInputTimeout = null;
    let continuousRecognitionRetryTimeout = null;
    let audioContextInitialized = false;
    let audioContext = null;

    // --- 1. Web Speech API Initialization (PRESERVED EXACTLY) ---
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition;

    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.interimResults = true;
        recognition.lang = 'en-US';
        recognition.currentStatus = 'idle'; // 'idle', 'starting', 'listening', 'stopping'

        recognition.onstart = () => {
            isRecording = true;
            recognition.currentStatus = 'listening';
            voiceControlBtn.classList.add('recording');
            chatInput.placeholder = "Listening...";
            if (lastSpeechInputTimeout) clearTimeout(lastSpeechInputTimeout);
        };

        recognition.onend = () => {
            isRecording = false;
            recognition.currentStatus = 'idle';
            voiceControlBtn.classList.remove('recording');
            chatInput.placeholder = "Type or talk...";

            if (isContinuousListening && !isBotSpeaking && recognition) {
                if (continuousRecognitionRetryTimeout) clearTimeout(continuousRecognitionRetryTimeout);
                continuousRecognitionRetryTimeout = setTimeout(() => {
                    if (recognition && !isBotSpeaking && recognition.currentStatus === 'idle') {
                        try {
                            recognition.start();
                            recognition.currentStatus = 'starting';
                        } catch (e) {
                            console.warn("Error restarting recognition from onend:", e.name, e.message);
                        }
                    }
                }, 500);
            } else if (!isContinuousListening && chatInput.value.trim().length > 0) {
                setTimeout(sendMessage, 100);
            }
        };

        recognition.onresult = (event) => {
            let interimTranscript = '';
            let finalTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                } else {
                    interimTranscript += event.results[i][0].transcript;
                }
            }

            chatInput.value = finalTranscript || interimTranscript;

            if (isContinuousListening && finalTranscript) {
                if (lastSpeechInputTimeout) clearTimeout(lastSpeechInputTimeout);
                lastSpeechInputTimeout = setTimeout(() => {
                    sendMessage();
                }, 700);
            }
        };

        recognition.onerror = (event) => {
            console.error("Speech recognition error:", event.error);
            isRecording = false;
            recognition.currentStatus = 'idle';
            voiceControlBtn.classList.remove('recording');
            chatInput.placeholder = "Type or talk...";
            if (lastSpeechInputTimeout) clearTimeout(lastSpeechInputTimeout);
            if (continuousRecognitionRetryTimeout) clearTimeout(continuousRecognitionRetryTimeout);

            let errorMessage = `Speech Error: ${event.error}`;
            if (event.error === 'not-allowed') {
                errorMessage = 'Microphone access was denied. Please allow it.';
                window.showToast(errorMessage, 'error');
            } else if (event.error === 'no-speech') {
                console.warn('No speech detected.');
                if (isContinuousListening && recognition) {
                    if (continuousRecognitionRetryTimeout) clearTimeout(continuousRecognitionRetryTimeout);
                    continuousRecognitionRetryTimeout = setTimeout(() => {
                        if (recognition.currentStatus === 'idle') {
                            try {
                                recognition.start();
                                recognition.currentStatus = 'starting';
                            } catch (e) { console.warn("Error restarting recognition after no-speech:", e.name, e.message); }
                        }
                    }, 500);
                }
                return;
            } else if (event.error === 'audio-capture') {
                errorMessage = 'Microphone not found or busy.';
                window.showToast(errorMessage, 'error');
            } else if (event.error === 'network' && isContinuousListening) {
                console.warn('Transient network error for speech. Attempting auto-recover.');
                if (isContinuousListening && recognition) {
                    if (continuousRecognitionRetryTimeout) clearTimeout(continuousRecognitionRetryTimeout);
                    continuousRecognitionRetryTimeout = setTimeout(() => {
                        if (recognition.currentStatus === 'idle') {
                            try {
                                recognition.start();
                                recognition.currentStatus = 'starting';
                            } catch (e) { console.warn("Error restarting recognition after network error:", e.name, e.message); }
                        }
                    }, 500);
                }
                return;
            } else {
                window.showToast(`Speech Error: ${event.error}`, 'error');
            }
        };
    } else {
        if (voiceControlBtn) voiceControlBtn.style.display = 'none';
        if (continuousListenToggleBtn) continuousListenToggleBtn.style.display = 'none';
        // window.showToast('Speech Recognition not supported in this browser.', 'info'); // Optional: Suppress if annoying
    }

    // --- 2. AudioContext Initialization ---
    function initializeAudioContext() {
        if (audioContextInitialized) return;
        try {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const buffer = audioContext.createBuffer(1, 1, 22050);
            const source = audioContext.createBufferSource();
            source.buffer = buffer;
            source.connect(audioContext.destination);
            source.start(0);
            source.onended = () => {
                source.disconnect();
                console.log("AudioContext primed.");
            };
            audioContextInitialized = true;
        } catch (e) {
            console.error("Failed to initialize AudioContext:", e);
        }
    }

    // --- 3. Voice Synthesis (TTS) Functions ---
    function populateVoiceList() {
        voices = speechSynthesis.getVoices();

        if (voices.length === 0) {
            console.log("Voices not yet loaded. Waiting for 'onvoiceschanged'.");
            return;
        }
        if (voiceSelector) {
            voiceSelector.innerHTML = '';
        }

        const preferredVoices = [
            "Google US English", "Microsoft Zira - English (United States)",
            "Microsoft David - English (United States)", "Google UK English Female"
        ];

        let availableVoices = voices.filter(v => v.lang.startsWith('en'));

        availableVoices.sort((a, b) => {
            let aPref = preferredVoices.indexOf(a.name);
            let bPref = preferredVoices.indexOf(b.name);
            if (aPref === -1) aPref = 99;
            if (bPref === -1) bPref = 99;
            return aPref - bPref;
        });

        availableVoices.forEach((voice) => {
            const option = document.createElement('option');
            option.textContent = `${voice.name} (${voice.lang})`;
            option.setAttribute('data-lang', voice.lang);
            option.setAttribute('data-name', voice.name);
            if (voiceSelector) {
                voiceSelector.appendChild(option);
            }
        });

        loadVoiceSettings();
    }

    function saveVoiceSettings() {
        if (voiceSelector && voiceSelector.options.length > 0) {
            const selectedVoiceName = voiceSelector.selectedOptions[0].getAttribute('data-name');
            localStorage.setItem('logic_tts_voice', selectedVoiceName);
        }
        if (voiceRate) {
            localStorage.setItem('logic_tts_rate', voiceRate.value);
        }
        window.showToast('Voice settings saved!', 'success');
        if (voiceSettingsModal) {
            voiceSettingsModal.hide();
        }
    }

    function loadVoiceSettings() {
        const savedVoiceName = localStorage.getItem('logic_tts_voice');
        const savedRate = localStorage.getItem('logic_tts_rate') || '1';
        const savedTtsEnabled = localStorage.getItem('logic_tts_enabled');
        const savedContinuousListening = localStorage.getItem('logic_continuous_listening');

        if (voiceRate) {
            voiceRate.value = savedRate;
        }
        if (rateValue) {
            rateValue.textContent = savedRate;
        }

        if (savedVoiceName && voiceSelector) {
            const options = Array.from(voiceSelector.options);
            const savedOption = options.find(opt => opt.getAttribute('data-name') === savedVoiceName);
            if (savedOption) {
                savedOption.selected = true;
            }
        }

        if (savedTtsEnabled === 'false') {
            isTtsEnabled = false;
            ttsIcon.className = 'fas fa-volume-mute';
            ttsToggleBtn.classList.remove('active');
        } else {
            isTtsEnabled = true;
            ttsIcon.className = 'fas fa-volume-up';
            ttsToggleBtn.classList.add('active');
        }

        if (savedContinuousListening === 'true') {
            isContinuousListening = true;
            continuousListenIcon.className = 'fas fa-headset';
            continuousListenToggleBtn.classList.add('active');
            if (recognition) {
                recognition.continuous = true;
                if (recognition.currentStatus === 'idle' && !isBotSpeaking) {
                    try {
                        recognition.start();
                        recognition.currentStatus = 'starting';
                    } catch (e) {
                        console.warn("Recognition error on load (continuous mode):", e.name, e.message);
                    }
                }
            }
        } else {
            isContinuousListening = false;
            continuousListenIcon.className = 'fas fa-headset';
            continuousListenToggleBtn.classList.remove('active');
            if (recognition) {
                recognition.continuous = false;
                if (recognition.currentStatus !== 'idle') {
                    recognition.stop();
                }
            }
        }
    }

    if (speechSynthesis.onvoiceschanged !== undefined) {
        speechSynthesis.onvoiceschanged = populateVoiceList;
    }
    populateVoiceList(); // Initial call

    function cleanTextForSpeech(text) {
        if (typeof marked === 'undefined') {
            console.error('Marked.js not loaded. Cannot clean text for speech.');
            return text.replace(/[*_`#]/g, ''); // Basic fallback
        }
        let cleanHtml = marked.parse(text);
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = cleanHtml;
        tempDiv.querySelectorAll('pre, code, img').forEach(element => element.remove());
        let plainText = tempDiv.textContent || tempDiv.innerText || '';
        plainText = plainText.replace(/[\n\r]+/g, ' ').replace(/\s+/g, ' ').trim();
        return plainText;
    }

    function renderBotMessageForSpeech(messageBubbleElement, markdownText) {
        if (typeof marked === 'undefined') {
            console.error('Marked.js not loaded. Cannot render markdown.');
            messageBubbleElement.textContent = markdownText;
            return;
        }
        const parsedHtml = marked.parse(markdownText);
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = parsedHtml;

        // Wrap words in spans for highlighting
        tempDiv.querySelectorAll('p, li, h1, h2, h3, h4, h5, h6').forEach(element => {
            if (element.closest('pre') || element.closest('code')) {
                return;
            }

            let processedHTML = '';
            Array.from(element.childNodes).forEach(node => {
                if (node.nodeType === Node.TEXT_NODE) {
                    processedHTML += node.textContent.split(/(\s+)/).filter(w => w.length > 0).map(word => `<span>${word}</span>`).join('');
                } else if (node.nodeType === Node.ELEMENT_NODE) {
                    let clonedElement = node.cloneNode(true);
                    if (clonedElement.textContent) {
                        clonedElement.innerHTML = clonedElement.textContent.split(/(\s+)/).filter(w => w.length > 0).map(word => `<span>${word}</span>`).join('');
                    }
                    processedHTML += clonedElement.outerHTML;
                }
            });
            element.innerHTML = processedHTML;
        });
        messageBubbleElement.innerHTML = tempDiv.innerHTML;
    }

    function speakText(text, messageBubble) {
        if (!isTtsEnabled || !'speechSynthesis' in window || !text) return;
        if (voices.length === 0) {
            console.warn("No voices loaded. Cannot speak.");
            return;
        }

        window.speechSynthesis.cancel(); // Cancel any previous speech

        const textToSpeak = " " + cleanTextForSpeech(text);
        if (!textToSpeak.trim()) return;

        let voiceToUse = null;
        if (voiceSelector) {
            const savedVoiceName = voiceSelector.selectedOptions[0].getAttribute('data-name');
            voiceToUse = voices.find(v => v.name === savedVoiceName);
        }

        if (!voiceToUse) voiceToUse = voices.find(v => v.name === "Google US English");
        if (!voiceToUse) voiceToUse = voices[0];
        if (!voiceToUse) {
            console.error("No suitable voice found.");
            return;
        }

        currentUtterance = new SpeechSynthesisUtterance(textToSpeak);
        currentUtterance.voice = voiceToUse;
        currentUtterance.rate = parseFloat(voiceRate ? voiceRate.value : 1.0);
        currentUtterance.pitch = 1.0;

        const wordSpans = Array.from(messageBubble.querySelectorAll('span'));
        let charCounter = 0;

        currentUtterance.onboundary = (event) => {
            if (event.name === 'word') {
                if (currentWordSpan) {
                    currentWordSpan.classList.remove('word-highlight');
                }

                let accumulatedChars = 0;
                for (const span of wordSpans) {
                    const word = span.textContent;
                    if (!word.trim()) {
                        accumulatedChars += word.length;
                        continue;
                    }

                    if (event.charIndex >= accumulatedChars + 1 && event.charIndex < accumulatedChars + 1 + word.length) {
                        currentWordSpan = span;
                        currentWordSpan.classList.add('word-highlight');
                        break;
                    }
                    accumulatedChars += word.length;
                }
            }
        };

        currentUtterance.onend = () => {
            if (currentWordSpan) currentWordSpan.classList.remove('word-highlight');
            currentUtterance = null;
            isBotSpeaking = false;
            if (isContinuousListening && recognition) {
                if (continuousRecognitionRetryTimeout) clearTimeout(continuousRecognitionRetryTimeout);
                continuousRecognitionRetryTimeout = setTimeout(() => {
                    if (recognition.currentStatus === 'idle') {
                        try {
                            recognition.start();
                            recognition.currentStatus = 'starting';
                        } catch (e) {
                            console.warn("Error resuming recognition after bot speech:", e.name, e.message);
                        }
                    }
                }, 200);
            }
        };

        currentUtterance.onerror = (event) => {
            console.error('Speech synthesis error:', event.error);
            if (currentWordSpan) currentWordSpan.classList.remove('word-highlight');
            currentUtterance = null;
            isBotSpeaking = false;
            if (isContinuousListening && recognition) {
                if (continuousRecognitionRetryTimeout) clearTimeout(continuousRecognitionRetryTimeout);
                continuousRecognitionRetryTimeout = setTimeout(() => {
                    if (recognition.currentStatus === 'idle') {
                        try {
                            recognition.start();
                            recognition.currentStatus = 'starting';
                        } catch (e) { console.warn("Error restarting recognition after TTS error:", e.name, e.message); }
                    }
                }, 200);
            }
        };

        window.speechSynthesis.speak(currentUtterance);
        isBotSpeaking = true;
    }

    // --- 4. Core Chat Functions ---
    function showTypingIndicator() {
        if (typingIndicator) {
            chatMessages.appendChild(typingIndicator);
            typingIndicator.style.display = 'flex';
            scrollToBottom();
        }
    }

    function hideTypingIndicator() {
        if (typingIndicator) {
            typingIndicator.style.display = 'none';
        }
    }

    function scrollToBottom() {
        if (chatMessages) {
            setTimeout(() => {
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }, 0);
        }
    }

    function addMessage(text, sender) {
        const messageBubble = document.createElement('div');
        messageBubble.className = `message-bubble ${sender}-message`;

        if (sender === 'bot') {
            messageBubble.setAttribute('data-raw-text', text);
            renderBotMessageForSpeech(messageBubble, text);

            if (isTtsEnabled) {
                speakText(text, messageBubble);
            }

            const wrapper = document.createElement('div');
            wrapper.className = 'message-wrapper bot-wrapper';

            const avatar = document.createElement('img');
            avatar.src = '/static/logic.png'; 
            avatar.className = 'bot-avatar';
            avatar.alt = 'Logic';

            wrapper.appendChild(avatar);
            wrapper.appendChild(messageBubble);

            if (chatMessages) {
                chatMessages.appendChild(wrapper);
            }

        } else {
            messageBubble.textContent = text;
            if (chatMessages) {
                chatMessages.appendChild(messageBubble);
            }
        }

        scrollToBottom();
    }

    async function sendMessage() {
        const message = chatInput.value.trim();
        if (message === '') return;

        if (!audioContextInitialized) {
            initializeAudioContext();
        }

        if (currentUtterance) window.speechSynthesis.cancel();
        if (recognition && recognition.currentStatus !== 'idle') {
            recognition.stop();
        }
        if (lastSpeechInputTimeout) clearTimeout(lastSpeechInputTimeout);

        addMessage(message, 'user');
        chatInput.value = '';
        sendMessageBtn.disabled = true;
        sendMessageBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
        showTypingIndicator();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message })
            });
            const result = await response.json();

            hideTypingIndicator();

            if (result.success) {
                addMessage(result.response, 'bot');
            } else {
                addMessage('Sorry, an error occurred: ' + (result.message || 'Unknown error'), 'bot');
            }
        } catch (error) {
            hideTypingIndicator();
            console.error('Error sending message:', error);
            addMessage('Failed to connect to the chatbot. Please check your connection.', 'bot');
        } finally {
            sendMessageBtn.disabled = false;
            sendMessageBtn.innerHTML = '<i class="fas fa-paper-plane mr-2"></i> Send';
            if (isContinuousListening && recognition && !isBotSpeaking) {
                if (continuousRecognitionRetryTimeout) clearTimeout(continuousRecognitionRetryTimeout);
                continuousRecognitionRetryTimeout = setTimeout(() => {
                    if (recognition.currentStatus === 'idle') {
                        try {
                            recognition.start();
                            recognition.currentStatus = 'starting';
                        } catch (e) {
                            console.warn("Recognition start failed in finally block:", e.name, e.message);
                        }
                    }
                }, 200);
            }
        }
    }

    // --- 5. LOAD CONVERSATION FUNCTION (Moved inside Scope) ---
    async function loadConversation(conversationId, element) {
        const chatMessages = document.getElementById('chatMessages');
        
        // UI: Highlight the active pill
        document.querySelectorAll('.history-pill').forEach(el => el.classList.remove('active'));
        if(element) element.classList.add('active');
    
        // UI: Show Loading Spinner
        chatMessages.innerHTML = `
            <div style="display:flex;justify-content:center;align-items:center;height:100%;">
                <div class="spinner-border text-primary" role="status"></div>
            </div>`;
    
        try {
            const response = await fetch(`/api/get-conversation/${conversationId}`);
            const result = await response.json();
    
            if (result.success) {
                chatMessages.innerHTML = ''; // Clear spinner
                
                if (result.history.length === 0) {
                    // Manually create message to avoid triggering TTS
                    const msgDiv = document.createElement('div');
                    msgDiv.className = 'message-bubble bot-message';
                    msgDiv.textContent = "This conversation is empty.";
                    chatMessages.appendChild(msgDiv);
                } else {
                    // Temporarily disable TTS so the bot doesn't read 10 messages at once
                    const wasTtsEnabled = isTtsEnabled;
                    isTtsEnabled = false; 

                    result.history.forEach(msg => {
                        addMessage(msg.message, msg.role === 'model' ? 'bot' : 'user');
                    });

                    // Restore TTS state
                    isTtsEnabled = wasTtsEnabled;
                }
            } else {
                chatMessages.innerHTML = `<div class="text-center mt-5 text-danger">Failed to load chat.</div>`;
            }
        } catch (error) {
            console.error("Error loading chat:", error);
            chatMessages.innerHTML = `<div class="text-center mt-5 text-danger">Network Error.</div>`;
        }
    }

    // --- 6. Event Listeners ---
    
    // Attach listener to History Pills (The fix for your red lines!)
    // We use document.body delegation to handle pills even if they refresh, 
    // or we can just select them since they are static on page load.
    const historyPills = document.querySelectorAll('.history-pill');
    historyPills.forEach(pill => {
        pill.addEventListener('click', function() {
            // Check if it's the "New Chat" button specifically
            if (this.id === 'newChatBtn') return; // Handled separately

            const id = this.getAttribute('data-id');
            if (id) {
                loadConversation(id, this);
            }
        });
    });

    // New Chat Button
    if (newChatBtn) {
        newChatBtn.addEventListener('click', async () => {
             // UI: Reset pills
             document.querySelectorAll('.history-pill').forEach(el => el.classList.remove('active'));
             
             chatMessages.innerHTML = `
                <div style="display:flex;justify-content:center;align-items:center;height:100%;">
                    <div class="spinner-border text-primary" role="status"></div>
                </div>`;
             
             try {
                 const response = await fetch('/api/start-new-chat', { method: 'POST' });
                 const result = await response.json();
                 
                 if (result.success) {
                     chatMessages.innerHTML = '';
                     // Use addMessage but prevent TTS for "System" messages if preferred
                     // For now we let it speak "Hello"
                     addMessage("Hello! I'm Logic. Starting a fresh conversation.", 'bot');
                 }
             } catch (e) {
                 console.error(e);
             }
        });
    }

    // Standard Listeners (Preserved)
    if (sendMessageBtn) {
        sendMessageBtn.addEventListener('click', sendMessage);
    }
    if (chatInput) {
        chatInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                sendMessage();
            }
        });
    }

    if (voiceControlBtn) {
        voiceControlBtn.addEventListener('click', () => {
            if (!recognition) return;
            if (!audioContextInitialized) initializeAudioContext();

            if (isContinuousListening) {
                if (recognition.currentStatus === 'listening' || recognition.currentStatus === 'starting') {
                    recognition.stop();
                    window.showToast('Continuous listening paused.', 'info');
                } else {
                    try {
                        recognition.start();
                        recognition.currentStatus = 'starting';
                        window.showToast('Continuous listening resumed.', 'info');
                    } catch (e) {
                        window.showToast('Failed to start listening. Check mic access.', 'error');
                    }
                }
            } else { // Push-to-talk
                if (recognition.currentStatus === 'listening' || recognition.currentStatus === 'starting') {
                    recognition.stop();
                } else {
                    if (currentUtterance) window.speechSynthesis.cancel();
                    chatInput.value = '';
                    try {
                        recognition.start();
                        recognition.currentStatus = 'starting';
                    } catch (e) {
                        window.showToast('Failed to start microphone. Check access.', 'error');
                    }
                }
            }
        });
    }

    if (ttsToggleBtn) {
        ttsToggleBtn.addEventListener('click', () => {
            isTtsEnabled = !isTtsEnabled;
            localStorage.setItem('logic_tts_enabled', isTtsEnabled);
            if (isTtsEnabled) {
                ttsIcon.className = 'fas fa-volume-up';
                ttsToggleBtn.classList.add('active');
                window.showToast('AI voice enabled.', 'info');
            } else {
                ttsIcon.className = 'fas fa-volume-mute';
                ttsToggleBtn.classList.remove('active');
                window.speechSynthesis.cancel();
                if (currentWordSpan) currentWordSpan.classList.remove('word-highlight');
                currentUtterance = null;
                isBotSpeaking = false;
                window.showToast('AI voice disabled.', 'info');
            }
        });
    }

    if (continuousListenToggleBtn) {
        continuousListenToggleBtn.addEventListener('click', () => {
            isContinuousListening = !isContinuousListening;
            localStorage.setItem('logic_continuous_listening', isContinuousListening);

            if (isContinuousListening) {
                continuousListenToggleBtn.classList.add('active');
                if (recognition) {
                    recognition.continuous = true;
                    if (recognition.currentStatus === 'idle' && !isBotSpeaking) {
                        try {
                            recognition.start();
                            recognition.currentStatus = 'starting';
                        } catch (e) {
                            window.showToast('Failed to start listening. Check mic access.', 'error');
                        }
                    }
                }
                window.showToast('Continuous listening enabled.', 'info');
            } else {
                continuousListenToggleBtn.classList.remove('active');
                if (recognition) {
                    recognition.continuous = false;
                    if (recognition.currentStatus !== 'idle') {
                        recognition.stop();
                    }
                }
                if (lastSpeechInputTimeout) clearTimeout(lastSpeechInputTimeout);
                if (continuousRecognitionRetryTimeout) clearTimeout(continuousRecognitionRetryTimeout);
                window.showToast('Continuous listening disabled.', 'info');
            }
        });
    }

    if (saveVoiceSettingsBtn) {
        saveVoiceSettingsBtn.addEventListener('click', saveVoiceSettings);
    }
    if (voiceRate) {
        voiceRate.addEventListener('input', (e) => {
            if (rateValue) rateValue.textContent = e.target.value;
        });
    }

    // --- Initial Page Setup ---
    document.querySelectorAll('.message-bubble.bot-message[data-raw-text]').forEach(bubble => {
        const rawText = bubble.getAttribute('data-raw-text');
        renderBotMessageForSpeech(bubble, rawText);
    });
    scrollToBottom();
});