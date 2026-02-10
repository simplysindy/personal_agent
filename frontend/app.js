/**
 * Obsidian AI Personal Assistant - Frontend Application
 */

const API_BASE = 'http://localhost:8000/api';
const WS_URL = 'ws://localhost:8000/api/chat/ws';

// State
const state = {
    connected: false,
    messages: [],
    conversations: [],
    currentConversation: null,
    isTyping: false,
    stats: {
        documents: 0,
        graphNodes: 0
    }
};

// DOM Elements
const elements = {
    messagesContainer: document.getElementById('messages-container'),
    chatContainer: document.getElementById('chat-container'),
    messageInput: document.getElementById('message-input'),
    chatForm: document.getElementById('chat-form'),
    sendBtn: document.getElementById('send-btn'),
    sessionTitle: document.getElementById('session-title'),
    connectionIndicator: document.getElementById('connection-indicator'),
    vaultStatus: document.getElementById('vault-status'),
    orbStatus: document.getElementById('orb-status'),
    notesCount: document.getElementById('notes-count'),
    graphNodesCount: document.getElementById('graph-nodes-count'),
    relatedNotes: document.getElementById('related-notes'),
    conversationList: document.getElementById('conversation-list'),
    syncBtn: document.getElementById('sync-btn'),
    settingsBtn: document.getElementById('settings-btn'),
    settingsModal: document.getElementById('settings-modal'),
    closeSettingsModal: document.getElementById('close-settings-modal'),
    fullSyncBtn: document.getElementById('full-sync-btn'),
    graphBtn: document.getElementById('graph-btn'),
    graphModal: document.getElementById('graph-modal'),
    closeGraphModal: document.getElementById('close-graph-modal'),
    graphContainer: document.getElementById('graph-container'),
    indexPercent: document.getElementById('index-percent'),
    indexBar: document.getElementById('index-bar'),
    indexStatus: document.getElementById('index-status'),
    docCount: document.getElementById('doc-count'),
    apiStatusIndicator: document.getElementById('api-status-indicator'),
    apiStatusText: document.getElementById('api-status-text'),
    newChatBtn: document.getElementById('new-chat-btn'),
    clearHistoryBtn: document.getElementById('clear-history-btn'),
    graphPreview: document.getElementById('graph-preview'),
    refreshIntelBtn: document.getElementById('refresh-intel-btn')
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    // Check API health
    await checkApiHealth();

    // Load stats
    await loadStats();

    // Setup event listeners
    setupEventListeners();

    // Add welcome message
    addSystemMessage("Vault connection established. All neural pathways active. Ready for your command, Commander.");

    // Load conversations from localStorage
    loadConversations();
}

// API Health Check
async function checkApiHealth() {
    try {
        const response = await fetch(`${API_BASE.replace('/api', '')}/health`);
        const data = await response.json();

        if (data.status === 'healthy') {
            setConnected(true);
            elements.apiStatusIndicator.className = 'w-2 h-2 rounded-full bg-green-500';
            elements.apiStatusText.textContent = 'Connected to backend';
        } else {
            setConnected(false);
        }
    } catch (error) {
        console.error('API health check failed:', error);
        setConnected(false);
        elements.apiStatusIndicator.className = 'w-2 h-2 rounded-full bg-red-500';
        elements.apiStatusText.textContent = 'Backend offline';
    }
}

function setConnected(connected) {
    state.connected = connected;
    if (connected) {
        elements.connectionIndicator.className = 'w-2 h-2 rounded-full bg-green-500 shadow-[0_0_10px_#22c55e]';
        elements.vaultStatus.textContent = 'Active';
        elements.orbStatus.textContent = 'VAULT SYNCHRONIZED';
    } else {
        elements.connectionIndicator.className = 'w-2 h-2 rounded-full bg-red-500 shadow-[0_0_10px_#ef4444]';
        elements.vaultStatus.textContent = 'Disconnected';
        elements.orbStatus.textContent = 'CONNECTION LOST';
    }
}

// Load Stats
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/knowledge/stats`);
        const data = await response.json();

        const graphStats = data.graph || {};
        const vectorStats = data.vector || {};

        const docCount = graphStats.Document || 0;
        const conceptCount = graphStats.Concept || 0;
        const personCount = graphStats.Person || 0;
        const projectCount = graphStats.Project || 0;

        const totalNodes = docCount + conceptCount + personCount + projectCount;

        state.stats.documents = docCount;
        state.stats.graphNodes = totalNodes;

        elements.notesCount.textContent = docCount.toLocaleString();
        elements.graphNodesCount.textContent = totalNodes.toLocaleString();
        elements.docCount.textContent = docCount.toLocaleString();

        // Set index bar
        if (docCount > 0) {
            elements.indexPercent.textContent = '100%';
            elements.indexBar.style.width = '100%';
            elements.indexStatus.textContent = 'Indexed';
        } else {
            elements.indexPercent.textContent = '0%';
            elements.indexBar.style.width = '0%';
            elements.indexStatus.textContent = 'No documents';
        }
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

// Event Listeners
function setupEventListeners() {
    // Chat form submit
    elements.chatForm.addEventListener('submit', handleSubmit);

    // Quick actions
    document.querySelectorAll('.quick-action').forEach(btn => {
        btn.addEventListener('click', () => {
            const action = btn.dataset.action;
            elements.messageInput.value = action;
            handleSubmit(new Event('submit'));
        });
    });

    // Settings modal
    elements.settingsBtn.addEventListener('click', () => {
        elements.settingsModal.classList.remove('hidden');
    });
    elements.closeSettingsModal.addEventListener('click', () => {
        elements.settingsModal.classList.add('hidden');
    });

    // Graph modal
    elements.graphBtn.addEventListener('click', openGraphModal);
    elements.graphPreview.addEventListener('click', openGraphModal);
    elements.closeGraphModal.addEventListener('click', () => {
        elements.graphModal.classList.add('hidden');
    });

    // Full sync
    elements.fullSyncBtn.addEventListener('click', startFullSync);

    // Sync button
    elements.syncBtn.addEventListener('click', startFullSync);

    // New chat
    elements.newChatBtn.addEventListener('click', startNewChat);

    // Clear history
    elements.clearHistoryBtn.addEventListener('click', clearAllHistory);

    // Refresh intel
    elements.refreshIntelBtn.addEventListener('click', loadStats);

    // Close modals on backdrop click
    elements.settingsModal.addEventListener('click', (e) => {
        if (e.target === elements.settingsModal) {
            elements.settingsModal.classList.add('hidden');
        }
    });
    elements.graphModal.addEventListener('click', (e) => {
        if (e.target === elements.graphModal) {
            elements.graphModal.classList.add('hidden');
        }
    });

    // Keyboard shortcut for sending
    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(new Event('submit'));
        }
    });
}

// Handle message submit
async function handleSubmit(e) {
    e.preventDefault();

    const message = elements.messageInput.value.trim();
    if (!message || state.isTyping) return;

    // Add user message
    addUserMessage(message);
    elements.messageInput.value = '';

    // Show typing indicator
    state.isTyping = true;
    elements.sendBtn.disabled = true;
    const typingId = addTypingIndicator();

    try {
        // Build conversation history (exclude system messages, limit to recent)
        const history = state.messages
            .filter(m => m.role === 'user' || m.role === 'agent')
            .map(m => ({ role: m.role, content: m.content }))
            .slice(-20);  // Last 20 messages (~10 exchanges)

        // Send to API with history
        const response = await fetch(`${API_BASE}/chat/message`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message,
                history,
                conversation_id: state.currentConversation
            })
        });

        const data = await response.json();

        // Remove typing indicator
        removeTypingIndicator(typingId);

        // Add agent response
        addAgentMessage(data.response, data.sources || [], data.intent);

        // Update related notes
        updateRelatedNotes(data.sources || []);

        // Save conversation
        saveConversation();

    } catch (error) {
        console.error('Chat error:', error);
        removeTypingIndicator(typingId);
        addSystemMessage("Connection error. Please ensure the backend is running.", true);
    } finally {
        state.isTyping = false;
        elements.sendBtn.disabled = false;
    }
}

// Message rendering
function addSystemMessage(text, isError = false) {
    const html = `
        <div class="flex gap-6 md:gap-8 mb-8 relative group message-enter">
            <div class="relative z-10 flex flex-col items-center shrink-0">
                <div class="w-10 h-10 md:w-12 md:h-12 rounded-full bg-black border ${isError ? 'border-red-500/40' : 'border-glow-purple/40'} flex items-center justify-center">
                    <span class="material-symbols-outlined ${isError ? 'text-red-500' : 'text-glow-purple'} text-sm md:text-base">settings_input_component</span>
                </div>
            </div>
            <div class="flex flex-col pt-1 w-full">
                <div class="flex items-center justify-between mb-1">
                    <span class="text-xs font-mono ${isError ? 'text-red-500/60' : 'text-glow-purple/60'}">SYSTEM MESSAGE • ${getCurrentTime()}</span>
                </div>
                <div class="p-4 rounded-lg rounded-tl-none bg-white/5 border ${isError ? 'border-red-500/30' : 'border-white/10'} backdrop-blur-md text-gray-400 text-sm md:text-base border-dashed">
                    ${escapeHtml(text)}
                </div>
            </div>
        </div>
    `;
    appendMessage(html);
    state.messages.push({ role: 'system', content: text });
}

function addUserMessage(text) {
    const html = `
        <div class="flex gap-6 md:gap-8 mb-8 relative group message-enter">
            <div class="relative z-10 flex flex-col items-center shrink-0">
                <div class="w-10 h-10 md:w-12 md:h-12 rounded-full bg-[#2d1b38] border border-primary flex items-center justify-center shadow-neon-sm">
                    <span class="material-symbols-outlined text-white text-sm md:text-base">person</span>
                </div>
            </div>
            <div class="flex flex-col pt-1 w-full">
                <div class="flex items-center justify-between mb-1">
                    <span class="text-xs font-mono text-primary">COMMANDER • ${getCurrentTime()}</span>
                </div>
                <div class="p-4 rounded-lg rounded-tl-none bg-primary/10 border border-primary/30 backdrop-blur-md text-white shadow-[0_0_20px_rgba(127,19,236,0.05)] text-sm md:text-base">
                    ${escapeHtml(text)}
                </div>
            </div>
        </div>
    `;
    appendMessage(html);
    state.messages.push({ role: 'user', content: text });
}

function addAgentMessage(text, sources = [], intent = 'general') {
    // Parse markdown-like formatting
    const formattedText = formatAgentResponse(text);

    // Build sources section if available
    let sourcesHtml = '';
    if (sources.length > 0) {
        sourcesHtml = `
            <div class="mt-4 p-3 rounded-lg border border-white/5 bg-black/40">
                <div class="flex items-center gap-2 text-green-400 mb-2">
                    <span class="material-symbols-outlined text-sm">source</span>
                    <h4 class="text-xs font-bold uppercase tracking-wider">Sources</h4>
                </div>
                <ul class="text-xs text-gray-400 space-y-1">
                    ${sources.map(s => `<li class="truncate">• ${escapeHtml(s)}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    const html = `
        <div class="flex gap-6 md:gap-8 mb-8 relative group message-enter">
            <div class="relative z-10 flex flex-col items-center shrink-0">
                <div class="w-10 h-10 md:w-12 md:h-12 rounded-full bg-black border border-glow-purple flex items-center justify-center shadow-neon">
                    <span class="material-symbols-outlined text-glow-purple text-sm md:text-base">smart_toy</span>
                </div>
            </div>
            <div class="flex flex-col pt-1 w-full">
                <div class="flex items-center justify-between mb-1">
                    <span class="text-xs font-mono text-glow-purple">OBSIDIAN AGENT • ${getCurrentTime()}</span>
                    <span class="text-[10px] font-mono text-gray-600 uppercase">${intent}</span>
                </div>
                <div class="p-5 rounded-lg rounded-tl-none glass-panel text-gray-100 flex flex-col gap-3">
                    <div class="text-sm md:text-base leading-relaxed prose prose-invert prose-sm max-w-none">
                        ${formattedText}
                    </div>
                    ${sourcesHtml}
                </div>
            </div>
        </div>
    `;
    appendMessage(html);
    state.messages.push({ role: 'agent', content: text, sources, intent });
}

function addTypingIndicator() {
    const id = 'typing-' + Date.now();
    const html = `
        <div id="${id}" class="flex gap-6 md:gap-8 mb-8 relative group message-enter">
            <div class="relative z-10 flex flex-col items-center shrink-0">
                <div class="w-10 h-10 md:w-12 md:h-12 rounded-full bg-[#1a1122] border border-white/10 flex items-center justify-center">
                    <span class="material-symbols-outlined text-glow-purple text-sm animate-pulse">smart_toy</span>
                </div>
            </div>
            <div class="flex flex-col pt-1 w-full">
                <div class="p-4 rounded-lg rounded-tl-none bg-white/5 border border-white/5 text-gray-500 text-sm flex items-center gap-2">
                    <span class="typing-indicator flex gap-1">
                        <span class="w-2 h-2 bg-glow-purple rounded-full"></span>
                        <span class="w-2 h-2 bg-glow-purple rounded-full"></span>
                        <span class="w-2 h-2 bg-glow-purple rounded-full"></span>
                    </span>
                    <span class="text-xs font-mono">Agent is thinking...</span>
                </div>
            </div>
        </div>
    `;
    appendMessage(html);
    return id;
}

function removeTypingIndicator(id) {
    const element = document.getElementById(id);
    if (element) {
        element.remove();
    }
}

function appendMessage(html) {
    elements.messagesContainer.insertAdjacentHTML('beforeend', html);
    scrollToBottom();
}

function scrollToBottom() {
    setTimeout(() => {
        elements.chatContainer.scrollTop = elements.chatContainer.scrollHeight;
    }, 100);
}

// Format agent response (basic markdown)
function formatAgentResponse(text) {
    // Escape HTML first
    let formatted = escapeHtml(text);

    // Bold
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Italic
    formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Code blocks
    formatted = formatted.replace(/```([\s\S]*?)```/g, '<pre class="bg-black/40 p-2 rounded mt-2 mb-2 overflow-x-auto"><code>$1</code></pre>');

    // Inline code
    formatted = formatted.replace(/`(.*?)`/g, '<code class="bg-black/40 px-1 rounded">$1</code>');

    // Line breaks
    formatted = formatted.replace(/\n/g, '<br>');

    // Lists
    formatted = formatted.replace(/^- (.*?)(<br>|$)/gm, '<li class="ml-4">$1</li>');

    return formatted;
}

// Related notes
function updateRelatedNotes(sources) {
    if (sources.length === 0) {
        elements.relatedNotes.innerHTML = '<div class="text-gray-500 text-xs italic p-2">No related notes found</div>';
        return;
    }

    const html = sources.slice(0, 5).map(source => `
        <div class="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 transition-colors cursor-pointer group border border-transparent hover:border-white/5">
            <span class="material-symbols-outlined text-gray-400 group-hover:text-primary">description</span>
            <div class="flex flex-col overflow-hidden">
                <span class="text-sm text-gray-300 truncate">${escapeHtml(source)}</span>
                <span class="text-[10px] text-gray-600">From search results</span>
            </div>
        </div>
    `).join('');

    elements.relatedNotes.innerHTML = html;
}

// Conversation management
function loadConversations() {
    const saved = localStorage.getItem('obsidian-ai-conversations');
    if (saved) {
        state.conversations = JSON.parse(saved);
        renderConversationList();
    }
}

function saveConversation() {
    if (state.messages.length < 2) return;

    const title = state.messages.find(m => m.role === 'user')?.content.slice(0, 30) || 'New Chat';

    if (state.currentConversation) {
        // Update existing
        const conv = state.conversations.find(c => c.id === state.currentConversation);
        if (conv) {
            conv.messages = state.messages;
            conv.updatedAt = Date.now();
        }
    } else {
        // Create new
        const conv = {
            id: Date.now().toString(),
            title: title + (title.length >= 30 ? '...' : ''),
            messages: state.messages,
            createdAt: Date.now(),
            updatedAt: Date.now()
        };
        state.conversations.unshift(conv);
        state.currentConversation = conv.id;
    }

    // Keep only last 20 conversations
    state.conversations = state.conversations.slice(0, 20);

    localStorage.setItem('obsidian-ai-conversations', JSON.stringify(state.conversations));
    renderConversationList();
}

function renderConversationList() {
    const html = state.conversations.map(conv => {
        const isActive = conv.id === state.currentConversation;
        return `
            <a class="conversation-item group flex items-center gap-3 px-3 py-3 rounded-xl ${isActive ? 'bg-primary/20 border border-primary/30 shadow-[0_0_15px_rgba(127,19,236,0.15)]' : 'hover:bg-white/5 border border-transparent'} transition-all cursor-pointer" data-id="${conv.id}">
                <span class="material-symbols-outlined ${isActive ? 'text-glow-purple' : 'text-gray-400'} group-hover:text-glow-purple transition-colors">chat_bubble</span>
                <span class="hidden md:block ${isActive ? 'text-white' : 'text-gray-400'} font-medium text-sm tracking-wide truncate">${escapeHtml(conv.title)}</span>
            </a>
        `;
    }).join('');

    elements.conversationList.innerHTML = html;

    // Add click handlers
    document.querySelectorAll('.conversation-item').forEach(item => {
        item.addEventListener('click', () => {
            loadConversation(item.dataset.id);
        });
    });
}

function loadConversation(id) {
    const conv = state.conversations.find(c => c.id === id);
    if (!conv) return;

    state.currentConversation = id;
    state.messages = [];
    elements.messagesContainer.innerHTML = '';

    // Re-render messages
    conv.messages.forEach(msg => {
        if (msg.role === 'system') {
            addSystemMessage(msg.content);
        } else if (msg.role === 'user') {
            addUserMessage(msg.content);
        } else if (msg.role === 'agent') {
            addAgentMessage(msg.content, msg.sources || [], msg.intent || 'general');
        }
    });

    elements.sessionTitle.textContent = `SESSION: ${conv.title.toUpperCase()}`;
    renderConversationList();
}

function startNewChat() {
    state.currentConversation = null;
    state.messages = [];
    elements.messagesContainer.innerHTML = '';
    elements.sessionTitle.textContent = 'SESSION: NEW CHAT';
    addSystemMessage("New session initialized. Ready for your command, Commander.");
    renderConversationList();
}

function clearAllHistory() {
    if (!confirm('Clear all conversation history? This cannot be undone.')) return;
    state.conversations = [];
    state.currentConversation = null;
    state.messages = [];
    elements.messagesContainer.innerHTML = '';
    elements.sessionTitle.textContent = 'SESSION: NEW CHAT';
    localStorage.removeItem('obsidian-ai-conversations');
    renderConversationList();
    addSystemMessage("All conversation history cleared. Ready for your command, Commander.");
}

// Full sync
async function startFullSync() {
    try {
        elements.fullSyncBtn.disabled = true;
        elements.fullSyncBtn.textContent = 'Syncing...';
        elements.indexStatus.textContent = 'Syncing...';
        elements.indexBar.style.width = '0%';

        const response = await fetch(`${API_BASE}/sync/full`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.status === 'started') {
            addSystemMessage("Full vault sync started. This may take a few minutes...");
            pollSyncStatus();
        } else {
            addSystemMessage(`Sync status: ${data.message}`);
        }
    } catch (error) {
        console.error('Sync error:', error);
        addSystemMessage("Failed to start sync. Please check the backend.", true);
    } finally {
        elements.fullSyncBtn.disabled = false;
        elements.fullSyncBtn.textContent = 'Start Full Sync';
    }
}

async function pollSyncStatus() {
    try {
        const response = await fetch(`${API_BASE}/sync/status`);
        const data = await response.json();

        if (data.running) {
            const percent = data.total > 0 ? Math.round((data.progress / data.total) * 100) : 0;
            elements.indexPercent.textContent = `${percent}%`;
            elements.indexBar.style.width = `${percent}%`;
            elements.indexStatus.textContent = `Processing ${data.progress}/${data.total}`;

            // Continue polling
            setTimeout(pollSyncStatus, 2000);
        } else {
            elements.indexPercent.textContent = '100%';
            elements.indexBar.style.width = '100%';
            elements.indexStatus.textContent = 'Complete';
            addSystemMessage("Vault sync complete! Knowledge graph updated.");
            loadStats();
        }
    } catch (error) {
        console.error('Poll error:', error);
    }
}

// Graph modal
async function openGraphModal() {
    elements.graphModal.classList.remove('hidden');

    // Load graph data
    try {
        const response = await fetch(`${API_BASE}/graph/visualization?limit=100`);
        const data = await response.json();

        renderGraph(data);
    } catch (error) {
        console.error('Graph load error:', error);
        elements.graphContainer.innerHTML = '<div class="flex items-center justify-center h-full text-gray-500">Failed to load graph data</div>';
    }
}

function renderGraph(data) {
    // Simple SVG-based graph visualization
    const width = elements.graphContainer.clientWidth;
    const height = elements.graphContainer.clientHeight || 500;

    if (!data.nodes || data.nodes.length === 0) {
        elements.graphContainer.innerHTML = '<div class="flex items-center justify-center h-full text-gray-500">No graph data available. Run a vault sync first.</div>';
        return;
    }

    // Position nodes in a force-directed-like layout (simplified)
    const nodes = data.nodes.map((node, i) => {
        const angle = (i / data.nodes.length) * 2 * Math.PI;
        const radius = Math.min(width, height) * 0.35;
        return {
            ...node,
            x: width / 2 + Math.cos(angle) * radius * (0.5 + Math.random() * 0.5),
            y: height / 2 + Math.sin(angle) * radius * (0.5 + Math.random() * 0.5)
        };
    });

    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    // Build SVG
    let svg = `<svg width="${width}" height="${height}" class="w-full h-full">`;

    // Draw edges
    data.edges.forEach(edge => {
        const source = nodeMap.get(edge.source);
        const target = nodeMap.get(edge.target);
        if (source && target) {
            svg += `<line x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}" stroke="rgba(127, 19, 236, 0.3)" stroke-width="1"/>`;
        }
    });

    // Draw nodes
    const colors = {
        Document: '#8162a0',
        Concept: '#22c55e',
        Person: '#3b82f6',
        Project: '#f59e0b',
        Resource: '#ec4899',
        Image: '#6366f1'
    };

    nodes.forEach(node => {
        const color = colors[node.label] || '#8162a0';
        const radius = node.label === 'Project' ? 12 : 8;

        svg += `
            <g class="cursor-pointer" data-id="${node.id}">
                <circle cx="${node.x}" cy="${node.y}" r="${radius}" fill="${color}" opacity="0.8">
                    <title>${node.name} (${node.label})</title>
                </circle>
                <text x="${node.x}" y="${node.y + radius + 12}" text-anchor="middle" fill="#9ca3af" font-size="10" class="pointer-events-none">${truncate(node.name, 15)}</text>
            </g>
        `;
    });

    // Legend
    svg += `
        <g transform="translate(20, 20)">
            ${Object.entries(colors).map(([label, color], i) => `
                <g transform="translate(0, ${i * 20})">
                    <circle cx="6" cy="6" r="6" fill="${color}"/>
                    <text x="18" y="10" fill="#9ca3af" font-size="11">${label}</text>
                </g>
            `).join('')}
        </g>
    `;

    svg += '</svg>';

    elements.graphContainer.innerHTML = svg;
}

// Utilities
function getCurrentTime() {
    return new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function truncate(str, len) {
    return str.length > len ? str.slice(0, len) + '...' : str;
}
