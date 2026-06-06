// ================= STATE MANAGEMENT =================
let currentUser = null;
let activeSessionId = null;
let memoriesList = [];

// ================= SELECTORS =================
const authScreen = document.getElementById("auth-screen");
const dashboardScreen = document.getElementById("dashboard-screen");
const loginView = document.getElementById("login-view");
const registerView = document.getElementById("register-view");
const legacyView = document.getElementById("legacy-view");
const authStatus = document.getElementById("auth-status");

const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const legacyForm = document.getElementById("legacy-form");

const linkToRegister = document.getElementById("link-to-register");
const linkToLogin = document.getElementById("link-to-login");

// Sidebar
const userDisplayName = document.getElementById("user-display-name");
const userDisplayId = document.getElementById("user-display-id");
const navChatBtn = document.getElementById("nav-chat-btn");
const navMemoriesBtn = document.getElementById("nav-memories-btn");
const logoutBtn = document.getElementById("logout-btn");
const newChatBtn = document.getElementById("new-chat-btn");
const sessionsListContainer = document.getElementById("sessions-list-container");

// Views
const chatView = document.getElementById("chat-view");
const memoriesView = document.getElementById("memories-view");

// Chat
const chatMessagesContainer = document.getElementById("chat-messages-container");
const chatInputForm = document.getElementById("chat-input-form");
const chatMessageInput = document.getElementById("chat-message-input");

// Memories
const memoryCreateForm = document.getElementById("memory-create-form");
const memoryContentInput = document.getElementById("memory-content-input");
const memorySearchInput = document.getElementById("memory-search-input");
const memoriesGridContainer = document.getElementById("memories-grid-container");

// ================= UTILITIES =================

function generateSessionId() {
    return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
}

function showScreen(screenId) {
    if (screenId === "auth") {
        authScreen.classList.add("active");
        dashboardScreen.classList.remove("active");
    } else {
        authScreen.classList.remove("active");
        dashboardScreen.classList.add("active");
    }
}

function showAuthView(viewName) {
    authStatus.style.display = "none";
    loginView.classList.remove("active");
    registerView.classList.remove("active");
    legacyView.classList.remove("active");
    
    if (viewName === "login") loginView.classList.add("active");
    else if (viewName === "register") registerView.classList.add("active");
    else if (viewName === "legacy") legacyView.classList.add("active");
}

function showAuthStatus(message, type = "error") {
    authStatus.textContent = message;
    authStatus.className = `auth-status-message ${type}`;
    authStatus.style.display = "block";
}

// Simple Markdown Parser for chat rendering
function parseMarkdown(text) {
    if (!text) return "";
    let html = text;
    
    // Escape HTML to prevent XSS
    html = html.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    
    // Code blocks
    html = html.replace(/```([\s\S]*?)```/g, function(match, code) {
        return `<pre><code>${code.trim()}</code></pre>`;
    });
    
    // Inline code
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    
    // Bold
    html = html.replace(/\*\*([\s\S]*?)\*\*/g, "<strong>$1</strong>");
    
    // Unordered lists
    html = html.replace(/^\s*[-*]\s+(.+)$/gm, "<li>$1</li>");
    html = html.replace(/(<li>.*<\/li>)/g, "<ul>$1</ul>");
    html = html.replace(/<\/ul>\s*<ul>/g, "");
    
    // Ordered lists
    html = html.replace(/^\s*\d+\.\s+(.+)$/gm, "<li>$1</li>");
    html = html.replace(/(<li>.*<\/li>)/g, function(match) {
        if (match.includes("<ul>")) return match;
        return `<ol>${match}</ol>`;
    });
    html = html.replace(/<\/ol>\s*<ol>/g, "");
    
    // Paragraphs
    let blocks = html.split(/\n\n+/);
    html = blocks.map(block => {
        block = block.trim();
        if (block.startsWith("<pre>") || block.startsWith("<ul>") || block.startsWith("<ol>")) {
            return block;
        }
        return `<p>${block.replace(/\n/g, "<br>")}</p>`;
    }).join("\n");
    
    return html;
}

// ================= API CALLS =================

async function handleLogin(username, password) {
    try {
        const response = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Authentication failed.");
        }
        
        if (data.status === "update_required") {
            // Legacy user needs password setup
            currentUser = { username: data.username, user_id: data.user_id };
            showAuthView("legacy");
            showAuthStatus("Legacy profile detected. Please set a password to continue.", "success");
        } else {
            // Success
            completeLogin(data.user_id, data.username);
        }
    } catch (err) {
        showAuthStatus(err.message);
    }
}

async function handleRegister(username, password) {
    try {
        const response = await fetch("/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Registration failed.");
        }
        
        showAuthView("login");
        showAuthStatus("Profile created successfully! Please log in.", "success");
    } catch (err) {
        showAuthStatus(err.message);
    }
}

async function handleLegacyUpdate(password) {
    try {
        const response = await fetch("/api/auth/update_password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: currentUser.username, password })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Failed to set password.");
        }
        
        completeLogin(data.user_id, data.username);
    } catch (err) {
        showAuthStatus(err.message);
    }
}

function completeLogin(userId, username) {
    currentUser = { user_id: userId, username: username };
    
    // UI Updates
    userDisplayName.textContent = currentUser.username;
    userDisplayId.textContent = `ID: ${currentUser.user_id}`;
    
    // Load state
    loadSessions();
    loadMemories();
    
    showScreen("dashboard");
}

async function loadSessions(selectSessionId = null) {
    if (!currentUser) return;
    try {
        const response = await fetch(`/api/sessions?user_id=${currentUser.user_id}`);
        const data = await response.json();
        
        if (data.status === "success") {
            const sessions = data.sessions || [];
            
            // Determine activeSessionId
            let storedSessionId = selectSessionId || localStorage.getItem("active_session_id");
            let sessionExists = sessions.some(s => s.session_id === storedSessionId);
            
            if (sessionExists) {
                activeSessionId = storedSessionId;
            } else if (sessions.length > 0) {
                activeSessionId = sessions[0].session_id;
            } else {
                // No sessions exist, create one
                await createNewSession();
                return;
            }
            
            localStorage.setItem("active_session_id", activeSessionId);
            
            // Render list
            sessionsListContainer.innerHTML = "";
            sessions.forEach(session => {
                const itemDiv = document.createElement("div");
                itemDiv.className = `session-item${session.session_id === activeSessionId ? ' active' : ''}`;
                itemDiv.dataset.sessionId = session.session_id;
                
                // Icon
                const iconSpan = document.createElement("span");
                iconSpan.className = "session-item-icon";
                iconSpan.textContent = "💬";
                itemDiv.appendChild(iconSpan);
                
                // Title
                const titleSpan = document.createElement("span");
                titleSpan.className = "session-item-title";
                titleSpan.textContent = session.title || "New Conversation";
                itemDiv.appendChild(titleSpan);
                
                // Actions container
                const actionsDiv = document.createElement("div");
                actionsDiv.className = "session-item-actions";
                
                // Rename button
                const renameBtn = document.createElement("button");
                renameBtn.className = "btn-session-action";
                renameBtn.title = "Rename conversation";
                renameBtn.textContent = "✏️";
                renameBtn.addEventListener("click", (e) => {
                    e.stopPropagation(); // Prevent selecting the session
                    startRenameSession(session.session_id, titleSpan);
                });
                actionsDiv.appendChild(renameBtn);
                
                // Delete button
                const deleteBtn = document.createElement("button");
                deleteBtn.className = "btn-session-action delete-hover";
                deleteBtn.title = "Delete conversation";
                deleteBtn.textContent = "🗑️";
                deleteBtn.addEventListener("click", (e) => {
                    e.stopPropagation(); // Prevent selecting the session
                    confirmDeleteSession(session.session_id);
                });
                actionsDiv.appendChild(deleteBtn);
                
                itemDiv.appendChild(actionsDiv);
                
                // Click item to load session
                itemDiv.addEventListener("click", () => {
                    if (activeSessionId !== session.session_id) {
                        activeSessionId = session.session_id;
                        localStorage.setItem("active_session_id", activeSessionId);
                        // Refresh active classes in UI
                        document.querySelectorAll(".session-item").forEach(el => el.classList.remove("active"));
                        itemDiv.classList.add("active");
                        loadChatHistory();
                    }
                });
                
                sessionsListContainer.appendChild(itemDiv);
            });
        }
    } catch (err) {
        console.error("Failed to load sessions", err);
    }
}

function startRenameSession(sessionId, titleSpan) {
    const currentTitle = titleSpan.textContent;
    const input = document.createElement("input");
    input.type = "text";
    input.className = "session-item-rename-input";
    input.value = currentTitle;
    
    // Replace titleSpan with input
    const parent = titleSpan.parentNode;
    parent.replaceChild(input, titleSpan);
    input.focus();
    input.select();
    
    let finished = false;
    
    async function finishRename() {
        if (finished) return;
        finished = true;
        
        const newTitle = input.value.trim();
        if (newTitle && newTitle !== currentTitle) {
            try {
                const response = await fetch(`/api/sessions/${sessionId}/title`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        user_id: currentUser.user_id,
                        title: newTitle
                    })
                });
                const data = await response.json();
                if (response.ok && data.status === "success") {
                    titleSpan.textContent = newTitle;
                } else {
                    titleSpan.textContent = currentTitle;
                    alert(data.detail || "Failed to rename session.");
                }
            } catch (err) {
                titleSpan.textContent = currentTitle;
                console.error("Error renaming session", err);
            }
        } else {
            titleSpan.textContent = currentTitle;
        }
        
        // Restore titleSpan
        if (input.parentNode === parent) {
            parent.replaceChild(titleSpan, input);
        }
    }
    
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            finishRename();
        } else if (e.key === "Escape") {
            e.preventDefault();
            finished = true;
            if (input.parentNode === parent) {
                parent.replaceChild(titleSpan, input);
            }
        }
    });
    
    input.addEventListener("blur", () => {
        finishRename();
    });
}

async function confirmDeleteSession(sessionId) {
    if (!confirm("Are you sure you want to delete this conversation? All chat history for this session will be permanently deleted.")) {
        return;
    }
    
    try {
        const response = await fetch(`/api/sessions/${sessionId}?user_id=${currentUser.user_id}`, {
            method: "DELETE"
        });
        const data = await response.json();
        
        if (response.ok && data.status === "success") {
            if (activeSessionId === sessionId) {
                activeSessionId = null;
                localStorage.removeItem("active_session_id");
            }
            loadSessions();
        } else {
            alert(data.detail || "Failed to delete session.");
        }
    } catch (err) {
        console.error("Error deleting session", err);
    }
}

async function createNewSession() {
    if (!currentUser) return;
    try {
        const response = await fetch(`/api/sessions?user_id=${currentUser.user_id}`, {
            method: "POST"
        });
        const data = await response.json();
        
        if (response.ok && data.status === "success") {
            activeSessionId = data.session_id;
            localStorage.setItem("active_session_id", activeSessionId);
            await loadSessions(activeSessionId);
        } else {
            alert(data.detail || "Failed to create new session.");
        }
    } catch (err) {
        console.error("Error creating session", err);
    }
}

async function loadChatHistory() {
    chatMessagesContainer.innerHTML = "";
    
    try {
        const response = await fetch(`/api/chat/history/${activeSessionId}?user_id=${currentUser.user_id}`);
        const data = await response.json();
        
        if (data.status === "success" && data.history && data.history.length > 0) {
            data.history.forEach(msg => {
                appendMessageToUI(msg.role, msg.content, msg.intent);
            });
        } else {
            renderWelcomeCard();
        }
    } catch (err) {
        console.error("Failed to load chat history", err);
        renderWelcomeCard();
    }
}

function renderWelcomeCard() {
    chatMessagesContainer.innerHTML = `
        <div class="welcome-message-card">
            <div class="card-icon">🤖</div>
            <h3>How can I assist you today?</h3>
            <p>You can talk to me naturally. The Manager Agent will analyze your request and route it to the appropriate processor:</p>
            <div class="routing-explanation-grid">
                <div class="explanation-pill pill-knowledge">💾 <strong>Knowledge</strong>: "Remember I enjoy reading about quantum physics" or "What do I like to read?"</div>
                <div class="explanation-pill pill-planner">📅 <strong>Planner</strong>: "Plan a trip to Japan for next month" or "Help me draft a study plan"</div>
                <div class="explanation-pill pill-decision">⚖️ <strong>Decision</strong>: "Compare React vs Vue for a local project" or "Help me decide on a database"</div>
            </div>
        </div>
    `;
}

async function sendChatMessage(messageText) {
    // 1. Remove welcome card if it is there
    const welcomeCard = chatMessagesContainer.querySelector(".welcome-message-card");
    if (welcomeCard) {
        chatMessagesContainer.innerHTML = "";
    }
    
    // 2. Append User message
    appendMessageToUI("user", messageText);
    
    // 3. Append Typing Indicator
    const typingIndicator = appendTypingIndicator();
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    
    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: currentUser.user_id,
                session_id: activeSessionId,
                message: messageText
            })
        });
        
        const data = await response.json();
        
        // Remove typing indicator
        typingIndicator.remove();
        
        if (!response.ok) {
            throw new Error(data.detail || "Server error processing chat.");
        }
        
        // 4. Append Assistant Response
        appendMessageToUI("assistant", data.response, data.intent);
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
        
        // Reload memories dynamically if user just told the system to remember something
        if (data.intent === "KNOWLEDGE") {
            loadMemories();
        }
        
        // Reload sessions to update title or order
        loadSessions(activeSessionId);
    } catch (err) {
        typingIndicator.remove();
        appendMessageToUI("assistant", `⚠️ Error: ${err.message}`, "SYSTEM");
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    }
}

async function loadMemories() {
    try {
        const response = await fetch(`/api/memories?user_id=${currentUser.user_id}`);
        const data = await response.json();
        
        if (data.status === "success") {
            memoriesList = data.memories;
            filterAndRenderMemories("");
        }
    } catch (err) {
        console.error("Failed to load memories", err);
    }
}

async function saveMemory(content) {
    try {
        const response = await fetch("/api/memories", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: currentUser.user_id,
                content: content
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Failed to save memory.");
        }
        
        // Clear input
        memoryContentInput.value = "";
        
        // Reload
        loadMemories();
    } catch (err) {
        alert(err.message);
    }
}

async function deleteMemory(memoryId) {
    if (!confirm("Are you sure you want to delete this memory? It will be removed from your long-term storage and vector store.")) {
        return;
    }
    
    try {
        const response = await fetch(`/api/memories/${memoryId}?user_id=${currentUser.user_id}`, {
            method: "DELETE"
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Failed to delete memory.");
        }
        
        // Reload
        loadMemories();
    } catch (err) {
        alert(err.message);
    }
}

async function clearChatHistory() {
    if (!confirm("Are you sure you want to clear current chat history? Stored memories will not be affected.")) {
        return;
    }
    
    try {
        const response = await fetch(`/api/chat/history/${activeSessionId}?user_id=${currentUser.user_id}`, {
            method: "DELETE"
        });
        
        if (response.ok) {
            loadChatHistory();
        }
    } catch (err) {
        console.error("Failed to clear chat history", err);
    }
}

// ================= RENDERING HELPERS =================

function appendMessageToUI(role, content, intent = null) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${role}`;
    
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.innerHTML = parseMarkdown(content);
    msgDiv.appendChild(bubble);
    
    const meta = document.createElement("div");
    meta.className = "message-meta";
    
    const timestampStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    if (role === "assistant" && intent) {
        const tag = document.createElement("span");
        tag.className = `agent-tag tag-${intent.toLowerCase()}`;
        tag.textContent = intent;
        meta.appendChild(tag);
    }
    
    const timeSpan = document.createElement("span");
    timeSpan.className = "msg-time";
    timeSpan.textContent = timestampStr;
    meta.appendChild(timeSpan);
    
    msgDiv.appendChild(meta);
    chatMessagesContainer.appendChild(msgDiv);
}

function appendTypingIndicator() {
    const msgDiv = document.createElement("div");
    msgDiv.className = "message assistant typing";
    
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.innerHTML = `
        <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;
    msgDiv.appendChild(bubble);
    chatMessagesContainer.appendChild(msgDiv);
    return msgDiv;
}

function filterAndRenderMemories(filterQuery) {
    memoriesGridContainer.innerHTML = "";
    
    const filtered = memoriesList.filter(mem => 
        mem.content.toLowerCase().includes(filterQuery.toLowerCase())
    );
    
    if (filtered.length === 0) {
        memoriesGridContainer.innerHTML = `
            <div class="no-memories-fallback">
                <span class="fallback-icon">📭</span>
                <h4>No memories found</h4>
                <p>${filterQuery ? "Try a different search term." : "Use the form on the left or talk in chat to save memories!"}</p>
            </div>
        `;
        return;
    }
    
    filtered.forEach(mem => {
        const card = document.createElement("div");
        card.className = "memory-card";
        
        // Format date: YYYY-MM-DD HH:MM
        const dateStr = mem.created_at.substring(0, 16).replace("T", " ");
        
        card.innerHTML = `
            <div class="memory-card-body">
                "${escapeHtml(mem.content)}"
            </div>
            <div class="memory-card-footer">
                <div>
                    <span class="memory-card-id">ID: ${mem.memory_id}</span>
                    <span class="memory-card-date">${dateStr}</span>
                </div>
                <button class="btn-trash" title="Delete memory" onclick="deleteMemory(${mem.memory_id})">
                    🗑️
                </button>
            </div>
        `;
        memoriesGridContainer.appendChild(card);
    });
}

function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// ================= EVENT LISTENERS =================

// Auth Navigation
linkToRegister.addEventListener("click", (e) => {
    e.preventDefault();
    showAuthView("register");
});

linkToLogin.addEventListener("click", (e) => {
    e.preventDefault();
    showAuthView("login");
});

// Auth Forms
loginForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value;
    handleLogin(username, password);
});

registerForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const username = document.getElementById("register-username").value.trim();
    const password = document.getElementById("register-password").value;
    const confirmPassword = document.getElementById("register-confirm-password").value;
    
    if (password !== confirmPassword) {
        showAuthStatus("Passwords do not match.");
        return;
    }
    handleRegister(username, password);
});

legacyForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const password = document.getElementById("legacy-password").value;
    const confirm = document.getElementById("legacy-confirm-password").value;
    
    if (password !== confirm) {
        showAuthStatus("Passwords do not match.");
        return;
    }
    handleLegacyUpdate(password);
});

// View Navigation
navChatBtn.addEventListener("click", () => {
    navChatBtn.classList.add("active");
    navMemoriesBtn.classList.remove("active");
    chatView.classList.add("active");
    memoriesView.classList.remove("active");
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
});

navMemoriesBtn.addEventListener("click", () => {
    navMemoriesBtn.classList.add("active");
    navChatBtn.classList.remove("active");
    memoriesView.classList.add("active");
    chatView.classList.remove("active");
});

// Chat form submission
chatInputForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const message = chatMessageInput.value.trim();
    if (!message) return;
    
    chatMessageInput.value = "";
    sendChatMessage(message);
});

// Send on Enter (but new line on Shift+Enter)
chatMessageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        chatInputForm.dispatchEvent(new Event("submit"));
    }
});

// Auto-grow input text area
chatMessageInput.addEventListener("input", function() {
    this.style.height = "auto";
    this.style.height = (this.scrollHeight - 16) + "px";
});

// Memory control forms
memoryCreateForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const content = memoryContentInput.value.trim();
    if (!content) return;
    saveMemory(content);
});

memorySearchInput.addEventListener("input", (e) => {
    filterAndRenderMemories(e.target.value);
});

// Sidebar action events
if (newChatBtn) {
    newChatBtn.addEventListener("click", () => {
        // Go back to chat console if we are in memory manager view
        navChatBtn.click();
        createNewSession();
    });
}

logoutBtn.addEventListener("click", () => {
    if (confirm("Are you sure you want to log out?")) {
        currentUser = null;
        activeSessionId = null;
        memoriesList = [];
        localStorage.removeItem("active_session_id");
        
        // Reset forms
        loginForm.reset();
        registerForm.reset();
        legacyForm.reset();
        
        showAuthView("login");
        showScreen("auth");
    }
});

// Bind globally so onclick on elements can invoke it
window.deleteMemory = deleteMemory;
