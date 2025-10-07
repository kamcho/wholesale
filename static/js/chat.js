class ProductChat {
    constructor(options) {
        // Required options
        this.productId = options.productId;
        this.variationId = options.variationId;
        
        // DOM Elements - use the IDs from the template
        this.chatBtn = document.getElementById(options.chatButtonId || 'aiChatButton');
        this.chatContainer = document.getElementById(options.chatContainerId || 'aiChatContainer');
        this.chatClose = document.getElementById(options.closeButtonId || 'aiCloseButton');
        this.chatMessages = document.getElementById(options.chatMessagesId || 'aiChatMessages');
        this.chatInput = document.getElementById(options.chatInputId || 'aiChatInput');
        this.sendBtn = document.getElementById(options.sendButtonId || 'aiSendButton');
        this.typingIndicator = document.getElementById(options.typingIndicatorId || 'aiTypingIndicator');
        this.unreadBadge = document.getElementById(options.unreadBadgeId || 'aiUnreadBadge');
        
        // Chat state
        this.isOpen = false;
        this.chatHistory = [];
        
        // Initialize the chat
        this.initialize();
    }
    
    initialize() {
        // Add event listeners
        this.chatBtn?.addEventListener('click', () => this.toggleChat());
        this.chatClose?.addEventListener('click', () => this.closeChat());
        this.sendBtn?.addEventListener('click', () => this.sendMessage());
        this.chatInput?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendMessage();
            }
        });
        
        // Add welcome message
        this.addMessage('assistant', 'Hello! How can I help you with this product today?');
    }
    
    toggleChat() {
        this.isOpen = !this.isOpen;
        
        if (this.isOpen) {
            this.chatContainer.classList.remove('hidden');
            this.chatContainer.classList.add('flex');
            // Mark messages as read when opening chat
            if (this.unreadBadge) {
                this.unreadBadge.style.display = 'none';
            }
            this.chatInput.focus();
            this.scrollToBottom();
        } else {
            this.chatContainer.classList.add('hidden');
            this.chatContainer.classList.remove('flex');
        }
    }
    
    closeChat() {
        this.isOpen = false;
        this.chatContainer.classList.add('hidden');
        this.chatContainer.classList.remove('flex');
    }
    
    async sendMessage() {
        const message = this.chatInput.value.trim();
        if (!message) return;
        
        // Add user message to chat
        this.addMessage('user', message);
        this.chatInput.value = '';
        
        // Show typing indicator
        if (this.typingIndicator) {
            this.typingIndicator.classList.remove('hidden');
        }
        this.scrollToBottom();
        
        try {
            // Add to chat history
            this.chatHistory.push({ is_user: true, text: message });
            
            // Send to server
            const response = await fetch('/core/api/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken(),
                },
                body: JSON.stringify({
                    message: message,
                    product_id: this.productId,
                    variation_id: this.variationId,
                    chat_history: this.chatHistory.slice(-5), // Send last 5 messages for context
                }),
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Add bot response to chat
                this.addMessage('assistant', data.response);
                this.chatHistory.push({ is_user: false, text: data.response });
            } else {
                throw new Error(data.error || 'Failed to get response');
            }
        } catch (error) {
            console.error('Chat error:', error);
            this.addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
        } finally {
            // Hide typing indicator
            if (this.typingIndicator) {
                this.typingIndicator.classList.add('hidden');
            }
            
            // Show unread badge if chat is closed
            if (!this.isOpen && this.unreadBadge) {
                this.unreadBadge.style.display = 'flex';
            }
        }
    }
    
    addMessage(sender, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender} mb-4`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = sender === 'user' 
            ? 'bg-purple-600 text-white rounded-lg p-3 ml-auto max-w-xs' 
            : 'bg-white rounded-lg p-3 shadow-sm max-w-xs';
        contentDiv.textContent = text;
        
        messageDiv.appendChild(contentDiv);
        
        // Add to messages container
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }
    
    getCSRFToken() {
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        return cookieValue || '';
    }
}

// Export the class for use in templates
window.ProductChat = ProductChat;
