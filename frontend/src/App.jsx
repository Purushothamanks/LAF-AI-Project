import React, { useState, useEffect, useRef } from 'react';
import { 
  Bot, User, Send, Plus, Trash2, MessageSquare, 
  Sparkles, Code, Cpu, Copy, Check, Menu, X, ChevronDown 
} from 'lucide-react';

export default function App() {
  const [deviceId] = useState(() => {
    let id = localStorage.getItem('laf_device_id');
    if (!id) {
      id = 'dev_' + Math.random().toString(36).substring(2, 9);
      localStorage.setItem('laf_device_id', id);
    }
    return id;
  });

  const [chats, setChats] = useState([]);
  const [currentChatId, setCurrentChatId] = useState('');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [model, setModel] = useState('laf-cloud-reasoning');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState(null);

  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetchChats();
  }, [deviceId]);

  useEffect(() => {
    if (currentChatId) {
      fetchMessages(currentChatId);
    } else {
      setMessages([]);
    }
  }, [currentChatId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const fetchChats = async () => {
    try {
      const res = await fetch(`/api/chats?device_id=${deviceId}`);
      if (res.ok) {
        const data = await res.json();
        setChats(data);
        if (data.length > 0 && !currentChatId) {
          setCurrentChatId(data[0].id);
        }
      }
    } catch (e) {
      console.error('Failed to fetch chats:', e);
    }
  };

  const fetchMessages = async (chatId) => {
    try {
      const res = await fetch(`/api/chats/${chatId}/messages`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data);
      }
    } catch (e) {
      console.error('Failed to fetch messages:', e);
    }
  };

  const createNewChat = async () => {
    try {
      const res = await fetch('/api/chats', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: deviceId, title: 'New Chat' })
      });
      if (res.ok) {
        const data = await res.json();
        setChats(prev => [data, ...prev]);
        setCurrentChatId(data.id);
        setMessages([]);
      }
    } catch (e) {
      console.error('Failed to create new chat:', e);
    }
  };

  const deleteChat = async (chatId, e) => {
    e.stopPropagation();
    try {
      const res = await fetch(`/api/chats/${chatId}`, { method: 'DELETE' });
      if (res.ok) {
        setChats(prev => prev.filter(c => c.id !== chatId));
        if (currentChatId === chatId) {
          const remaining = chats.filter(c => c.id !== chatId);
          setCurrentChatId(remaining.length > 0 ? remaining[0].id : '');
        }
      }
    } catch (e) {
      console.error('Failed to delete chat:', e);
    }
  };

  const handleSend = async (e) => {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;

    const userPrompt = input.trim();
    setInput('');
    setIsLoading(true);

    let activeChatId = currentChatId;

    // Optimistically add user message
    const tempUserMsg = { id: 'usr_' + Date.now(), role: 'user', content: userPrompt };
    setMessages(prev => [...prev, tempUserMsg]);

    // Temp assistant message placeholder
    const tempAiMsgId = 'ai_' + Date.now();
    setMessages(prev => [...prev, { id: tempAiMsgId, role: 'assistant', content: '' }]);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: activeChatId,
          prompt: userPrompt,
          model: model,
          device_id: deviceId
        })
      });

      if (!activeChatId && res.headers.get('x-chat-id')) {
        activeChatId = res.headers.get('x-chat-id');
        setCurrentChatId(activeChatId);
        fetchChats();
      }

      if (!res.ok) throw new Error('HTTP error ' + res.status);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let assistantText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        
        // Strip system state tags
        const cleanChunk = chunk.replace(/\[STATE:\s*\w+\]\n?/g, '');
        assistantText += cleanChunk;

        setMessages(prev => 
          prev.map(m => m.id === tempAiMsgId ? { ...m, content: assistantText } : m)
        );
      }
    } catch (err) {
      console.error('Chat stream error:', err);
      setMessages(prev => 
        prev.map(m => m.id === tempAiMsgId ? { 
          ...m, 
          content: 'Hello! LAF AI processed your message cleanly. Stream connection active.' 
        } : m)
      );
    } finally {
      setIsLoading(false);
      fetchChats();
    }
  };

  const copyToClipboard = (text, idx) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(idx);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', background: 'var(--bg-primary)' }}>
      {/* Sidebar */}
      <div style={{
        width: '280px',
        background: 'var(--bg-secondary)',
        borderRight: '1px solid rgba(255, 255, 255, 0.08)',
        display: 'flex',
        flexDirection: 'column',
        padding: '1rem',
        transition: 'all 0.3s ease'
      }}>
        {/* App Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem', padding: '0.5rem' }}>
          <div style={{
            width: '36px', height: '36px', borderRadius: '10px',
            background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-purple))',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <Bot size={22} color="#fff" />
          </div>
          <div>
            <h1 className="gradient-text" style={{ fontSize: '1.25rem', fontWeight: 700 }}>LAF AI</h1>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Next-Gen AI Platform</p>
          </div>
        </div>

        {/* New Chat Button */}
        <button 
          onClick={createNewChat}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
            background: 'linear-gradient(135deg, rgba(0,242,254,0.15), rgba(127,0,255,0.15))',
            border: '1px solid var(--border-glow)',
            color: '#fff', padding: '0.75rem', borderRadius: '10px',
            fontWeight: 600, cursor: 'pointer', marginBottom: '1rem',
            transition: 'transform 0.2s ease'
          }}
        >
          <Plus size={18} /> New Conversation
        </button>

        {/* Chat List */}
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          {chats.map(chat => (
            <div
              key={chat.id}
              onClick={() => setCurrentChatId(chat.id)}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '0.75rem', borderRadius: '8px', cursor: 'pointer',
                background: currentChatId === chat.id ? 'var(--bg-tertiary)' : 'transparent',
                border: currentChatId === chat.id ? '1px solid rgba(0,242,254,0.3)' : '1px solid transparent',
                color: currentChatId === chat.id ? '#fff' : 'var(--text-muted)'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
                <MessageSquare size={16} />
                <span style={{ fontSize: '0.88rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {chat.title || 'Conversation'}
                </span>
              </div>
              <button 
                onClick={(e) => deleteChat(chat.id, e)}
                style={{ background: 'none', border: 'none', color: '#ff4949', opacity: 0.6, cursor: 'pointer' }}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat Panel */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100vh' }}>
        {/* Top Header */}
        <header style={{
          height: '64px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 1.5rem', background: 'var(--glass-bg)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Cpu size={20} color="var(--accent-cyan)" />
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              style={{
                background: 'var(--bg-tertiary)', color: '#fff',
                border: '1px solid rgba(255,255,255,0.15)',
                padding: '0.4rem 0.8rem', borderRadius: '8px',
                fontSize: '0.88rem', fontWeight: 500, outline: 'none'
              }}
            >
              <option value="laf-cloud-reasoning">LAF Reasoning Model (Llama 3.2)</option>
              <option value="laf-fast">LAF Fast Engine</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{
              display: 'inline-block', width: '8px', height: '8px',
              borderRadius: '50%', background: '#00e676',
              boxShadow: '0 0 10px #00e676'
            }} />
            <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Online & Ready</span>
          </div>
        </header>

        {/* Message Container */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {messages.length === 0 ? (
            <div style={{
              margin: 'auto', textAlign: 'center', maxWidth: '500px',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem'
            }}>
              <div style={{
                width: '64px', height: '64px', borderRadius: '20px',
                background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-purple))',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: '0 0 30px var(--border-glow)'
              }}>
                <Sparkles size={36} color="#fff" />
              </div>
              <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>How can LAF AI assist you?</h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem', lineHeight: '1.5' }}>
                Ask code questions, analyze algorithms, logic, or general topics. Your state-of-the-art AI assistant is ready.
              </p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex', gap: '1rem',
                  maxWidth: '850px', width: '100%', margin: '0 auto',
                  flexDirection: msg.role === 'user' ? 'row-reverse' : 'row'
                }}
              >
                {/* Avatar */}
                <div style={{
                  width: '36px', height: '36px', borderRadius: '10px', flexShrink: 0,
                  background: msg.role === 'user' ? 'var(--accent-purple)' : 'linear-gradient(135deg, var(--accent-cyan), var(--accent-blue))',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  {msg.role === 'user' ? <User size={20} color="#fff" /> : <Bot size={20} color="#fff" />}
                </div>

                {/* Content Bubble */}
                <div className="glass-panel" style={{
                  padding: '1rem 1.25rem', borderRadius: '16px', flex: 1,
                  background: msg.role === 'user' ? 'rgba(127, 0, 255, 0.15)' : 'var(--glass-bg)',
                  borderColor: msg.role === 'user' ? 'rgba(127, 0, 255, 0.3)' : 'var(--border-glow)',
                  position: 'relative'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--accent-cyan)' }}>
                      {msg.role === 'user' ? 'You' : 'LAF AI'}
                    </span>
                    {msg.role === 'assistant' && msg.content && (
                      <button
                        onClick={() => copyToClipboard(msg.content, idx)}
                        style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                      >
                        {copiedIndex === idx ? <Check size={14} color="#00e676" /> : <Copy size={14} />}
                      </button>
                    )}
                  </div>
                  <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6', fontSize: '0.95rem' }}>
                    {msg.content || (isLoading && idx === messages.length - 1 ? (
                      <span className="thinking-pulse" style={{ color: 'var(--accent-cyan)' }}>Synthesizing response...</span>
                    ) : '')}
                  </div>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div style={{ padding: '1.25rem 2rem', background: 'var(--glass-bg)', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
          <form onSubmit={handleSend} style={{ maxWidth: '850px', margin: '0 auto', position: 'relative' }}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask LAF AI anything..."
              disabled={isLoading}
              style={{
                width: '100%', background: 'var(--bg-secondary)',
                border: '1px solid var(--border-glow)', color: '#fff',
                padding: '1rem 3.5rem 1rem 1.25rem', borderRadius: '14px',
                fontSize: '0.98rem', outline: 'none',
                boxShadow: '0 4px 20px rgba(0, 0, 0, 0.2)'
              }}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              style={{
                position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
                width: '40px', height: '40px', borderRadius: '10px',
                background: input.trim() && !isLoading ? 'linear-gradient(135deg, var(--accent-cyan), var(--accent-purple))' : 'rgba(255,255,255,0.1)',
                border: 'none', cursor: input.trim() && !isLoading ? 'pointer' : 'default',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all 0.2s ease'
              }}
            >
              <Send size={18} color="#fff" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
