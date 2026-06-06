// ================= STATE MANAGEMENT =================
let currentUser = null;
let activeSessionId = null;
let memoriesList = [];
let activeRoadmap = null; // Stored personal active roadmap
let decisionsCount = 0;   // Count of decision analyses run

// Initialize persistent state from LocalStorage
try {
    const storedRoadmap = localStorage.getItem("active_roadmap");
    if (storedRoadmap) {
        activeRoadmap = JSON.parse(storedRoadmap);
    }
    const storedDecisions = localStorage.getItem("decisions_count");
    if (storedDecisions) {
        decisionsCount = parseInt(storedDecisions, 10);
    }
} catch (e) {
    console.error("Failed to restore state from local storage", e);
}

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
const logoutBtn = document.getElementById("logout-btn");
const newChatBtn = document.getElementById("new-chat-btn");
const sessionsListContainer = document.getElementById("sessions-list-container");

// Nav Buttons
const navHomeBtn = document.getElementById("nav-home-btn");
const navChatBtn = document.getElementById("nav-chat-btn");
const navMemoriesBtn = document.getElementById("nav-memories-btn");
const navPlannerBtn = document.getElementById("nav-planner-btn");
const navDecisionBtn = document.getElementById("nav-decision-btn");

// Views
const homeView = document.getElementById("home-view");
const chatView = document.getElementById("chat-view");
const memoriesView = document.getElementById("memories-view");
const plannerView = document.getElementById("planner-view");
const decisionView = document.getElementById("decision-view");

// Home View Widgets
const homeGreeting = document.getElementById("home-greeting");
const statMemoriesCount = document.getElementById("stat-memories-count");
const statActiveRoadmaps = document.getElementById("stat-active-roadmaps");
const statDecisionsCount = document.getElementById("stat-decisions-count");
const homeActiveTasksList = document.getElementById("home-active-tasks-list");
const activeRoadmapTitle = document.getElementById("active-roadmap-title");
const homeRecentMemoriesList = document.getElementById("home-recent-memories-list");
const sysIndexSize = document.getElementById("sys-index-size");

// Chat Console
const chatMessagesContainer = document.getElementById("chat-messages-container");
const chatInputForm = document.getElementById("chat-input-form");
const chatMessageInput = document.getElementById("chat-message-input");
const chatTelemetryContainer = document.getElementById("chat-telemetry-container");
const telemetryRoutingTitle = document.getElementById("telemetry-routing-title");
const telemetryRoutingDesc = document.getElementById("telemetry-routing-desc");

// Memories Agent Workspace
const memoryCreateForm = document.getElementById("memory-create-form");
const memoryContentInput = document.getElementById("memory-content-input");
const memorySearchInput = document.getElementById("memory-search-input");
const memoriesGridContainer = document.getElementById("memories-grid-container");

// Planner Agent Workspace
const plannerForm = document.getElementById("planner-create-form");
const plannerGoalInput = document.getElementById("planner-goal-input");
const plannerRoadmapOutput = document.getElementById("planner-roadmap-output");
const btnActivateRoadmap = document.getElementById("btn-activate-roadmap");
const plannerTelemetryBox = document.getElementById("planner-telemetry-box");
const btnGeneratePlan = document.getElementById("btn-generate-plan");

// Decision Agent Workspace
const decisionForm = document.getElementById("decision-create-form");
const decisionQueryInput = document.getElementById("decision-query-input");
const decisionReportOutput = document.getElementById("decision-report-output");
const decisionTelemetryBox = document.getElementById("decision-telemetry-box");
const btnAnalyzeDecision = document.getElementById("btn-analyze-decision");

// ================= NAVIGATION CONTROL =================

function showScreen(screenId) {
    if (screenId === "auth") {
        authScreen.classList.add("active");
        dashboardScreen.classList.remove("active");
    } else {
        authScreen.classList.remove("active");
        dashboardScreen.classList.add("active");
    }
}

function showView(viewName) {
    // Hide all views
    const views = [homeView, chatView, memoriesView, plannerView, decisionView];
    views.forEach(v => { if (v) v.classList.remove("active"); });

    // Deactivate all nav buttons
    const navButtons = [navHomeBtn, navChatBtn, navMemoriesBtn, navPlannerBtn, navDecisionBtn];
    navButtons.forEach(btn => { if (btn) btn.classList.remove("active"); });

    // Show selected view & active nav state
    if (viewName === "home") {
        homeView.classList.add("active");
        navHomeBtn.classList.add("active");
        updateDashboard();
    } else if (viewName === "chat") {
        chatView.classList.add("active");
        navChatBtn.classList.add("active");
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    } else if (viewName === "memories") {
        memoriesView.classList.add("active");
        navMemoriesBtn.classList.add("active");
        loadMemories();
    } else if (viewName === "planner") {
        plannerView.classList.add("active");
        navPlannerBtn.classList.add("active");
    } else if (viewName === "decision") {
        decisionView.classList.add("active");
        navDecisionBtn.classList.add("active");
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

// ================= DYNAMIC MARKDOWN PARSER =================

function parseMarkdown(text) {
    if (!text) return "";
    
    // 1. Escape HTML
    let html = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
        
    // 2. Code blocks (e.g. ```python)
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function(match, lang, code) {
        return `<pre><code class="language-${lang}">${code.trim()}</code></pre>`;
    });
    
    // 3. Inline code (e.g. `code`)
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    
    // 4. Headers (#, ##, ###)
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
    
    // 5. Bold & Italic (* and **)
    html = html.replace(/\*\*([\s\S]*?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*([\s\S]*?)\*/g, "<em>$1</em>");
    
    // 6. Blockquotes (> quote)
    html = html.replace(/^\>\s+(.*$)/gim, '<blockquote>$1</blockquote>');
    
    // 7. Parse Markdown Tables
    let lines = html.split("\n");
    let inTable = false;
    let tableHtml = "";
    let processedLines = [];
    
    for (let i = 0; i < lines.length; i++) {
        let line = lines[i].trim();
        if (line.startsWith("|") && line.endsWith("|")) {
            if (!inTable) {
                inTable = true;
                tableHtml = "<table>";
            }
            
            // Skip dividers
            if (line.includes("---") || line.includes("===")) {
                continue;
            }
            
            let cells = line.split("|").slice(1, -1).map(c => c.trim());
            let rowType = tableHtml.includes("<thead>") ? "td" : "th";
            let rowHtml = "<tr>" + cells.map(c => `<${rowType}>${c}</${rowType}>`).join("") + "</tr>";
            
            if (rowType === "th") {
                tableHtml += "<thead>" + rowHtml + "</thead><tbody>";
            } else {
                tableHtml += rowHtml;
            }
        } else {
            if (inTable) {
                inTable = false;
                tableHtml += "</tbody></table>";
                processedLines.push(tableHtml);
            }
            processedLines.push(lines[i]);
        }
    }
    if (inTable) {
        tableHtml += "</tbody></table>";
        processedLines.push(tableHtml);
    }
    
    let parsedText = processedLines.join("\n");
    
    // 8. Lists (Unordered & Ordered)
    parsedText = parsedText.replace(/^\s*[-*]\s+(.+)$/gm, "<li>$1</li>");
    parsedText = parsedText.replace(/(<li>.*<\/li>)/g, "<ul>$1</ul>");
    parsedText = parsedText.replace(/<\/ul>\s*<ul>/g, "");
    
    parsedText = parsedText.replace(/^\s*\d+\.\s+(.+)$/gm, "<li>$1</li>");
    parsedText = parsedText.replace(/(<li>.*<\/li>)/g, function(match) {
        if (match.includes("<ul>")) return match;
        return `<ol>${match}</ol>`;
    });
    parsedText = parsedText.replace(/<\/ol>\s*<ol>/g, "");
    
    // 9. Paragraph construction
    let blocks = parsedText.split(/\n\n+/);
    let finalHtml = blocks.map(block => {
        let trimmed = block.trim();
        if (!trimmed) return "";
        if (trimmed.startsWith("<pre>") || trimmed.startsWith("<ul>") || trimmed.startsWith("<ol>") || trimmed.startsWith("<table>") || trimmed.startsWith("<blockquote>") || trimmed.startsWith("<h1>") || trimmed.startsWith("<h2>") || trimmed.startsWith("<h3>") || trimmed.startsWith("<h4") || trimmed.startsWith("<div")) {
            return trimmed;
        }
        return `<p>${trimmed.replace(/\n/g, "<br>")}</p>`;
    }).join("\n");
    
    return finalHtml;
}

// ================= HOME DASHBOARD RENDERING =================

function updateDashboard() {
    if (!currentUser) return;
    
    // 1. Greet user based on local time
    const hour = new Date().getHours();
    let greetText = "Good morning";
    if (hour >= 12 && hour < 17) greetText = "Good afternoon";
    else if (hour >= 17) greetText = "Good evening";
    homeGreeting.textContent = `${greetText}, ${currentUser.username}`;
    
    // 2. Set stats counters
    statMemoriesCount.textContent = memoriesList.length;
    statActiveRoadmaps.textContent = activeRoadmap ? 1 : 0;
    statDecisionsCount.textContent = decisionsCount;
    sysIndexSize.textContent = `Active Vector Index (${memoriesList.length} nodes)`;
    
    // 3. Render last 3 memories
    homeRecentMemoriesList.innerHTML = "";
    if (memoriesList.length === 0) {
        homeRecentMemoriesList.innerHTML = `
            <div class="empty-state">
                <span>💾</span>
                <p>Your long-term memory store is empty.</p>
            </div>
        `;
    } else {
        const recent = memoriesList.slice(0, 3);
        recent.forEach(mem => {
            const div = document.createElement("div");
            div.className = "home-recent-item";
            const dateStr = mem.created_at.substring(0, 16).replace("T", " ");
            div.innerHTML = `
                <div class="home-recent-content">"${escapeHtml(mem.content)}"</div>
                <span class="home-recent-date">${dateStr}</span>
            `;
            homeRecentMemoriesList.appendChild(div);
        });
    }
    
    // 4. Render Active Roadmap Tasks
    homeActiveTasksList.innerHTML = "";
    if (!activeRoadmap || !activeRoadmap.tasks || activeRoadmap.tasks.length === 0) {
        activeRoadmapTitle.textContent = "No Active Plan";
        homeActiveTasksList.innerHTML = `
            <div class="empty-state">
                <span>📅</span>
                <p>No active roadmap. Go to the Planner Agent to generate and activate one!</p>
            </div>
        `;
    } else {
        activeRoadmapTitle.textContent = activeRoadmap.goal;
        activeRoadmap.tasks.forEach((task, idx) => {
            const taskDiv = document.createElement("div");
            taskDiv.className = "checklist-task-item";
            
            const checkbox = document.createElement("div");
            checkbox.className = `checklist-checkbox${task.completed ? ' checked' : ''}`;
            checkbox.innerHTML = "✓";
            checkbox.addEventListener("click", () => {
                toggleDashboardTask(idx);
            });
            
            const textSpan = document.createElement("span");
            textSpan.className = "checklist-task-text";
            textSpan.textContent = task.text;
            
            taskDiv.appendChild(checkbox);
            taskDiv.appendChild(textSpan);
            homeActiveTasksList.appendChild(taskDiv);
        });
    }
}

function toggleDashboardTask(taskIdx) {
    if (activeRoadmap && activeRoadmap.tasks[taskIdx]) {
        activeRoadmap.tasks[taskIdx].completed = !activeRoadmap.tasks[taskIdx].completed;
        localStorage.setItem("active_roadmap", JSON.stringify(activeRoadmap));
        updateDashboard();
    }
}

// ================= AUTHENTICATION & LOGIN API =================

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
            currentUser = { username: data.username, user_id: data.user_id };
            showAuthView("legacy");
            showAuthStatus("Legacy profile detected. Please set a password.", "success");
        } else {
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
    userDisplayName.textContent = currentUser.username;
    userDisplayId.textContent = `ID: ${currentUser.user_id}`;
    
    loadSessions();
    loadMemories().then(() => {
        showScreen("dashboard");
        showView("home");
    });
}

// ================= SESSION CHAT MANAGEMENT =================

async function loadSessions(selectSessionId = null) {
    if (!currentUser) return;
    try {
        const response = await fetch(`/api/sessions?user_id=${currentUser.user_id}`);
        const data = await response.json();
        
        if (data.status === "success") {
            const sessions = data.sessions || [];
            let storedSessionId = selectSessionId || localStorage.getItem("active_session_id");
            let sessionExists = sessions.some(s => s.session_id === storedSessionId);
            
            if (sessionExists) {
                activeSessionId = storedSessionId;
            } else if (sessions.length > 0) {
                activeSessionId = sessions[0].session_id;
            } else {
                await createNewSession();
                return;
            }
            
            localStorage.setItem("active_session_id", activeSessionId);
            
            sessionsListContainer.innerHTML = "";
            sessions.forEach(session => {
                const itemDiv = document.createElement("div");
                itemDiv.className = `session-item${session.session_id === activeSessionId ? ' active' : ''}`;
                itemDiv.dataset.sessionId = session.session_id;
                
                const iconSpan = document.createElement("span");
                iconSpan.className = "session-item-icon";
                iconSpan.textContent = "💬";
                itemDiv.appendChild(iconSpan);
                
                const titleSpan = document.createElement("span");
                titleSpan.className = "session-item-title";
                titleSpan.textContent = session.title || "New Conversation";
                itemDiv.appendChild(titleSpan);
                
                const actionsDiv = document.createElement("div");
                actionsDiv.className = "session-item-actions";
                
                const renameBtn = document.createElement("button");
                renameBtn.className = "btn-sidebar-add btn-session-action";
                renameBtn.title = "Rename conversation";
                renameBtn.textContent = "✏️";
                renameBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    startRenameSession(session.session_id, titleSpan);
                });
                actionsDiv.appendChild(renameBtn);
                
                const deleteBtn = document.createElement("button");
                deleteBtn.className = "btn-sidebar-add btn-session-action delete-hover";
                deleteBtn.title = "Delete conversation";
                deleteBtn.textContent = "🗑️";
                deleteBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    confirmDeleteSession(session.session_id);
                });
                actionsDiv.appendChild(deleteBtn);
                
                itemDiv.appendChild(actionsDiv);
                
                itemDiv.addEventListener("click", () => {
                    if (activeSessionId !== session.session_id) {
                        activeSessionId = session.session_id;
                        localStorage.setItem("active_session_id", activeSessionId);
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
                    body: JSON.stringify({ user_id: currentUser.user_id, title: newTitle })
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
        if (input.parentNode === parent) {
            parent.replaceChild(titleSpan, input);
        }
    }
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { finishRename(); }
        else if (e.key === "Escape") {
            finished = true;
            if (input.parentNode === parent) parent.replaceChild(titleSpan, input);
        }
    });
    input.addEventListener("blur", finishRename);
}

async function confirmDeleteSession(sessionId) {
    if (!confirm("Are you sure you want to delete this session?")) return;
    try {
        const response = await fetch(`/api/sessions/${sessionId}?user_id=${currentUser.user_id}`, { method: "DELETE" });
        const data = await response.json();
        if (response.ok && data.status === "success") {
            if (activeSessionId === sessionId) {
                activeSessionId = null;
                localStorage.removeItem("active_session_id");
            }
            loadSessions();
        }
    } catch (err) {
        console.error("Error deleting session", err);
    }
}

async function createNewSession() {
    if (!currentUser) return;
    try {
        const response = await fetch(`/api/sessions?user_id=${currentUser.user_id}`, { method: "POST" });
        const data = await response.json();
        if (response.ok && data.status === "success") {
            activeSessionId = data.session_id;
            localStorage.setItem("active_session_id", activeSessionId);
            await loadSessions(activeSessionId);
            loadChatHistory();
        }
    } catch (err) {
        console.error("Error creating session", err);
    }
}

async function loadChatHistory() {
    chatMessagesContainer.innerHTML = "";
    chatTelemetryContainer.style.display = "none";
    try {
        const response = await fetch(`/api/chat/history/${activeSessionId}?user_id=${currentUser.user_id}`);
        const data = await response.json();
        
        if (data.status === "success" && data.history && data.history.length > 0) {
            data.history.forEach(msg => {
                appendMessageToUI(msg.role, msg.content, msg.intent);
            });
        } else {
            renderChatWelcomeCard();
        }
    } catch (err) {
        console.error("Failed to load chat history", err);
        renderChatWelcomeCard();
    }
}

function renderChatWelcomeCard() {
    chatMessagesContainer.innerHTML = `
        <div class="welcome-message-card">
            <div class="card-icon">🤖</div>
            <h3>How can I assist you today?</h3>
            <p>I route your requests automatically to the correct internal agents using personal background memory constraints:</p>
            <div class="routing-explanation-grid">
                <div class="explanation-pill pill-knowledge">💾 <strong>Knowledge Agent</strong>: "Remember I have a hackathon on June 15" or "What hackathons do I have?"</div>
                <div class="explanation-pill pill-planner">📅 <strong>Planner Agent</strong>: "Generate a study guide for Rust" or "Create a plan to build an app"</div>
                <div class="explanation-pill pill-decision">⚖️ <strong>Decision Studio</strong>: "Compare PostgreSQL vs MongoDB for local storage" or "Which is better?"</div>
            </div>
        </div>
    `;
}

// ================= GENERAL CHAT INPUT SUBMISSION =================

async function sendChatMessage(messageText) {
    const welcomeCard = chatMessagesContainer.querySelector(".welcome-message-card");
    if (welcomeCard) chatMessagesContainer.innerHTML = "";
    
    appendMessageToUI("user", messageText);
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
        typingIndicator.remove();
        
        if (!response.ok) {
            throw new Error(data.detail || "Server error processing chat.");
        }
        
        appendMessageToUI("assistant", data.response, data.intent);
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
        
        // Show context routing telemetry bar
        renderTelemetry(data);
        
        if (data.intent === "KNOWLEDGE") {
            loadMemories();
        }
        
        loadSessions(activeSessionId);
    } catch (err) {
        typingIndicator.remove();
        appendMessageToUI("assistant", `⚠️ Error: ${err.message}`, "SYSTEM");
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    }
}

function renderTelemetry(chatData) {
    if (!chatData || !chatData.intent) {
        chatTelemetryContainer.style.display = "none";
        return;
    }
    
    const intent = chatData.intent.toUpperCase();
    const outputs = chatData.agent_outputs || {};
    
    chatTelemetryContainer.style.display = "flex";
    telemetryRoutingTitle.textContent = `Manager Node Route: ${intent} Agent`;
    
    let description = "Orchestrated node completed successfully. No local user context was fetched.";
    if (outputs.personalized_with_context || (outputs.memories && outputs.memories.length > 0) || (outputs.retrieved_memories && outputs.retrieved_memories.length > 0)) {
        const memories = outputs.retrieved_memories || outputs.memories || [];
        if (memories.length > 0) {
            const memorySnippets = memories.map(m => `"${m.content.substring(0, 30)}..."`).join(", ");
            description = `🧠 Memory Context retrieved to customize this response: ${memorySnippets}`;
        } else {
            description = "🧠 User background memories retrieved and injected to personalize response constraints.";
        }
    } else if (outputs.action === "remember") {
        description = `💾 Knowledge Agent saved a new memory fact to the FAISS database (ID: ${outputs.memory?.memory_id || 'new'}).`;
    }
    
    telemetryRoutingDesc.textContent = description;
}

// ================= KNOWLEDGE AGENT API ACTIONS =================

async function loadMemories() {
    if (!currentUser) return;
    try {
        const response = await fetch(`/api/memories?user_id=${currentUser.user_id}`);
        const data = await response.json();
        
        if (data.status === "success") {
            memoriesList = data.memories || [];
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
            body: JSON.stringify({ user_id: currentUser.user_id, content: content })
        });
        
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to save memory.");
        
        memoryContentInput.value = "";
        await loadMemories();
    } catch (err) {
        alert(err.message);
    }
}

async function deleteMemory(memoryId) {
    if (!confirm("Delete this memory from SQLite database and FAISS index?")) return;
    try {
        const response = await fetch(`/api/memories/${memoryId}?user_id=${currentUser.user_id}`, { method: "DELETE" });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to delete memory.");
        await loadMemories();
    } catch (err) {
        alert(err.message);
    }
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
                <p>Try saving another memory constraint or check your query.</p>
            </div>
        `;
        return;
    }
    
    filtered.forEach(mem => {
        const card = document.createElement("div");
        card.className = "memory-card";
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

// ================= PLANNER agent WORKSPACE ACTIONS =================

async function handlePlannerSubmission(e) {
    e.preventDefault();
    const goal = plannerGoalInput.value.trim();
    if (!goal) return;
    
    plannerTelemetryBox.style.display = "none";
    btnActivateRoadmap.style.display = "none";
    
    // Set loading
    plannerRoadmapOutput.innerHTML = `
        <div class="empty-state">
            <div class="typing-dots" style="font-size: 24px; margin-bottom: 12px;">
                <span></span><span></span><span></span>
            </div>
            <p>Planner Agent is fetching background memories and building personalized roadmap...</p>
        </div>
    `;
    btnGeneratePlan.disabled = true;
    
    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: currentUser.user_id,
                session_id: "planner_session_temp", // temporary isolated session
                message: `Create a detailed planning roadmap for: ${goal}`
            })
        });
        
        const data = await response.json();
        btnGeneratePlan.disabled = false;
        
        if (!response.ok) throw new Error(data.detail || "Planner failed.");
        
        // Show Telemetry in Planner Workspace
        const outputs = data.agent_outputs || {};
        if (outputs.personalized_with_context || (outputs.retrieved_memories && outputs.retrieved_memories.length > 0)) {
            plannerTelemetryBox.style.display = "block";
            const memories = outputs.retrieved_memories || [];
            if (memories.length > 0) {
                const snippets = memories.map(m => `"${m.content.substring(0, 35)}..."`).join(", ");
                plannerTelemetryBox.innerHTML = `<span>🧠 Injected context memories used to customize roadmap: ${snippets}</span>`;
            } else {
                plannerTelemetryBox.innerHTML = `<span>🧠 User background preferences injected to customize planning milestones.</span>`;
            }
        }
        
        // Render Output Markdown
        plannerRoadmapOutput.innerHTML = `
            <div class="rendered-markdown">
                ${parseMarkdown(data.response)}
            </div>
        `;
        
        // Save current generated plan to a temp global to allow Activation
        window.generatedRoadmapData = {
            goal: goal,
            markdown: data.response
        };
        
        btnActivateRoadmap.style.display = "block";
    } catch (err) {
        btnGeneratePlan.disabled = false;
        plannerRoadmapOutput.innerHTML = `
            <div class="empty-state">
                <span style="color: var(--danger)">⚠️</span>
                <p>Failed to generate plan: ${err.message}</p>
            </div>
        `;
    }
}

function activateRoadmap() {
    if (!window.generatedRoadmapData) return;
    
    const goal = window.generatedRoadmapData.goal;
    const md = window.generatedRoadmapData.markdown;
    
    // Parse list items from markdown as checklists
    const tasks = [];
    const lines = md.split("\n");
    let idCounter = 1;
    
    lines.forEach(line => {
        const trimmed = line.trim();
        // Match list items starting with - or * or digit
        const match = trimmed.match(/^[-*\d\.]+\s+(.+)$/);
        if (match) {
            const taskText = match[1].trim();
            // Avoid headers, phases, bold keys as actual checklist items
            if (taskText.length > 5 && 
                taskText.length < 120 && 
                !taskText.startsWith("#") && 
                !taskText.toLowerCase().includes("phase") && 
                !taskText.toLowerCase().includes("milestone") &&
                !taskText.startsWith("**")) {
                tasks.push({ id: idCounter++, text: taskText, completed: false });
            }
        }
    });
    
    if (tasks.length === 0) {
        // Fallback: create arbitrary placeholder steps if parsing is too strict
        tasks.push({ id: 1, text: "Review the plan draft in detail", completed: false });
        tasks.push({ id: 2, text: "Set milestones and deadlines", completed: false });
        tasks.push({ id: 3, text: "Initiate project resources", completed: false });
    }
    
    activeRoadmap = { goal: goal, tasks: tasks };
    localStorage.setItem("active_roadmap", JSON.stringify(activeRoadmap));
    
    alert(`🎉 Roadmap "${goal}" activated! Check your Home Dashboard to track task items.`);
    showView("home");
}

// ================= DECISION STUDIO actions =================

async function handleDecisionSubmission(e) {
    e.preventDefault();
    const query = decisionQueryInput.value.trim();
    if (!query) return;
    
    decisionTelemetryBox.style.display = "none";
    
    // Set loading
    decisionReportOutput.innerHTML = `
        <div class="empty-state">
            <div class="typing-dots" style="font-size: 24px; margin-bottom: 12px;">
                <span></span><span></span><span></span>
            </div>
            <p>Decision Agent is analyzing trade-offs and formatting matrix report...</p>
        </div>
    `;
    btnAnalyzeDecision.disabled = true;
    
    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: currentUser.user_id,
                session_id: "decision_session_temp",
                message: `Analyze and compare: ${query}`
            })
        });
        
        const data = await response.json();
        btnAnalyzeDecision.disabled = false;
        
        if (!response.ok) throw new Error(data.detail || "Decision analysis failed.");
        
        // Show Telemetry
        const outputs = data.agent_outputs || {};
        if (outputs.personalized_with_context || (outputs.retrieved_memories && outputs.retrieved_memories.length > 0)) {
            decisionTelemetryBox.style.display = "block";
            const memories = outputs.retrieved_memories || [];
            if (memories.length > 0) {
                const snippets = memories.map(m => `"${m.content.substring(0, 35)}..."`).join(", ");
                decisionTelemetryBox.innerHTML = `<span>🧠 Injected context memories used to customize criteria: ${snippets}</span>`;
            } else {
                decisionTelemetryBox.innerHTML = `<span>🧠 User background memories injected to customize comparison matrix weight.</span>`;
            }
        }
        
        // Render Output Markdown
        let renderedHtml = parseMarkdown(data.response);
        
        // Inject layout tags dynamically for enhanced styling (e.g. pros/cons cards & recommendation highlight box)
        renderedHtml = formatDecisionAesthetics(renderedHtml);
        
        decisionReportOutput.innerHTML = `
            <div class="decision-viewer">
                ${renderedHtml}
            </div>
        `;
        
        // Increment Decisions analyzed
        decisionsCount++;
        localStorage.setItem("decisions_count", decisionsCount);
    } catch (err) {
        btnAnalyzeDecision.disabled = false;
        decisionReportOutput.innerHTML = `
            <div class="empty-state">
                <span style="color: var(--danger)">⚠️</span>
                <p>Failed to analyze decision: ${err.message}</p>
            </div>
        `;
    }
}

// Enhance markdown tables, recommendation lists, pros/cons visually
function formatDecisionAesthetics(html) {
    let output = html;
    
    // 1. Highlight recommendations
    output = output.replace(/<h2>Recommendation<\/h2>\s*([\s\S]*?)(?=<h2>|$)/i, function(match, inner) {
        return `<div class="decision-recommendation-box">
            <h4>🧠 System Recommendation</h4>
            ${inner.trim()}
        </div>`;
    });
    
    // 2. Wrap blockquotes in summary design box
    output = output.replace(/<blockquote>([\s\S]*?)<\/blockquote>/g, function(match, inner) {
        return `<div class="decision-summary-box"><p>${inner.trim()}</p></div>`;
    });
    
    return output;
}

// ================= RENDER HELPERS =================

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

function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// ================= EVENT LISTENERS =================

// Auth View switches
linkToRegister.addEventListener("click", (e) => { e.preventDefault(); showAuthView("register"); });
linkToLogin.addEventListener("click", (e) => { e.preventDefault(); showAuthView("login"); });

// Forms Submission
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

// View Navigation Binding
navHomeBtn.addEventListener("click", () => showView("home"));
navChatBtn.addEventListener("click", () => showView("chat"));
navMemoriesBtn.addEventListener("click", () => showView("memories"));
navPlannerBtn.addEventListener("click", () => showView("planner"));
navDecisionBtn.addEventListener("click", () => showView("decision"));

// Sidebar Add Button (Trigger new session and navigate to Chat Console)
newChatBtn.addEventListener("click", () => {
    showView("chat");
    createNewSession();
});

// Chat Console form submission
chatInputForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const message = chatMessageInput.value.trim();
    if (!message) return;
    
    chatMessageInput.value = "";
    chatMessageInput.style.height = "auto";
    sendChatMessage(message);
});

chatMessageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        chatInputForm.dispatchEvent(new Event("submit"));
    }
});

chatMessageInput.addEventListener("input", function() {
    this.style.height = "auto";
    this.style.height = (this.scrollHeight - 16) + "px";
});

// Knowledge Add Memory form submission
memoryCreateForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const content = memoryContentInput.value.trim();
    if (!content) return;
    saveMemory(content);
});

memorySearchInput.addEventListener("input", (e) => {
    filterAndRenderMemories(e.target.value);
});

// Planner Agent form submission
plannerForm.addEventListener("submit", handlePlannerSubmission);
btnActivateRoadmap.addEventListener("click", activateRoadmap);

// Decision Agent form submission
decisionForm.addEventListener("submit", handleDecisionSubmission);

// Logout Profile
logoutBtn.addEventListener("click", () => {
    if (confirm("Disconnect and logout profile?")) {
        currentUser = null;
        activeSessionId = null;
        memoriesList = [];
        localStorage.removeItem("active_session_id");
        loginForm.reset();
        registerForm.reset();
        legacyForm.reset();
        showAuthView("login");
        showScreen("auth");
    }
});

// Bind globally for onclick triggers
window.deleteMemory = deleteMemory;
