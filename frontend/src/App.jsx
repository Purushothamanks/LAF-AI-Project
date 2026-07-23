import React, { useState, useEffect, useRef } from 'react';
import * as XLSX from 'xlsx';
import { 
  Plus, 
  Trash2, 
  Send, 
  MessageSquare, 
  Sparkles, 
  Code, 
  Play, 
  Wrench, 
  Copy, 
  Check, 
  Edit3, 
  X, 
  AlertCircle,
  Database,
  Cpu,
  Search,
  Settings,
  Paperclip,
  Mic,
  MicOff,
  Volume2,
  Download,
  Terminal,
  FileText,
  Share2,
  Menu,
  Bell,
  Smartphone,
  User
} from 'lucide-react';

const API_BASE = ''; // Proxy-handled
const APP_VERSION = '1.2.7'; // Current app version for update notifications

const CODE_TEMPLATES = {
  python: `print("Hello, World!")`,
  javascript: `console.log("Hello, World!");`,
  cpp: `#include <iostream>\nusing namespace std;\n\nint main() {\n    cout << "Hello, World!" << endl;\n    return 0;\n}`,
  c: `#include <stdio.h>\n\nint main() {\n    printf("Hello, World!\\n");\n    return 0;\n}`,
  java: `public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, World!");\n    }\n}`
};

export default function App() {
  const [chats, setChats] = useState([]);
  const [currentChatId, setCurrentChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [model, setModel] = useState('laf-cloud-reasoning');
  const [deviceId] = useState(() => {
    let id = localStorage.getItem('laf_device_id');
    if (!id) {
      id = 'usr_' + Math.random().toString(36).substring(2, 9) + '_' + Date.now().toString(36);
      localStorage.setItem('laf_device_id', id);
    }
    return id;
  });
  const [sidebarOpen, setSidebarOpen] = useState(false); // Mobile sidebar state
  const [updateAvailable, setUpdateAvailable] = useState(false); // Update notification state
  const [deferredPrompt, setDeferredPrompt] = useState(null); // PWA install prompt

  // Code_It states
  const [codeItOpen, setCodeItOpen] = useState(false);
  const [codeItLang, setCodeItLang] = useState('python');
  const [codeItCode, setCodeItCode] = useState(CODE_TEMPLATES.python);
  const [codeItStdin, setCodeItStdin] = useState('');
  const [codeItConsoleOutput, setCodeItConsoleOutput] = useState('');
  const [codeItConsoleError, setCodeItConsoleError] = useState('');
  const [codeItIsRunning, setCodeItIsRunning] = useState(false);
  
  // Search and filter sidebar
  const [searchQuery, setSearchQuery] = useState('');
  
  // Custom states
  const [currentState, setCurrentState] = useState(''); // Tracking state tags during streams
  
  // Attachment state
  const [attachments, setAttachments] = useState([]); // Array of { name, type, size, content }
  const fileInputRef = useRef(null);
  
  // User configuration and helper for initials
  const [userName, setUserName] = useState(() => localStorage.getItem('laf_username') || '');
  const [usernameInput, setUsernameInput] = useState('');
  const [usernameModalOpen, setUsernameModalOpen] = useState(false);

  useEffect(() => {
    if (!userName) {
      setUsernameModalOpen(true);
    }
  }, [userName]);

  const handleSaveUsername = () => {
    if (usernameInput.trim()) {
      localStorage.setItem('laf_username', usernameInput.trim());
      setUserName(usernameInput.trim());
      setUsernameModalOpen(false);
    }
  };

  const getUserInitials = (name) => {
    if (!name) return 'U';
    const parts = name.trim().split(/\s+/);
    if (parts.length > 1) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return (name[0] + (name[1] || '')).toUpperCase();
  };

  // Speech states
  const [isDictating, setIsDictating] = useState(false);
  const recognitionRef = useRef(null);
  
  // Modal states
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);
  const [statsModalOpen, setStatsModalOpen] = useState(false);
  const [docModalOpen, setDocModalOpen] = useState(false);
  const [docType, setDocType] = useState(''); // 'privacy' | 'terms'
  const [customSystemPrompt, setCustomSystemPrompt] = useState('You are an emotionally expressive, highly empathetic AI assistant named LAF.');
  
  // Inline edit state
  const [editingMessageId, setEditingMessageId] = useState(null);
  const [editText, setEditText] = useState('');
  
  // Sandbox outputs state
  const [sandboxOutputs, setSandboxOutputs] = useState({});
  
  // Code fixer modal state
  const [fixModalOpen, setFixModalOpen] = useState(false);
  const [fixData, setFixData] = useState({ language: '', originalCode: '', explanation: '', correctedCode: '', errorText: '' });
  
  // Copy clipboard state
  const [copiedText, setCopiedText] = useState(null);

  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetchChats();
    setupSpeechRecognition();
    // Check for updates on load
    checkForUpdates();
    // Set up PWA install prompt listener
    const handleBeforeInstallPrompt = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    };
  }, []);
  
  const checkForUpdates = () => {
    // Simulate checking for updates - in production you'd compare versions from server
    const lastVersion = localStorage.getItem('lastKnownVersion');
    if (lastVersion && lastVersion !== APP_VERSION) {
      setUpdateAvailable(true);
    } else {
      localStorage.setItem('lastKnownVersion', APP_VERSION);
    }
  };
  
  const handleInstallPWA = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') {
      setDeferredPrompt(null);
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchChats = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/chats?device_id=${deviceId}`);
      if (res.ok) {
        const data = await res.json();
        setChats(data);
      }
    } catch (err) {
      console.error('Failed to fetch chats:', err);
    }
  };

  const selectChat = async (chatId) => {
    setCurrentChatId(chatId);
    setMessages([]);
    setCurrentState('');
    try {
      const res = await fetch(`${API_BASE}/api/chats/${chatId}/messages`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data);
      }
    } catch (err) {
      console.error('Failed to fetch messages:', err);
    }
  };

  const handleNewChat = () => {
    setCurrentChatId(null);
    setMessages([]);
    setCurrentState('');
    setAttachments([]);
  };

  const handleDeleteChat = async (e, chatId) => {
    e.stopPropagation();
    if (!window.confirm('Delete this conversation history?')) return;
    
    try {
      const res = await fetch(`${API_BASE}/api/chats/${chatId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        if (currentChatId === chatId) {
          handleNewChat();
        }
        fetchChats();
      }
    } catch (err) {
      console.error('Failed to delete chat:', err);
    }
  };

  const handleEditMessage = async (messageId, newContent) => {
    try {
      const res = await fetch(`${API_BASE}/api/messages/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: messageId, new_content: newContent })
      });
      if (res.ok) {
        setEditingMessageId(null);
        if (currentChatId) selectChat(currentChatId);
      }
    } catch (err) {
      console.error('Failed to edit message:', err);
    }
  };

  const handleTruncateChat = async (timestamp) => {
    if (!currentChatId) return;
    if (!window.confirm('Delete all messages recorded after this timestamp?')) return;
    
    try {
      const res = await fetch(`${API_BASE}/api/chats/truncate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: currentChatId, timestamp })
      });
      if (res.ok) {
        selectChat(currentChatId);
      }
    } catch (err) {
      console.error('Failed to truncate chat:', err);
    }
  };

  // Web Speech API dictation setup
  const setupSpeechRecognition = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const rec = new SpeechRecognition();
      rec.continuous = false;
      rec.interimResults = false;
      rec.lang = 'en-US';
      
      rec.onstart = () => setIsDictating(true);
      rec.onend = () => setIsDictating(false);
      rec.onerror = () => setIsDictating(false);
      
      rec.onresult = (e) => {
        const text = e.results[0][0].transcript;
        setInputText(prev => prev + (prev ? ' ' : '') + text);
      };
      
      recognitionRef.current = rec;
    }
  };

  const toggleDictation = () => {
    if (!recognitionRef.current) {
      alert('Speech recognition is not supported in this browser.');
      return;
    }
    if (isDictating) {
      recognitionRef.current.stop();
    } else {
      recognitionRef.current.start();
    }
  };

  // Code_It execution and review handlers
  const runCodeIt = async () => {
    setCodeItIsRunning(true);
    setCodeItConsoleOutput('Running code in secure sandbox...');
    setCodeItConsoleError('');

    try {
      const res = await fetch(`${API_BASE}/api/execute_code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          language: codeItLang,
          code: codeItCode,
          stdin: codeItStdin
        })
      });

      if (res.ok) {
        const data = await res.json();
        setCodeItConsoleOutput(data.output || '');
        setCodeItConsoleError(data.error || '');
      } else {
        setCodeItConsoleError('Failed to execute code. Sandbox returned an error.');
      }
    } catch (err) {
      setCodeItConsoleError('Failed to reach compile sandbox. Please check connection.');
    } finally {
      setCodeItIsRunning(false);
    }
  };

  const handleLanguageChange = (lang) => {
    setCodeItLang(lang);
    setCodeItCode(CODE_TEMPLATES[lang] || '');
  };

  const askLafToReviewCode = () => {
    if (!codeItCode.trim()) return;
    const promptText = `\`\`\`${codeItLang}\n${codeItCode}\n\`\`\``;
    handleSendMessage(promptText);
  };

  // Text to speech aloud reader
  const speakMessage = (text) => {
    // Strip HTML/Markdown tags for clean voice output
    const cleanText = text
      .replace(/<[^>]*>/g, '')
      .replace(/```[\s\S]*?```/g, '[Code Block omitted]')
      .replace(/\*\*([^*]+)\*\*/g, '$1')
      .replace(/\*([^*]+)\*/g, '$1');

    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel(); // stop past speeches
      const utterance = new SpeechSynthesisUtterance(cleanText);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      // Try to get a preferred voice
      const voices = window.speechSynthesis.getVoices();
      if (voices.length > 0) {
        utterance.voice = voices.find(voice => voice.lang === 'en-US' && voice.name.includes('Google')) || voices[0];
      }
      window.speechSynthesis.speak(utterance);
    } else {
      alert('Text to speech is not supported in this browser.');
    }
  };

  // Attachment handling including Excel parser
  const handleAttachmentUpload = (e) => {
    const filesList = Array.from(e.target.files);
    filesList.forEach(file => {
      const reader = new FileReader();
      const ext = file.name.split('.').pop().toLowerCase();
      
      if (['xlsx', 'xls'].includes(ext)) {
        reader.onload = (event) => {
          try {
            const data = new Uint8Array(event.target.result);
            const workbook = XLSX.read(data, { type: 'array' });
            let csvContent = "";
            workbook.SheetNames.forEach(sheetName => {
              const worksheet = workbook.Sheets[sheetName];
              const csv = XLSX.utils.sheet_to_csv(worksheet);
              csvContent += `Sheet: ${sheetName}\n${csv}\n\n`;
            });
            
            setAttachments(prev => [
              ...prev,
              {
                name: file.name,
                type: 'text/csv',
                size: file.size,
                content: csvContent
              }
            ]);
          } catch (err) {
            alert(`Error parsing Excel file: ${err.message}`);
          }
        };
        reader.readAsArrayBuffer(file);
      } else {
        // Read text/code files as plain text
        reader.onload = (event) => {
          setAttachments(prev => [
            ...prev,
            {
              name: file.name,
              type: file.type || 'text/plain',
              size: file.size,
              content: event.target.result
            }
          ]);
        };
        if (file.type.startsWith('image/')) {
          reader.readAsDataURL(file);
        } else {
          reader.readAsText(file);
        }
      }
    });
    
    // Reset file input
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeAttachment = (index) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  // Submit Prompt logic
  const handleSendMessage = async (textToSend) => {
    let rawPrompt = textToSend || inputText;
    if (!rawPrompt.trim() && attachments.length === 0 && !isLoading) return;

    if (!rawPrompt.trim() && attachments.length > 0) {
      rawPrompt = "Please analyze this attached file in detail and explain its contents, summary, and structure.";
    }

    setInputText('');
    setIsLoading(true);
    setCurrentState('Synthesizing prompt...');

    // package attachments into prompt
    let processedPrompt = '';
    attachments.forEach(att => {
      processedPrompt += `[Attached File: ${att.name} (${att.type}, ${att.size} bytes)]\nContent Preview/Data:\n${att.content}\n[End of File: ${att.name}]\n\n`;
    });
    processedPrompt += rawPrompt;
    
    // Clear local visual attachments list
    setAttachments([]);

    // Optimistically add user message
    const tempUserMsgId = 'temp-user-' + Date.now();
    const newUserMsg = {
      id: tempUserMsgId,
      role: 'user',
      content: rawPrompt,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, newUserMsg]);

    let activeChatId = currentChatId;

    // Temporary placeholder for assistant streaming message
    const tempAiMsgId = 'temp-ai-' + Date.now();
    let assistantContent = '';
    
    setMessages(prev => [...prev, {
      id: tempAiMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString()
    }]);

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          chat_id: activeChatId || '',
          prompt: processedPrompt,
          model: model,
          device_id: deviceId,
          user_name: userName || ''
        })
      });

      if (!response.ok) {
        throw new Error('Failed to run chat stream');
      }

      const respChatId = response.headers.get('x-chat-id');
      if (respChatId) {
        activeChatId = respChatId;
        setCurrentChatId(activeChatId);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          const chunk = decoder.decode(value);
          
          // Match state tags like [STATE: ANALYZING]
          const stateMatch = chunk.match(/\[STATE:\s*([^\]]+)\]/);
          if (stateMatch) {
            const stateText = stateMatch[1].trim();
            setCurrentState(stateText);
          }

          // Clean chunk of state tags
          const cleanChunk = chunk.replace(/\[STATE:[^\]]+\]\n?/g, '').replace(/\[STATE: CREATED\]\n?/g, '');
          assistantContent += cleanChunk;
          
          setMessages(prev => prev.map(msg => {
            if (msg.id === tempAiMsgId) {
              return { ...msg, content: assistantContent };
            }
            return msg;
          }));
        }
      }

      fetchChats();
      // Reload final message logs from sqlite
      if (activeChatId) {
        const resMsg = await fetch(`${API_BASE}/api/chats/${activeChatId}/messages`);
        if (resMsg.ok) {
          const actualMessages = await resMsg.json();
          setMessages(actualMessages);
        }
      }

    } catch (err) {
      console.error(err);
      fetchChats();
      let restoredFromDb = false;
      if (activeChatId) {
        try {
          const resMsg = await fetch(`${API_BASE}/api/chats/${activeChatId}/messages`);
          if (resMsg.ok) {
            const actualMessages = await resMsg.json();
            if (actualMessages && actualMessages.length > 0) {
              setMessages(actualMessages);
              restoredFromDb = true;
            }
          }
        } catch (dbErr) {
          console.error("DB message fetch failed:", dbErr);
        }
      }

      if (!restoredFromDb) {
        setMessages(prev => prev.map(msg => {
          if (msg.id === tempAiMsgId) {
            if (assistantContent && assistantContent.trim().length > 0) {
              return { ...msg, content: assistantContent };
            }
            return { ...msg, content: 'Generation interrupted. Verify network status and retry.' };
          }
          return msg;
        }));
      }
    } finally {
      setIsLoading(false);
      setCurrentState('');
    }
  };

  const executeCode = async (messageId, language, code) => {
    setSandboxOutputs(prev => ({
      ...prev,
      [messageId]: { output: '', error: '', isRunning: true }
    }));

    try {
      const res = await fetch(`${API_BASE}/api/execute_code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language, code })
      });
      if (res.ok) {
        const data = await res.json();
        setSandboxOutputs(prev => ({
          ...prev,
          [messageId]: { output: data.output, error: data.error, isRunning: false }
        }));
      } else {
        setSandboxOutputs(prev => ({
          ...prev,
          [messageId]: { output: '', error: 'HTTP Execution Error.', isRunning: false }
        }));
      }
    } catch (err) {
      setSandboxOutputs(prev => ({
        ...prev,
        [messageId]: { output: '', error: 'Sandbox disconnected.', isRunning: false }
      }));
    }
  };

  const getSuggestedFix = async (messageId, language, code, errorText) => {
    try {
      setFixData({
        language,
        originalCode: code,
        explanation: 'Consulting LAF system diagnostics...',
        correctedCode: '',
        errorText
      });
      setFixModalOpen(true);

      const res = await fetch(`${API_BASE}/api/fix_code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language, code, errors: [errorText] })
      });

      if (res.ok) {
        const data = await res.json();
        setFixData(prev => ({
          ...prev,
          explanation: data.explanation,
          correctedCode: data.corrected_code
        }));
      } else {
        setFixData(prev => ({
          ...prev,
          explanation: 'Trouble communicating with backend debugger.',
          correctedCode: code
        }));
      }
    } catch (err) {
      setFixData(prev => ({
        ...prev,
        explanation: 'Network failure calling code fix compiler.',
        correctedCode: code
      }));
    }
  };

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedText(id);
    setTimeout(() => setCopiedText(null), 2000);
  };

  // Export chat function
  const handleExportChat = (format) => {
    if (messages.length === 0) return;
    let mimeType = 'text/plain';
    let filename = `chat_${currentChatId || 'export'}`;
    let fileContent = '';

    if (format === 'json') {
      mimeType = 'application/json';
      filename += '.json';
      fileContent = JSON.stringify(messages, null, 2);
    } else {
      filename += '.md';
      fileContent = `# LAF AI Exported Conversation\n\n`;
      messages.forEach(msg => {
        fileContent += `### **${msg.role.toUpperCase()}** (${new Date(msg.timestamp).toLocaleString()})\n\n${msg.content}\n\n---\n\n`;
      });
    }

    const blob = new Blob([fileContent], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const shareChat = () => {
    if (messages.length === 0) {
      alert("No messages to share.");
      return;
    }
    let chatContent = `# LAF AI Shared Conversation\n\n`;
    messages.forEach(msg => {
      const sender = msg.role === 'user' ? userName : 'LAF AI : Model - L1';
      chatContent += `### **${sender}** (${new Date(msg.timestamp).toLocaleString()})\n\n${msg.content}\n\n---\n\n`;
    });
    navigator.clipboard.writeText(chatContent);
    alert("Conversation history copied to clipboard as formatted markdown! Share it anywhere. 🚀");
  };

  const downloadMessage = (msg) => {
    const mediaMatch = msg.content.match(/src="([^"]+)"/i);
    if (mediaMatch) {
      const mediaUrl = mediaMatch[1];
      const link = document.createElement('a');
      link.href = mediaUrl;
      link.download = mediaUrl.split('/').pop() || 'media_asset';
      link.target = '_blank';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } else {
      const blob = new Blob([msg.content], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `message_${msg.id}.txt`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }
  };

  // Advanced Markdown & HTML tags Parser for professional text rendering
  const parseMarkdownMessage = (msgId, content) => {
    if (!content) return null;
    
    // Split into segments by code blocks
    const segments = [];
    const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g;
    let lastIndex = 0;
    let match;

    while ((match = codeBlockRegex.exec(content)) !== null) {
      // Parse plain markdown text before code block
      if (match.index > lastIndex) {
        segments.push(
          <div key={`md-${lastIndex}`} className="markdown-block-wrapper">
            {parseRichText(content.substring(lastIndex, match.index))}
          </div>
        );
      }

      // Add code runner widget
      const language = match[1] || 'python';
      const code = match[2].trim();
      const codeBlockId = `${msgId}-code-${match.index}`;

      segments.push(
        <pre key={codeBlockId} className="code-block-container" style={{ margin: '14px 0', border: '1px solid var(--border-color)', borderRadius: '8px', background: '#07090f', overflow: 'hidden' }}>
          <div className="code-header" style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 14px', background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid var(--border-color)', fontSize: '11px', color: 'var(--text-secondary)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: '600' }}>
              <Terminal size={12} />
              {language.toUpperCase()}
            </span>
            <div className="code-header-actions" style={{ display: 'flex', gap: '8px' }}>
              <button 
                onClick={() => copyToClipboard(code, codeBlockId)} 
                className="code-action-btn"
                style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}
              >
                {copiedText === codeBlockId ? <Check size={12} style={{ color: '#4ade80' }} /> : <Copy size={12} />}
                <span>{copiedText === codeBlockId ? 'Copied' : 'Copy'}</span>
              </button>
              
              {['python', 'javascript', 'js', 'java', 'c', 'cpp', 'c++'].includes(language.toLowerCase()) && (
                <button 
                  onClick={() => executeCode(msgId, language, code)}
                  className="code-action-btn"
                  style={{ background: 'transparent', border: 'none', color: 'var(--accent-indigo)', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', fontWeight: '600' }}
                >
                  <Play size={12} />
                  <span>Run</span>
                </button>
              )}
            </div>
          </div>
          <code className="code-content" style={{ display: 'block', padding: '14px', overflowX: 'auto', fontFamily: 'var(--font-mono)', fontSize: '13px', color: '#cbd5e1' }}>{code}</code>
          
          {/* Sandbox terminal widget */}
          {sandboxOutputs[msgId] && (
            <div className="sandbox-output-panel" style={{ borderTop: '1px solid var(--border-color)', background: '#04050a' }}>
              <div className="sandbox-output-header" style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 14px', background: 'rgba(255,255,255,0.01)', borderBottom: '1px solid rgba(255,255,255,0.05)', fontSize: '11px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>⚡ CONSOLE OUTPUT</span>
                {sandboxOutputs[msgId].error && (
                  <button
                    onClick={() => getSuggestedFix(msgId, language, code, sandboxOutputs[msgId].error)}
                    className="code-action-btn"
                    style={{ color: '#f472b6', background: 'transparent', border: 'none', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}
                  >
                    <Wrench size={11} />
                    <span>Get AI Fix</span>
                  </button>
                )}
              </div>
              <div className={`sandbox-output-content ${sandboxOutputs[msgId].error ? 'error' : 'success'}`} style={{ padding: '12px 14px', whiteSpace: 'pre-wrap', fontFamily: 'var(--font-mono)', fontSize: '12.5px', color: sandboxOutputs[msgId].error ? '#f87171' : '#4ade80' }}>
                {sandboxOutputs[msgId].isRunning ? 'Process executing in sandbox...' : sandboxOutputs[msgId].output || sandboxOutputs[msgId].error || 'Success: exit code 0'}
              </div>
            </div>
          )}
        </pre>
      );

      lastIndex = codeBlockRegex.lastIndex;
    }

    if (lastIndex < content.length) {
      segments.push(
        <div key={`md-${lastIndex}`} className="markdown-block-wrapper">
          {parseRichText(content.substring(lastIndex))}
        </div>
      );
    }

    return segments;
  };

  // Helper parser for markdown syntax and HTML tag representations (images, videos, audio)
  const parseRichText = (text) => {
    const elements = [];
    const mediaRegex = /<(video|audio|img)\s+src="([^"]+)"\s*(?:alt="([^"]*)")?>\s*(?:<\/\1>)?/gi;
    let lastIndex = 0;
    let match;

    while ((match = mediaRegex.exec(text)) !== null) {
      const prevText = text.substring(lastIndex, match.index);
      if (prevText) {
        elements.push(...parseMarkdownBlocks(prevText, `syntax-${lastIndex}`));
      }

      const tag = match[1].toLowerCase();
      const src = match[2];
      const alt = match[3] || 'media attachment';
      const key = `media-${lastIndex}`;

      if (tag === 'img') {
        elements.push(<img key={key} src={src} alt={alt} className="media-tag-image" style={{ maxWidth: '100%', borderRadius: '8px', margin: '8px 0', border: '1px solid var(--border-color)' }} />);
      } else if (tag === 'audio') {
        elements.push(<audio key={key} src={src} controls className="media-tag-audio" style={{ width: '100%', margin: '8px 0' }} />);
      } else if (tag === 'video') {
        elements.push(<video key={key} src={src} controls className="media-tag-video" style={{ width: '100%', borderRadius: '8px', background: '#000', margin: '8px 0' }} />);
      }

      lastIndex = mediaRegex.lastIndex;
    }

    if (lastIndex < text.length) {
      elements.push(...parseMarkdownBlocks(text.substring(lastIndex), `syntax-${lastIndex}`));
    }

    return elements;
  };

  // Parser for blocks: handles headings, lists, and tabular data tables
  const parseMarkdownBlocks = (text, keyPrefix) => {
    const blocks = [];
    const lines = text.split('\n');
    let currentTable = null;
    let currentList = null;
    let currentParagraph = [];

    const flushParagraph = (key) => {
      if (currentParagraph.length > 0) {
        blocks.push(
          <p key={key} style={{ margin: '6px 0', lineHeight: '1.6', wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
            {currentParagraph}
          </p>
        );
        currentParagraph = [];
      }
    };

    const flushTable = (key) => {
      if (currentTable) {
        blocks.push(renderHTMLTable(key, currentTable));
        currentTable = null;
      }
    };

    const flushList = (key) => {
      if (currentList) {
        if (currentList.type === 'ordered') {
          blocks.push(
            <ol key={key} className="markdown-numbered-list" style={{ margin: '6px 0 6px 20px', paddingLeft: '0' }}>
              {currentList.items.map((item, idx) => <li key={idx} className="markdown-numbered-item" style={{ listStyleType: 'decimal', marginBottom: '3px' }}>{item}</li>)}
            </ol>
          );
        } else {
          blocks.push(
            <ul key={key} className="markdown-bullet-list" style={{ margin: '6px 0 6px 20px', paddingLeft: '0' }}>
              {currentList.items.map((item, idx) => <li key={idx} className="markdown-bullet-item" style={{ listStyleType: 'disc', marginBottom: '3px' }}>{item}</li>)}
            </ul>
          );
        }
        currentList = null;
      }
    };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const lineTrim = line.trim();

      // Check Table block: starts and ends with |
      if (lineTrim.startsWith('|') && lineTrim.endsWith('|')) {
        flushParagraph(`p-${i}`);
        flushList(`l-${i}`);
        if (!currentTable) {
          currentTable = [];
        }
        currentTable.push(lineTrim);
        continue;
      } else {
        flushTable(`t-${i}`);
      }

      // Check Unordered List item
      if (lineTrim.startsWith('- ') || lineTrim.startsWith('* ')) {
        flushParagraph(`p-${i}`);
        if (!currentList || currentList.type !== 'unordered') {
          flushList(`l-${i}`);
          currentList = { type: 'unordered', items: [] };
        }
        currentList.items.push(renderTextStyles(lineTrim.substring(2)));
        continue;
      }

      // Check Ordered List item
      const numMatch = lineTrim.match(/^(\d+)\.\s(.*)/);
      if (numMatch) {
        flushParagraph(`p-${i}`);
        if (!currentList || currentList.type !== 'ordered') {
          flushList(`l-${i}`);
          currentList = { type: 'ordered', items: [] };
        }
        currentList.items.push(renderTextStyles(numMatch[2]));
        continue;
      }

      // Flush lists if we didn't match a list item
      flushList(`l-${i}`);

      // Headings
      if (lineTrim.startsWith('### ')) {
        flushParagraph(`p-${i}`);
        blocks.push(<h4 key={`h3-${i}`} className="markdown-header-3">{renderTextStyles(lineTrim.substring(4))}</h4>);
        continue;
      }
      if (lineTrim.startsWith('## ')) {
        flushParagraph(`p-${i}`);
        blocks.push(<h3 key={`h2-${i}`} className="markdown-header-2">{renderTextStyles(lineTrim.substring(3))}</h3>);
        continue;
      }
      if (lineTrim.startsWith('# ')) {
        flushParagraph(`p-${i}`);
        blocks.push(<h2 key={`h1-${i}`} style={{ fontSize: '18px', fontWeight: '800', margin: '18px 0 8px 0', borderBottom: '1px solid var(--border-color)', paddingBottom: '4px' }}>{renderTextStyles(lineTrim.substring(2))}</h2>);
        continue;
      }

      // Normal paragraph text
      if (lineTrim === '') {
        flushParagraph(`p-${i}`);
      } else {
        currentParagraph.push(renderTextStyles(line));
        if (i < lines.length - 1) {
          currentParagraph.push(<br key={`br-${i}`} />);
        }
      }
    }

    flushParagraph('p-final');
    flushTable('t-final');
    flushList('l-final');

    return blocks;
  };

  // Render markdown tables beautifully with clean scrolling and formatting
  const renderHTMLTable = (key, rawRows) => {
    if (rawRows.length < 1) return null;
    
    const parsedRows = rawRows.map(row => 
      row.split('|').map(cell => cell.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1)
    );

    const header = parsedRows[0];
    let dataRows = parsedRows.slice(1);
    
    // Filter separator rows (---|---|---)
    if (dataRows.length > 0 && dataRows[0].every(cell => cell.startsWith('-') || cell.startsWith(':'))) {
      dataRows = dataRows.slice(1);
    }

    return (
      <div key={key} style={{ overflowX: 'auto', maxWidth: '100%', margin: '12px 0', borderRadius: '8px', border: '1px solid var(--border-color)', WebkitOverflowScrolling: 'touch' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', textAlign: 'left', background: 'rgba(255,255,255,0.01)' }}>
          <thead>
            <tr style={{ background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid var(--border-color)' }}>
              {header.map((cell, idx) => (
                <th key={idx} style={{ padding: '10px 12px', fontWeight: '600', color: '#fff', whiteSpace: 'nowrap' }}>
                  {renderTextStyles(cell)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dataRows.map((row, rowIdx) => (
              <tr key={rowIdx} style={{ borderBottom: rowIdx < dataRows.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none' }}>
                {row.map((cell, cellIdx) => (
                  <td key={cellIdx} style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>
                    {renderTextStyles(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  // Render inline styles like **bold**, *italic*, [link](url), and `inline code`
  const renderTextStyles = (text) => {
    if (!text) return '';
    let parts = [text];

    // 1. Inline code: `code`
    parts = parts.flatMap((part, idx) => {
      if (typeof part !== 'string') return part;
      const chunks = [];
      const regex = /`([^`]+)`/g;
      let last = 0;
      let m;
      while ((m = regex.exec(part)) !== null) {
        if (m.index > last) chunks.push(part.substring(last, m.index));
        chunks.push(<code key={`ic-${idx}-${m.index}`} className="markdown-inline-code">{m[1]}</code>);
        last = regex.lastIndex;
      }
      if (last < part.length) chunks.push(part.substring(last));
      return chunks;
    });

    // 2. Bold text: **bold**
    parts = parts.flatMap((part, idx) => {
      if (typeof part !== 'string') return part;
      const chunks = [];
      const regex = /\*\*([^*]+)\*\*/g;
      let last = 0;
      let m;
      while ((m = regex.exec(part)) !== null) {
        if (m.index > last) chunks.push(part.substring(last, m.index));
        chunks.push(<strong key={`b-${idx}-${m.index}`} className="markdown-bold">{m[1]}</strong>);
        last = regex.lastIndex;
      }
      if (last < part.length) chunks.push(part.substring(last));
      return chunks;
    });

    // 3. Italic text: *italic*
    parts = parts.flatMap((part, idx) => {
      if (typeof part !== 'string') return part;
      const chunks = [];
      const regex = /\*([^*]+)\*/g;
      let last = 0;
      let m;
      while ((m = regex.exec(part)) !== null) {
        if (m.index > last) chunks.push(part.substring(last, m.index));
        chunks.push(<em key={`it-${idx}-${m.index}`} className="markdown-italic">{m[1]}</em>);
        last = regex.lastIndex;
      }
      if (last < part.length) chunks.push(part.substring(last));
      return chunks;
    });

    // 4. Links: [title](url)
    parts = parts.flatMap((part, idx) => {
      if (typeof part !== 'string') return part;
      const chunks = [];
      const regex = /\[([^\]]+)\]\(([^)]+)\)/g;
      let last = 0;
      let m;
      while ((m = regex.exec(part)) !== null) {
        if (m.index > last) chunks.push(part.substring(last, m.index));
        chunks.push(<a key={`lnk-${idx}-${m.index}`} href={m[2]} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-blue)', textDecoration: 'underline' }}>{m[1]}</a>);
        last = regex.lastIndex;
      }
      if (last < part.length) chunks.push(part.substring(last));
      return chunks;
    });

    return parts;
  };

  // Filter conversations
  const filteredChats = chats.filter(chat => 
    chat.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="app-layout">
      {/* Ambient background animation */}
      <div className="bg-animation-container">
        <div className="bg-glow bg-glow-1"></div>
        <div className="bg-glow bg-glow-2"></div>
        <div className="bg-glow bg-glow-3"></div>
      </div>

      {/* Mobile Sidebar Overlay */}
      <div 
        className={`sidebar-overlay ${sidebarOpen ? 'show' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      {/* Sidebar */}
      <div className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div 
            style={{ 
              width: '28px', 
              height: '28px', 
              borderRadius: '50%', 
              backgroundColor: '#ffffff', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              overflow: 'hidden'
            }}
          >
            <img 
              src="/laf-logo.png" 
              alt="LAF Logo" 
              style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
              onError={(e) => { e.target.onerror = null; e.target.src = "/laf-logo.svg"; }}
            />
          </div>
          <span className="logo-name">LAF Console</span>
          {/* Mobile close button */}
          <button 
            className="icon-action-btn"
            onClick={() => setSidebarOpen(false)}
            style={{ display: window.innerWidth <= 768 ? 'block' : 'none' }}
          >
            <X size={16} />
          </button>
        </div>
        
        {/* Search Conversation */}
        <div className="search-box-container">
          <input 
            type="text" 
            placeholder="Search conversations..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="search-input"
          />
        </div>

        <button onClick={handleNewChat} className="new-chat-button">
          <Plus size={14} />
          <span>New Chat Session</span>
        </button>

        <div className="chat-history-scroll">
          {filteredChats.map(chat => (
            <div 
              key={chat.id} 
              onClick={() => {
                selectChat(chat.id);
                setSidebarOpen(false);
              }}
              className={`chat-item ${currentChatId === chat.id ? 'selected' : ''}`}
            >
              <div className="chat-item-text">
                <span>{chat.title}</span>
              </div>
              <div className="chat-item-actions">
                <button 
                  onClick={(e) => handleDeleteChat(e, chat.id)} 
                  className="icon-action-btn"
                  title="Delete conversation"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          <div 
            className="user-badge" 
            onClick={() => {
              setUsernameInput(userName);
              setUsernameModalOpen(true);
            }}
            title="Click to edit name / login as user"
            style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div className="user-avatar" style={{ position: 'relative' }}>
                {getUserInitials(userName)}
                {/* Update Notification Badge */}
                {updateAvailable && (
                  <span 
                    style={{
                      position: 'absolute',
                      top: -2,
                      right: -2,
                      width: 10,
                      height: 10,
                      background: '#f472b6',
                      borderRadius: '50%',
                      border: '2px solid var(--bg-sidebar)'
                    }}
                  />
                )}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontWeight: '600', fontSize: '13px' }}>{userName || 'Enter Name'}</span>
                <span style={{ fontSize: '10px', color: 'var(--accent-indigo)' }}>Edit</span>
              </div>
            </div>
            <User size={15} style={{ color: 'var(--text-secondary)' }} />
          </div>
        </div>
      </div>

      {/* Main chat interface view */}
      <div className="main-chat-container">
        <div className="main-chat-header">
          <div className="header-title-section" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* Mobile Menu Toggle */}
            <button 
              className="icon-action-btn"
              onClick={() => setSidebarOpen(true)}
              style={{ display: window.innerWidth <= 768 ? 'flex' : 'none' }}
            >
              <Menu size={18} />
            </button>
            <h3>{currentChatId ? chats.find(c => c.id === currentChatId)?.title || 'Conversation log' : (
              <button 
                onClick={handleInstallPWA}
                className="model-select-dropdown"
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '6px', 
                  fontWeight: '600', 
                  color: 'var(--accent-indigo)',
                  cursor: 'pointer'
                }}
              >
                <Smartphone size={14} />
                <span>Download App</span>
              </button>
            )}</h3>
          </div>

          <div className="header-right-actions">
            {messages.length > 0 && (
              <button 
                onClick={shareChat} 
                className="model-select-dropdown"
                style={{ display: 'flex', alignItems: 'center', gap: '5px', fontWeight: '600', color: 'var(--accent-purple)' }}
                title="Share this conversation"
              >
                <Share2 size={13} />
                <span>Share Chat</span>
              </button>
            )}

            <button 
              onClick={() => setCodeItOpen(prev => !prev)} 
              className="model-select-dropdown"
              style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: '600', color: 'var(--accent-indigo)' }}
            >
              <Code size={14} />
              <span>Code_It</span>
            </button>

            <span 
              className="model-select-dropdown"
              style={{ fontWeight: '600', color: 'var(--text-secondary)', cursor: 'default' }}
            >
              Model : LAF 1
            </span>
          </div>
        </div>

        {/* Message viewport */}
        {messages.length === 0 ? (
          <div className="welcome-viewport">
            <div 
              className="welcome-logo-container" 
              style={{ 
                width: '96px', 
                height: '96px', 
                borderRadius: '50%', 
                backgroundColor: '#ffffff', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center', 
                marginBottom: '24px', 
                boxShadow: '0 0 20px rgba(99, 102, 241, 0.35)', 
                overflow: 'hidden',
                margin: '0 auto 24px auto'
              }}
            >
              <img 
                src="/laf-logo.png" 
                alt="LAF Logo" 
                style={{ 
                  width: '100%', 
                  height: '100%', 
                  objectFit: 'cover'
                }} 
                onError={(e) => { e.target.onerror = null; e.target.src = "/laf-logo.svg"; }}
              />
            </div>
            <h2 className="welcome-heading">LAF Welcomes you - {userName}</h2>
            <p className="welcome-time-greeting" style={{ fontSize: '15px', color: 'var(--text-secondary)', marginTop: '8px', fontWeight: '500' }}>
              {(() => {
                const hour = new Date().getHours();
                if (hour < 12) return 'Good morning';
                if (hour < 17) return 'Good afternoon';
                return 'Good evening';
              })()}!
            </p>
          </div>
        ) : (
          <div className="messages-viewport">
            {messages.map(msg => (
              <div key={msg.id} className={`chat-bubble-row ${msg.role === 'user' ? 'user' : 'ai'}`}>
                <div className={`bubble-avatar ${msg.role === 'user' ? 'user' : 'ai'}`} title={msg.role === 'user' ? userName : 'LAF AI : Model - L1'}>
                  {msg.role === 'user' ? (
                    getUserInitials(userName)
                  ) : (
                    <img src="/laf-logo.png" alt="LAF Logo" style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }} onError={(e) => { e.target.onerror = null; e.target.src = "/laf-logo.svg"; }} />
                  )}
                </div>
                <div className="bubble-body-container">
                  <div className="bubble-sender-name" style={{ fontSize: '11px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '2px', alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                    {msg.role === 'user' ? userName : 'LAF AI : Model - L1'}
                  </div>
                  <div className="chat-bubble">
                    {editingMessageId === msg.id ? (
                      <div>
                        <textarea 
                          value={editText} 
                          onChange={(e) => setEditText(e.target.value)}
                          className="edit-message-textarea"
                          style={{ border: '1px solid var(--accent-indigo)' }}
                        />
                        <div className="edit-actions-row">
                          <button onClick={() => setEditingMessageId(null)} className="edit-btn-cancel">Cancel</button>
                          <button onClick={() => handleEditMessage(msg.id, editText)} className="edit-btn-save">Save</button>
                        </div>
                      </div>
                    ) : (
                      parseMarkdownMessage(msg.id, msg.content)
                    )}
                  </div>
                  
                  {/* Meta control line */}
                  {!editingMessageId && (
                    <div className="message-meta-info">
                      <span>{new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      <span>•</span>
                      <span onClick={() => copyToClipboard(msg.content, msg.id)} className="meta-link" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                        {copiedText === msg.id ? <Check size={11} color="#10b981" /> : <Copy size={11} />}
                        {copiedText === msg.id ? 'Copied!' : 'Copy'}
                      </span>
                      <span>•</span>
                      <span onClick={() => speakMessage(msg.content)} className="meta-link" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                        <Volume2 size={11} /> Speak
                      </span>
                      {msg.role === 'user' && (
                        <>
                          <span>•</span>
                          <span onClick={() => { setEditingMessageId(msg.id); setEditText(msg.content); }} className="meta-link">
                            Edit
                          </span>
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
            
            {/* Show streaming state loader when generating */}
            {isLoading && currentState && (
              <div className="state-loader-container">
                <div className="state-loader-spinner"></div>
                <span>LAF Status: {currentState}...</span>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Input Controls */}
        <div className="floating-input-panel">
          <div className="chat-input-wrapper">
            
            {/* Attachment preview row */}
            {attachments.length > 0 && (
              <div className="attachment-preview-bar">
                {attachments.map((att, idx) => (
                  <div key={idx} className="attachment-preview-chip">
                    <FileText size={11} />
                    <span style={{ maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{att.name}</span>
                    <button onClick={() => removeAttachment(idx)} className="attachment-remove-btn">
                      <X size={10} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="chat-textarea-row">
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                placeholder={attachments.length > 0 ? "Prompt about attached files..." : "Send prompt (Add /search for web queries, upload Excel/text files)..."}
                className="textarea-field"
                rows={1}
              />
              
              <div className="chat-input-actions-row">
                {/* File Upload click trigger */}
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  onChange={handleAttachmentUpload}
                  style={{ display: 'none' }}
                  multiple 
                />
                <button 
                  onClick={() => fileInputRef.current?.click()} 
                  className="input-trigger-btn"
                  title="Attach text, code or Excel files"
                >
                  <Paperclip size={15} />
                </button>

                {/* Speech Dictation Button */}
                <button 
                  onClick={toggleDictation}
                  className={`input-trigger-btn ${isDictating ? 'active' : ''}`}
                  title={isDictating ? "Listening..." : "Dictate Prompt"}
                >
                  {isDictating ? <MicOff size={15} /> : <Mic size={15} />}
                </button>

                <button 
                  onClick={() => handleSendMessage()}
                  disabled={(!inputText.trim() && attachments.length === 0) || isLoading}
                  className="submit-chat-btn"
                >
                  <Send size={14} />
                </button>
              </div>
            </div>
          </div>
          <div className="input-bottom-copyright">
            © {new Date().getFullYear()} LAF AI. All rights reserved. •{' '}
            <button onClick={() => { setDocType('privacy'); setDocModalOpen(true); }} className="doc-link-btn">Privacy Policy</button> •{' '}
            <button onClick={() => { setDocType('terms'); setDocModalOpen(true); }} className="doc-link-btn">Terms of Service</button>
          </div>
        </div>
      </div>

      {/* Settings Modal */}
      {settingsModalOpen && (
        <div className="professional-modal-backdrop" onClick={() => setSettingsModalOpen(false)}>
          <div className="professional-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title-bar">
              <h4>System Configuration</h4>
              <button onClick={() => setSettingsModalOpen(false)} className="icon-action-btn">
                <X size={16} style={{ color: 'var(--text-secondary)' }} />
              </button>
            </div>
            <div className="modal-body">
              <div className="modal-input-group">
                <span className="modal-input-label">Custom System Instruction (Model Guidance)</span>
                <textarea 
                  value={customSystemPrompt} 
                  onChange={(e) => setCustomSystemPrompt(e.target.value)}
                  className="modal-text-input"
                  style={{ minHeight: '80px', fontFamily: 'var(--font-sans)', resize: 'vertical' }}
                />
              </div>
              <div className="modal-input-group">
                <span className="modal-input-label">Encrypted Storage Schema</span>
                <input 
                  type="text" 
                  value="Fernet Symmetric Key Derivation (AES-128)" 
                  disabled 
                  className="modal-text-input" 
                  style={{ opacity: 0.7 }}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button onClick={() => setSettingsModalOpen(false)} className="modal-action-btn primary">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Database stats Modal */}
      {statsModalOpen && (
        <div className="professional-modal-backdrop" onClick={() => setStatsModalOpen(false)}>
          <div className="professional-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title-bar">
              <h4>SQLite Storage Diagnostics</h4>
              <button onClick={() => setStatsModalOpen(false)} className="icon-action-btn">
                <X size={16} style={{ color: 'var(--text-secondary)' }} />
              </button>
            </div>
            <div className="modal-body">
              <div className="stat-row">
                <span>Active Chat Containers</span>
                <span style={{ fontWeight: '600' }}>{chats.length} Sessions</span>
              </div>
              <div className="stat-row">
                <span>Global Messages Recorded</span>
                <span style={{ fontWeight: '600' }}>
                  {messages.length > 0 ? messages.length : 'Select a chat to inspect messages'}
                </span>
              </div>
              <div className="stat-row">
                <span>Database Encryption</span>
                <span style={{ color: '#4ade80', fontWeight: '600' }}>Active (E2EE Enabled)</span>
              </div>
              <div className="stat-row">
                <span>Memory Context Matching</span>
                <span style={{ color: 'var(--accent-indigo)', fontWeight: '600' }}>TF-IDF Cosine Similarity</span>
              </div>
            </div>
            <div className="modal-footer">
              <button onClick={() => setStatsModalOpen(false)} className="modal-action-btn primary">Dismiss</button>
            </div>
          </div>
        </div>
      )}

      {/* Suggested Fix Diagnostics Modal */}
      {fixModalOpen && (
        <div className="professional-modal-backdrop" onClick={() => setFixModalOpen(false)}>
          <div className="professional-modal" style={{ maxWidth: '700px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-title-bar" style={{ borderBottom: '1px solid rgba(244, 114, 182, 0.2)' }}>
              <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#f472b6' }}>
                <Sparkles size={16} />
                <span>AI Compilation Debugger</span>
              </h4>
              <button onClick={() => setFixModalOpen(false)} className="icon-action-btn">
                <X size={16} />
              </button>
            </div>
            <div className="modal-body">
              <div className="modal-input-group">
                <span className="modal-input-label" style={{ color: '#f87171' }}>Diagnostic Console Trace:</span>
                <pre style={{ background: '#07090f', padding: '10px', borderRadius: '6px', fontSize: '12px', color: '#f87171', whiteSpace: 'pre-wrap', fontFamily: 'var(--font-mono)' }}>
                  {fixData.errorText}
                </pre>
              </div>

              <div className="modal-input-group">
                <span className="modal-input-label" style={{ color: '#a78bfa' }}>AI Explanation:</span>
                <div style={{ background: 'rgba(255,255,255,0.01)', padding: '10px', borderRadius: '6px', fontSize: '13px', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>
                  {fixData.explanation}
                </div>
              </div>

              <div className="modal-input-group">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <span className="modal-input-label" style={{ color: '#4ade80' }}>Suggested Corrected Code:</span>
                  <button 
                    onClick={() => copyToClipboard(fixData.correctedCode, 'modal-fix-code')}
                    className="code-action-btn"
                    style={{ border: 'none', background: 'transparent', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', fontSize: '11px' }}
                  >
                    {copiedText === 'modal-fix-code' ? <Check size={12} style={{ color: '#4ade80' }} /> : <Copy size={12} />}
                    <span>{copiedText === 'modal-fix-code' ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>
                <pre style={{ background: '#07090f', padding: '12px', borderRadius: '6px', overflowX: 'auto', fontFamily: 'var(--font-mono)', fontSize: '12.5px', color: '#e2e8f0', border: '1px solid rgba(255,255,255,0.04)' }}>
                  <code>{fixData.correctedCode || 'Compiling fix...'}</code>
                </pre>
              </div>
            </div>
            <div className="modal-footer">
              <button onClick={() => setFixModalOpen(false)} className="modal-action-btn primary">Dismiss</button>
            </div>
          </div>
        </div>
      )}
      {/* Privacy Policy and Terms of Service Modal */}
      {docModalOpen && (
        <div className="professional-modal-backdrop" onClick={() => setDocModalOpen(false)}>
          <div className="professional-modal" style={{ maxWidth: '600px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-title-bar">
              <h4>{docType === 'privacy' ? 'Privacy Policy' : 'Terms of Service'}</h4>
              <button onClick={() => setDocModalOpen(false)} className="icon-action-btn">
                <X size={16} style={{ color: 'var(--text-secondary)' }} />
              </button>
            </div>
            <div className="modal-body" style={{ maxHeight: '400px', overflowY: 'auto', fontSize: '13px', lineHeight: '1.6', color: 'var(--text-secondary)', paddingRight: '8px' }}>
              {docType === 'privacy' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <p style={{ fontWeight: '600', color: 'var(--text-primary)' }}>LAF AI Privacy Policy</p>
                  <p>Effective Date: July 18, 2026</p>
                  <p><strong>1. Data Encryption & Security:</strong> LAF AI ensures all conversation history and database records are encrypted using Fernet Symmetric Key Derivation (AES-128) protocols. Your data remains secure and private on your local storage device.</p>
                  <p><strong>2. Local Data Storage:</strong> Conversations are saved to a local SQLite database. No external cloud server has access to read, scan, or process your chat histories, ensuring absolute confidentiality.</p>
                  <p><strong>3. Inference Transmissions:</strong> If cloud reasoning models are selected, your current query is processed securely through API endpoints (such as Google Gemini). These inputs are not used for public model training in accordance with developer and enterprise data terms.</p>
                  <p><strong>4. Export & Rights:</strong> You retain complete control of your local histories. You can export data at any time or truncate/delete histories directly within the interface.</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <p style={{ fontWeight: '600', color: 'var(--text-primary)' }}>LAF AI Terms of Service</p>
                  <p>Effective Date: July 18, 2026</p>
                  <p><strong>1. Agreement to Terms:</strong> By accessing and executing prompts on the LAF AI platform, you agree to be bound by these service terms.</p>
                  <p><strong>2. Local Compiler Execution:</strong> The application provides interactive compilers sandboxed natively inside secure execution contexts. The user accepts full responsibility for scripts run within these sandboxes.</p>
                  <p><strong>3. Service Modification & Ownership:</strong> LAF AI is designed by Purushothaman. The developer provides the platform "as-is" and reserves the right to modify system defaults, local architectures, and tools at any time.</p>
                  <p><strong>4. Disclaimer of Liability:</strong> In no event shall the developer be held liable for any data loss, sandbox compiler issues, API failures, or damages arising out of the performance of the system.</p>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button onClick={() => setDocModalOpen(false)} className="modal-action-btn primary">Dismiss</button>
            </div>
          </div>
        </div>
      )}
      {/* Username Setup / Login Modal for New Users */}
      {usernameModalOpen && (
        <div className="professional-modal-backdrop" style={{ zIndex: 9999 }}>
          <div className="professional-modal" style={{ maxWidth: '420px', textAlign: 'center', padding: '28px', borderRadius: '16px', border: '1px solid var(--border-color, rgba(255,255,255,0.1))' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
              <div 
                style={{ 
                  width: '72px', 
                  height: '72px', 
                  borderRadius: '20px', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  overflow: 'hidden',
                  boxShadow: '0 0 25px rgba(99, 102, 241, 0.45)',
                  backgroundColor: '#6366f1'
                }}
              >
                <img 
                  src="/laf-logo.png" 
                  alt="LAF Logo" 
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
                  onError={(e) => { e.target.onerror = null; e.target.src = "/laf-logo.svg"; }}
                />
              </div>
              <div>
                <h3 style={{ fontSize: '20px', fontWeight: '700', color: 'var(--text-primary)', margin: '0 0 6px 0' }}>Welcome to LAF AI</h3>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0 }}>Please enter your name to log in and start your session:</p>
              </div>
              
              <input 
                type="text" 
                placeholder="Enter your name..." 
                value={usernameInput}
                onChange={(e) => setUsernameInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSaveUsername(); }}
                className="code-it-stdin-input"
                style={{ width: '100%', textAlign: 'center', fontSize: '15px', padding: '12px 16px', borderRadius: '10px' }}
                autoFocus
              />

              <button 
                onClick={handleSaveUsername} 
                disabled={!usernameInput.trim()}
                className="code-it-btn-run"
                style={{ width: '100%', padding: '12px', fontSize: '15px', fontWeight: '600', borderRadius: '10px' }}
              >
                Log In & Continue
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Code_It Workspace */}
      {codeItOpen && (
        <div className="code-it-sidebar">
          <div className="sidebar-header" style={{ borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: '700', color: 'var(--text-primary)', fontSize: '14px' }}>Code_It Workspace</span>
            <button onClick={() => setCodeItOpen(false)} className="icon-action-btn" title="Close Workspace">
              <X size={16} />
            </button>
          </div>
          
          <div className="code-it-editor-container">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span className="code-it-label">Practice Language</span>
              <select 
                value={codeItLang} 
                onChange={(e) => handleLanguageChange(e.target.value)}
                className="code-it-select"
              >
                <option value="python">Python</option>
                <option value="javascript">JavaScript (Node.js)</option>
                <option value="cpp">C++ (GCC)</option>
                <option value="c">C (GCC)</option>
                <option value="java">Java (OpenJDK)</option>
              </select>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="code-it-label">Editor</span>
                <button 
                  onClick={() => setCodeItCode(CODE_TEMPLATES[codeItLang])} 
                  className="code-action-btn"
                  style={{ border: 'none', background: 'transparent', color: 'var(--accent-indigo)', fontSize: '11px', cursor: 'pointer' }}
                >
                  Reset Template
                </button>
              </div>
              <textarea
                value={codeItCode}
                onChange={(e) => setCodeItCode(e.target.value)}
                className="code-it-textarea"
                placeholder="Write your code here..."
              />
            </div>

            <div className="code-it-console">
              <div className="code-it-console-header">
                <span>⚡ EXECUTION CONSOLE</span>
                {(codeItConsoleOutput || codeItConsoleError) && (
                  <button 
                    onClick={() => { setCodeItConsoleOutput(''); setCodeItConsoleError(''); }} 
                    style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '9px' }}
                  >
                    Clear
                  </button>
                )}
              </div>
              <div className="code-it-console-body" style={{ color: codeItConsoleError ? '#f87171' : '#4ade80' }}>
                {codeItIsRunning ? 'Compiling and executing code in sandbox...' : codeItConsoleOutput || codeItConsoleError || 'Sandbox ready. Click Run Code to execute.'}
              </div>
            </div>
          </div>
          
          <div className="code-it-actions-footer">
            <button 
              onClick={runCodeIt} 
              disabled={codeItIsRunning || !codeItCode.trim()} 
              className="code-it-btn-run"
              style={{ flex: 1 }}
            >
              <Play size={13} style={{ fill: 'currentColor' }} />
              <span>{codeItIsRunning ? 'Running...' : 'Run Code'}</span>
            </button>
            <button 
              onClick={askLafToReviewCode} 
              disabled={codeItIsRunning || !codeItCode.trim()}
              className="code-it-btn-secondary"
              title="Send to LAF AI for review"
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Sparkles size={13} style={{ color: 'var(--accent-purple)' }} />
              <span>Ask LAF</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
