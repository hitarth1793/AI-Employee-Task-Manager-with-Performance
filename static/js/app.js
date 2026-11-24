document.addEventListener("DOMContentLoaded", () => {
    // AI assistant
    const form = document.getElementById("assistant-form");
    const log = document.getElementById("chat-log");
    const input = document.getElementById("question");
    const codeText = document.getElementById("code-text");
    const voiceBtn = document.getElementById("start-voice") || document.getElementById("mic-btn");
    const speakBtn = document.getElementById("speak-answer");
    const sendBtn = document.getElementById("assistant-send");
    const providerSelect = document.getElementById("assistant-provider");
    const assistantStatus = document.getElementById("assistant-status");
    const conversationSelect = document.getElementById("saved-conversations");
    const newConversationBtn = document.getElementById("new-conversation");
    const deleteConversationBtn = document.getElementById("delete-conversation");
    const exportConversationBtn = document.getElementById("export-conversation");
    const shareConversationBtn = document.getElementById("share-conversation");
    const includeContext = document.getElementById("include-task-context");
    const languageSelect = document.getElementById("assistant-language");
    const checkProviderBtn = document.getElementById("check-provider");
    const providerStatus = document.getElementById("provider-status");
    const stopBtn = document.getElementById("assistant-stop");
    const shareStatus = document.getElementById("share-chat-status");
    const initialGreeting = log?.querySelector(".bubble.bot")?.textContent || "Hi! Ask me a question or attach code for review.";
    let recognition = null;
    let selectedVoice = null;
    let isAsking = false;
    const conversation = [];
    let conversationId = null;
    let activeRequest = null;
    let lastFailedRequest = null;

    function csrfToken() {
        return document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
    }

    async function apiRequest(url, options = {}) {
        const token = csrfToken();
        const headers = new Headers(options.headers || {});
        if (options.method === "POST" && token) headers.set("X-CSRFToken", token);
        const response = await fetch(url, {...options, headers});
        const data = await response.json().catch(() => null);
        if (!response.ok) {
            throw new Error(data?.error || `The request failed (HTTP ${response.status}).`);
        }
        return data;
    }

    function resetConversation(messages = []) {
        conversation.length = 0;
        conversation.push(...messages
            .filter(message => message && ["user", "model"].includes(message.role) && typeof message.text === "string")
            .slice(-12)
            .map(message => ({role: message.role, text: message.text})));
        if (log) {
            log.replaceChildren();
            appendMessage(initialGreeting, "bot");
            for (const message of messages) {
                if (!message || typeof message.text !== "string") continue;
                if (message.role === "user") {
                    appendMessage(message.text, "user");
                } else if (message.role === "model") {
                    const answer = appendMessage(message.text, "bot");
                    addAnswerTools(answer, message.text);
                    if (message.provider) {
                        const attribution = document.createElement("small");
                        attribution.className = "provider-attribution";
                        const providerName = {
                            gemini: "Gemini",
                            groq: "GroqCloud",
                            ollama: "Ollama",
                            external: "External AI"
                        }[message.provider] || message.provider;
                        attribution.textContent = `Answered by ${providerName}${message.model ? ` · ${message.model}` : ""}`;
                        answer.appendChild(attribution);
                    }
                }
            }
        }
    }

    async function refreshConversationList() {
        if (!conversationSelect) return;
        const data = await apiRequest("/assistant/conversations/");
        conversationSelect.replaceChildren(new Option("Current conversation", ""));
        data.conversations.forEach(item => {
            const option = new Option(item.title, item.id);
            conversationSelect.add(option);
        });
        conversationSelect.value = conversationId ? String(conversationId) : "";
        if (deleteConversationBtn) deleteConversationBtn.disabled = !conversationId;
    }

    async function startNewConversation() {
        if (isAsking) activeRequest?.abort();
        const item = await apiRequest("/assistant/conversations/", {method: "POST"});
        conversationId = item.id;
        lastFailedRequest = null;
        resetConversation();
        await refreshConversationList();
    }

    async function openConversation(id) {
        if (!id) {
            conversationId = null;
            resetConversation();
            if (deleteConversationBtn) deleteConversationBtn.disabled = true;
            return;
        }
        const item = await apiRequest(`/assistant/conversations/${encodeURIComponent(id)}/`);
        conversationId = item.id;
        lastFailedRequest = null;
        resetConversation(item.messages || []);
        if (deleteConversationBtn) deleteConversationBtn.disabled = false;
    }

    function transcriptText() {
        return log ? [...log.querySelectorAll(".bubble")].map(message => {
            const copy = message.cloneNode(true);
            copy.querySelectorAll(".message-tools, .provider-attribution").forEach(node => node.remove());
            return `${message.classList.contains("user") ? "You" : "Assistant"}: ${copy.textContent.trim()}`;
        }).join("\n\n") : "";
    }

    function addAnswerTools(answerMessage, text) {
        if (!answerMessage) return;
        const tools = document.createElement("div");
        tools.className = "message-tools";
        const copyButton = document.createElement("button");
        copyButton.type = "button";
        copyButton.className = "btn small";
        copyButton.textContent = "Copy answer";
        copyButton.addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(text);
                copyButton.textContent = "Copied";
                window.setTimeout(() => { copyButton.textContent = "Copy answer"; }, 1600);
            } catch {
                copyButton.textContent = "Copy unavailable";
            }
        });
        tools.appendChild(copyButton);
        answerMessage.querySelectorAll("pre code").forEach(code => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn small";
            button.textContent = "Copy code";
            button.addEventListener("click", async () => {
                try {
                    await navigator.clipboard.writeText(code.textContent);
                    button.textContent = "Copied";
                    window.setTimeout(() => { button.textContent = "Copy code"; }, 1600);
                } catch {
                    button.textContent = "Copy unavailable";
                }
            });
            code.parentElement.appendChild(button);
        });
        answerMessage.appendChild(tools);
    }

    function renderInlineText(parent, text) {
        const tokenPattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
        let lastIndex = 0;
        for (const match of text.matchAll(tokenPattern)) {
            parent.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
            const token = match[0];
            const element = token.startsWith("**")
                ? document.createElement("strong")
                : document.createElement("code");
            element.textContent = token.startsWith("**") ? token.slice(2, -2) : token.slice(1, -1);
            parent.appendChild(element);
            lastIndex = match.index + token.length;
        }
        parent.appendChild(document.createTextNode(text.slice(lastIndex)));
    }

    function renderAssistantText(parent, text) {
        const blocks = text.split(/```([^\n`]*)\n?([\s\S]*?)```/g);
        for (let index = 0; index < blocks.length; index += 3) {
            const prose = blocks[index].trim();
            if (prose) {
                prose.split(/\n{2,}/).forEach(block => {
                    const lines = block.split("\n");
                    const heading = lines.length === 1 && lines[0].match(/^#{1,3}\s+(.+)$/);
                    if (heading) {
                        const title = document.createElement("h3");
                        renderInlineText(title, heading[1]);
                        parent.appendChild(title);
                        return;
                    }
                    const isList = lines.every(line => /^\s*(?:[-*]|\d+\.)\s+/.test(line));
                    if (isList) {
                        const ordered = /^\s*\d+\./.test(lines[0]);
                        const list = document.createElement(ordered ? "ol" : "ul");
                        lines.forEach(line => {
                            const item = document.createElement("li");
                            renderInlineText(item, line.replace(/^\s*(?:[-*]|\d+\.)\s+/, ""));
                            list.appendChild(item);
                        });
                        parent.appendChild(list);
                        return;
                    }
                    const paragraph = document.createElement("p");
                    lines.forEach((line, lineIndex) => {
                        if (lineIndex) paragraph.appendChild(document.createElement("br"));
                        renderInlineText(paragraph, line);
                    });
                    parent.appendChild(paragraph);
                });
            }
            if (index + 2 < blocks.length) {
                const pre = document.createElement("pre");
                const code = document.createElement("code");
                code.textContent = blocks[index + 2].replace(/\n$/, "");
                pre.appendChild(code);
                parent.appendChild(pre);
            }
        }
    }

    function appendMessage(text, sender, extraClass = "") {
        if (!log) return null;
        const msg = document.createElement("div");
        msg.className = `bubble ${sender} ${extraClass}`.trim();
        if (sender === "bot" && !extraClass.includes("loading")) {
            renderAssistantText(msg, text);
        } else {
            msg.textContent = text;
        }
        log.appendChild(msg);
        log.scrollTop = log.scrollHeight;
        return msg;
    }

    async function ask(q, retryCode = null) {
        if (isAsking) return;
        const attachedCode = retryCode === null
            ? (codeText ? codeText.value.trim() : "")
            : retryCode;
        q = (q || "").trim();
        if (!q && !attachedCode) return;
        if (!q) q = "Please review this code.";
        if (!log || !input) return;

        const csrf = csrfToken();
        if (!csrf) {
            appendMessage("The request could not be sent because the security token is missing. Refresh the page and try again.", "bot");
            return;
        }
        appendMessage(q, "user");
        input.value = "";
        if (codeText) codeText.value = "";
        const body = new URLSearchParams({
            question: q,
            code_text: attachedCode,
            history: JSON.stringify(conversation.slice(-12)),
            provider: providerSelect ? providerSelect.value : "auto",
            conversation_id: conversationId || "",
            include_context: includeContext?.checked ? "true" : "false",
            language: languageSelect?.value || "auto"
        });
        const loading = appendMessage("Thinking", "bot", "loading");
        isAsking = true;
        activeRequest = new AbortController();
        lastFailedRequest = {question: q, code: attachedCode};
        if (sendBtn) sendBtn.disabled = true;
        if (stopBtn) stopBtn.hidden = false;
        document.querySelectorAll(".suggestions button").forEach(button => {
            button.disabled = true;
        });
        if (form) form.setAttribute("aria-busy", "true");
        if (assistantStatus) assistantStatus.textContent = "Thinking…";
        try {
            const res = await fetch("/assistant/ask/", {
                method: "POST",
                headers: {"X-CSRFToken": csrf, "Content-Type": "application/x-www-form-urlencoded"},
                body,
                signal: activeRequest.signal
            });
            const data = await res.json().catch(() => null);
            if (!res.ok) {
                throw new Error((data && data.error) || `The request failed (HTTP ${res.status}).`);
            }
            if (!data || typeof data.answer !== "string") {
                throw new Error("The assistant returned an unreadable response. Please try again.");
            }
            if (loading) loading.remove();
            const answer = data.answer || "The assistant returned an empty response. Please try again.";
            conversation.push({
                role: "user",
                text: attachedCode ? `${q}\n\nCode:\n${attachedCode}` : q
            });
            conversation.push({role: "model", text: answer});
            conversationId = data.conversation_id || conversationId;
            if (conversation.length > 12) conversation.splice(0, conversation.length - 12);
            const answerMessage = appendMessage(answer, "bot");
            addAnswerTools(answerMessage, answer);
            if (answerMessage && data.provider) {
                const providerName = {
                    gemini: "Gemini",
                    groq: "GroqCloud",
                    ollama: "Ollama",
                    external: "External AI"
                }[data.provider] || data.provider;
                const attribution = document.createElement("small");
                attribution.className = "provider-attribution";
                attribution.textContent = `Answered by ${providerName}${data.model ? ` · ${data.model}` : ""}`;
                answerMessage.appendChild(attribution);
            }
            lastFailedRequest = null;
            await refreshConversationList();
        } catch (error) {
            if (loading) loading.remove();
            if (error.name === "AbortError") {
                appendMessage("Stopped waiting for this response. The provider may still finish processing the request. Use Retry to ask again.", "bot");
                return;
            }
            const message = error instanceof TypeError
                ? "Could not connect to the assistant. Check your connection and try again."
                : error.message || "The assistant could not complete your request. Please try again.";
            const errorMessage = appendMessage(message, "bot");
            if (errorMessage) {
                const retry = document.createElement("button");
                retry.type = "button";
                retry.className = "btn small";
                retry.textContent = "Retry";
                retry.addEventListener("click", () => {
                    if (lastFailedRequest) ask(lastFailedRequest.question, lastFailedRequest.code);
                });
                errorMessage.appendChild(retry);
            }
        } finally {
            isAsking = false;
            activeRequest = null;
            if (sendBtn) sendBtn.disabled = false;
            if (stopBtn) stopBtn.hidden = true;
            document.querySelectorAll(".suggestions button").forEach(button => {
                button.disabled = false;
            });
            if (form) form.removeAttribute("aria-busy");
            if (assistantStatus) assistantStatus.textContent = "Ready to help";
        }
    }

    function setListening(isListening) {
        if (!assistantStatus) return;
        assistantStatus.textContent = isListening ? "Listening..." : "Ready to help";
    }

    function setSpeaking(isSpeaking) {
        if (!assistantStatus) return;
        assistantStatus.textContent = isSpeaking ? "Talking..." : "Ready to help";
    }

    function speakAnswer(text) {
        if (!window.speechSynthesis || !text) return;
        const utterance = new SpeechSynthesisUtterance(text);
        if (selectedVoice) {
            utterance.voice = selectedVoice;
        }
        utterance.rate = 1;
        utterance.onstart = () => setSpeaking(true);
        utterance.onend = () => setSpeaking(false);
        utterance.onerror = () => setSpeaking(false);
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
    }

    function initVoiceAssistant() {
        const inputField = input || document.getElementById("chat-input");
        const chatForm = form || document.getElementById("chat-form");
        if (!voiceBtn || !inputField) return;

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            console.warn("Web Speech API is not supported in this browser environment.");
            voiceBtn.title = "Voice input unavailable - please use text input";
            voiceBtn.classList.add("disabled");
            return;
        }

        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = "en-US";
        recognition.onstart = () => {
            voiceBtn.classList.add("listening");
            voiceBtn.setAttribute("aria-pressed", "true");
            setListening(true);
        };
        recognition.onresult = event => {
            voiceBtn.classList.remove("listening");
            voiceBtn.setAttribute("aria-pressed", "false");
            const transcript = event.results[0][0].transcript;
            inputField.value = transcript;
            if (chatForm) {
                chatForm.requestSubmit();
            } else {
                ask(transcript);
            }
        };
        recognition.onerror = event => {
            voiceBtn.classList.remove("listening");
            voiceBtn.setAttribute("aria-pressed", "false");
            setListening(false);
            console.warn("Speech recognition error:", event.error);
            if (["not-allowed", "audio-capture", "network", "no-speech"].includes(event.error)) {
                alert(`Voice input error (${event.error}). Please type your command manually in the text box.`);
            } else {
                appendMessage("Voice recognition error. Please try again or type your request.", "bot");
            }
        };
        recognition.onend = () => {
            voiceBtn.classList.remove("listening");
            voiceBtn.setAttribute("aria-pressed", "false");
            setListening(false);
        };

        voiceBtn.addEventListener("click", event => {
            event.preventDefault();
            try {
                recognition.start();
            } catch (error) {
                voiceBtn.classList.remove("listening");
                voiceBtn.setAttribute("aria-pressed", "false");
                console.error("Failed to start speech recognition:", error);
                alert("Microphone access is currently unavailable. You can type your request directly into the chat input.");
            }
        });
    }

    initVoiceAssistant();

    if (form) {
        form.addEventListener("submit", e => {
            e.preventDefault();
            ask(input.value);
        });
        document.querySelectorAll(".suggestions button").forEach(btn => {
            btn.addEventListener("click", () => ask(btn.dataset.q));
        });
    }

    if (speakBtn) {
        speakBtn.addEventListener("click", e => {
            e.preventDefault();
            const messages = log ? log.querySelectorAll(".bubble.bot:not(.loading)") : [];
            speakAnswer(messages.length ? messages[messages.length - 1].textContent : "");
        });
    }

    if (stopBtn) stopBtn.addEventListener("click", () => activeRequest?.abort());
    if (newConversationBtn) {
        newConversationBtn.addEventListener("click", () => {
            startNewConversation().catch(error => {
                if (shareStatus) shareStatus.textContent = error.message;
            });
        });
    }
    if (conversationSelect) {
        conversationSelect.addEventListener("change", () => {
            openConversation(conversationSelect.value).catch(error => {
                if (shareStatus) shareStatus.textContent = error.message;
            });
        });
    }
    if (deleteConversationBtn) {
        deleteConversationBtn.addEventListener("click", async () => {
            if (!conversationId || !window.confirm("Delete this saved conversation?")) return;
            try {
                await apiRequest(`/assistant/conversations/${conversationId}/delete/`, {method: "POST"});
                conversationId = null;
                resetConversation();
                await refreshConversationList();
            } catch (error) {
                if (shareStatus) shareStatus.textContent = error.message;
            }
        });
    }
    if (exportConversationBtn) {
        exportConversationBtn.addEventListener("click", () => {
            const content = transcriptText();
            if (!content) return;
            const blob = new Blob([content], {type: "text/plain;charset=utf-8"});
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = "assistant-conversation.txt";
            link.click();
            URL.revokeObjectURL(url);
        });
    }
    if (shareConversationBtn) {
        shareConversationBtn.addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(transcriptText());
                if (shareStatus) shareStatus.textContent = "Conversation copied. Share it wherever you choose.";
            } catch {
                if (shareStatus) shareStatus.textContent = "Clipboard access is unavailable. Use Export chat instead.";
            }
        });
    }
    if (checkProviderBtn) {
        providerSelect?.addEventListener("change", () => {
            if (providerStatus) providerStatus.textContent = "";
        });
        checkProviderBtn.addEventListener("click", async () => {
            const provider = providerSelect?.value;
            if (!["gemini", "groq", "ollama"].includes(provider)) {
                if (providerStatus) providerStatus.textContent = "Choose a specific cloud or Ollama provider to check.";
                return;
            }
            checkProviderBtn.disabled = true;
            if (providerStatus) providerStatus.textContent = "Checking provider…";
            try {
                const result = await apiRequest("/assistant/providers/check/", {
                    method: "POST",
                    headers: {"Content-Type": "application/x-www-form-urlencoded"},
                    body: new URLSearchParams({provider})
                });
                const labels = {
                    available: "Connected; configured model is available.",
                    not_configured: "Provider is not configured.",
                    model_missing: result.message,
                    unavailable: result.message
                };
                if (providerStatus) providerStatus.textContent = labels[result.status] || "Provider status unknown.";
            } catch (error) {
                if (providerStatus) providerStatus.textContent = error.message;
            } finally {
                checkProviderBtn.disabled = false;
            }
        });
    }

    if (conversationSelect) {
        refreshConversationList()
            .then(async () => {
                const latest = conversationSelect.options[1]?.value;
                if (latest) await openConversation(latest);
            })
            .catch(error => {
                if (shareStatus) shareStatus.textContent = `Could not load saved conversations: ${error.message}`;
            });
    }

    function selectVoice() {
        if (!window.speechSynthesis) return;
        const voices = window.speechSynthesis.getVoices();
        selectedVoice = voices.find(voice => voice.default) || voices[0] || null;
    }

    if (window.speechSynthesis) {
        window.speechSynthesis.onvoiceschanged = selectVoice;
        selectVoice();
    }

    setListening(false);
    setSpeaking(false);

    // Kanban drag/drop
    let dragged = null;
    document.querySelectorAll(".kanban-card").forEach(card => {
        card.addEventListener("dragstart", () => { dragged = card; });
    });
    document.querySelectorAll(".kanban-col").forEach(col => {
        col.addEventListener("dragover", e => e.preventDefault());
        col.addEventListener("drop", async e => {
            e.preventDefault();
            if (!dragged) return;
            col.querySelector(".dropzone").appendChild(dragged);
            const csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");
            const csrf = csrfInput ? csrfInput.value : "";
            const body = new URLSearchParams({task_id: dragged.dataset.task, status: col.dataset.status});
            await fetch("/tasks/kanban/update/", {
                method:"POST",
                headers: {"X-CSRFToken": csrf, "Content-Type":"application/x-www-form-urlencoded"},
                body

        
            });
        });
    });
});
