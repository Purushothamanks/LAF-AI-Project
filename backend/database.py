import sqlite3
import os
import uuid
import base64
import re
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

DB_PATH = os.path.join(os.path.dirname(__file__), "laf_storage.db")

# Deterministic key derivation setup
SECRET_SALT = b"laf_encryption_salt_2026"
SECRET_PASSWORD = b"laf_secure_e2ee_credentials_passphrase"

kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=SECRET_SALT,
    iterations=100000,
)
encryption_key = base64.urlsafe_b64encode(kdf.derive(SECRET_PASSWORD))
fernet = Fernet(encryption_key)

def encrypt_text(text: str) -> str:
    """
    Encrypts text to a secure base64 string.
    """
    if not text:
        return text
    try:
        encrypted_bytes = fernet.encrypt(text.encode("utf-8"))
        return "E2EE:" + encrypted_bytes.decode("utf-8")
    except Exception as e:
        print(f"Encryption error: {e}")
        return text

def decrypt_text(text: str) -> str:
    """
    Decrypts a base64 string back to plaintext.
    """
    if not text or not text.startswith("E2EE:"):
        return text
    try:
        encrypted_part = text[5:]
        decrypted_bytes = fernet.decrypt(encrypted_part.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except Exception as e:
        print(f"Decryption error: {e}")
        return text

def get_db_connection():
    """
    Establish connection to SQLite database with thread safety and WAL configurations.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
    except sqlite3.OperationalError:
        pass
    return conn

def init_db():
    """
    Initialize SQLite tables for chats and messages.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Create chats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Dynamic migration: add device_id column to chats if it doesn't exist
        try:
            cursor.execute("ALTER TABLE chats ADD COLUMN device_id TEXT DEFAULT 'global'")
        except sqlite3.OperationalError:
            pass
            
        # Create messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats (id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for optimized queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages (chat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages (timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chats_device_id ON chats (device_id)")
        
        # AI Model Knowledge & Trained Datasets Tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_model_knowledge (
                id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                provider TEXT,
                family TEXT,
                category TEXT,
                description TEXT,
                capabilities TEXT,
                context_limit INTEGER,
                trained_data_snippet TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trained_datasets (
                id TEXT PRIMARY KEY,
                dataset_name TEXT NOT NULL,
                source TEXT,
                domain TEXT,
                content TEXT NOT NULL,
                accuracy_score REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_name ON ai_model_knowledge (model_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dataset_domain ON trained_datasets (domain)")
        conn.commit()

def create_chat(title="New Chat", device_id="global") -> str:
    """
    Creates a new chat session and returns its ID.
    """
    chat_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO chats (id, title, created_at, device_id) VALUES (?, ?, ?, ?)",
            (chat_id, title, created_at, device_id)
        )
        conn.commit()
    return chat_id

def get_all_chats(device_id="global"):
    """
    Fetches all chat sessions matching device_id sorted by creation date (newest first).
    """
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM chats WHERE device_id = ? ORDER BY created_at DESC",
            (device_id,)
        ).fetchall()
        return [dict(row) for row in rows]

def get_messages_for_chat(chat_id: str):
    """
    Fetches message history for a specific chat, decrypting message content.
    """
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY timestamp ASC",
            (chat_id,)
        ).fetchall()
        
        messages = []
        for row in rows:
            d_row = dict(row)
            d_row["content"] = decrypt_text(d_row["content"])
            messages.append(d_row)
        return messages

def add_message_to_chat(chat_id: str, role: str, content: str) -> str:
    """
    Adds a message to a chat session, encrypting message content.
    """
    msg_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    
    # If this is the first user message, update the chat title to match the query (plaintext title)
    if role == "user":
        with get_db_connection() as conn:
            # Check if this is the first user message in this chat
            message_count = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE chat_id = ? AND role = 'user'",
                (chat_id,)
            ).fetchone()[0]
            
            if message_count == 0:
                # Update title to a preview of the prompt
                title = content[:30] + "..." if len(content) > 30 else content
                conn.execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))
                conn.commit()

    encrypted_content = encrypt_text(content)
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO messages (id, chat_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (msg_id, chat_id, role, encrypted_content, timestamp)
        )
        conn.commit()
    return msg_id

def delete_chat(chat_id: str):
    """
    Deletes a chat session and all its messages.
    """
    with get_db_connection() as conn:
        conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        conn.commit()

def edit_db_message(msg_id: str, new_content: str):
    """
    Edits the content of a specific message in the database, encrypting content.
    """
    encrypted_content = encrypt_text(new_content)
    with get_db_connection() as conn:
        conn.execute("UPDATE messages SET content = ? WHERE id = ?", (encrypted_content, msg_id))
        conn.commit()

def truncate_messages_after(chat_id: str, timestamp: str):
    """
    Deletes all messages in a chat that occurred after a specific timestamp.
    """
    with get_db_connection() as conn:
        conn.execute("DELETE FROM messages WHERE chat_id = ? AND timestamp > ?", (chat_id, timestamp))
        conn.commit()

def get_global_memory_context(current_chat_id: str, query_prompt: str = None, limit: int = 5) -> str:
    """
    Retrieves a list of highly relevant messages from other chats to serve as global memory context using TF-IDF similarity.
    Falls back to chronological recent messages if no query_prompt is provided or similarity match is low.
    """
    try:
        import collections
        import math
        
        with get_db_connection() as conn:
            # Fetch a fast pool of recent past messages (15 messages max)
            rows = conn.execute("""
                SELECT role, content, timestamp FROM messages 
                WHERE chat_id != ? 
                ORDER BY timestamp DESC 
                LIMIT 15
            """, (current_chat_id,)).fetchall()
            
            all_messages = []
            for row in rows:
                d_row = dict(row)
                d_row["content"] = decrypt_text(d_row["content"])
                all_messages.append(d_row)
                
            if not all_messages:
                return ""

            selected_messages = []
            
            # If query_prompt is provided, run TF-IDF cosine similarity ranking
            if query_prompt and len(all_messages) > 0:
                def tokenize(text):
                    return re.findall(r'\b\w{2,}\b', text.lower()) # words of length >= 2

                query_tokens = tokenize(query_prompt)
                if query_tokens:
                    query_tf = collections.Counter(query_tokens)
                    doc_tokens_list = [tokenize(msg["content"]) for msg in all_messages]
                    
                    # Gather unique words
                    all_words = set(query_tokens)
                    for tokens in doc_tokens_list:
                        all_words.update(tokens)
                        
                    doc_count = len(all_messages)
                    df = collections.Counter()
                    for tokens in doc_tokens_list:
                        for token in set(tokens):
                            df[token] += 1
                            
                    idf = {}
                    for word in all_words:
                        idf[word] = math.log((1 + doc_count) / (1 + df[word])) + 1
                        
                    # Query vector norm
                    query_vec = {}
                    query_norm = 0
                    for word, tf in query_tf.items():
                        val = tf * idf.get(word, 1.0)
                        query_vec[word] = val
                        query_norm += val * val
                    query_norm = math.sqrt(query_norm)
                    
                    scored_messages = []
                    if query_norm > 0:
                        for idx, msg in enumerate(all_messages):
                            tokens = doc_tokens_list[idx]
                            if not tokens:
                                continue
                            doc_tf = collections.Counter(tokens)
                            doc_norm = 0
                            doc_vec = {}
                            for word, tf in doc_tf.items():
                                val = tf * idf.get(word, 1.0)
                                doc_vec[word] = val
                                doc_norm += val * val
                            doc_norm = math.sqrt(doc_norm)
                            
                            if doc_norm == 0:
                                continue
                                
                            dot_product = sum(query_vec.get(word, 0) * doc_vec.get(word, 0) for word in query_tokens)
                            sim = dot_product / (query_norm * doc_norm)
                            
                            # Filter out system state tags or placeholders from scoring
                            if sim > 0.05:
                                scored_messages.append((msg, sim))
                                
                        # Sort by similarity descending
                        scored_messages.sort(key=lambda x: x[1], reverse=True)
                        # Take top N
                        top_matched = scored_messages[:limit]
                        # Keep only the messages
                        selected_messages = [item[0] for item in top_matched]
                        # Reverse so they are chronological in prompt
                        selected_messages = list(reversed(selected_messages))
            
            # Fallback to last N chronological if no similarity matches or query_prompt was not provided
            if not selected_messages:
                # Get the last chronological messages up to the limit
                selected_messages = list(reversed(all_messages[:limit]))
                
            memory_str = "\n[GLOBAL SEMANTIC MEMORY FROM PREVIOUS CONVERSATIONS]\n"
            for msg in selected_messages:
                role_label = "User" if msg['role'] == 'user' else "LAF"
                content_cleaned = re.sub(r'data:[^;]+;base64,[^\s]+', '[Base64 Attachment Data]', msg['content'])
                memory_str += f"- {role_label}: {content_cleaned}\n"
            memory_str += "[END OF GLOBAL MEMORY]\n"
            return memory_str
    except Exception as e:
        print(f"Memory retrieval failed: {e}")
        return ""

def search_ai_model_knowledge(query_prompt: str, limit: int = 4) -> str:
    """
    Searches the ingested trained AI models knowledge base and domain datasets 
    for relevant grounding context to maximize LAF AI response accuracy.
    """
    if not query_prompt:
        return ""
        
    try:
        query_words = [w.lower() for w in re.findall(r'\b\w{3,}\b', query_prompt)]
        if not query_words:
            return ""
            
        context_blocks = []
        with get_db_connection() as conn:
            # 1. Search Trained Datasets
            ds_rows = conn.execute("SELECT dataset_name, domain, content FROM trained_datasets").fetchall()
            matched_ds = []
            for row in ds_rows:
                score = sum(1 for w in query_words if w in row["dataset_name"].lower() or w in row["domain"].lower() or w in row["content"].lower())
                if score > 0:
                    matched_ds.append((dict(row), score))
                    
            matched_ds.sort(key=lambda x: x[1], reverse=True)
            for ds, s in matched_ds[:limit]:
                context_blocks.append(
                    f"[TRAINED DATASET ({ds['domain']})]: {ds['dataset_name']}\n{ds['content'].strip()}"
                )

            # 2. Search AI Model Knowledge Definitions if model/ai query
            if any(k in query_prompt.lower() for k in ["model", "ai", "llm", "gpt", "claude", "gemini", "llama", "ollama", "mistral", "qwen", "deepseek", "accuracy"]):
                mod_rows = conn.execute("SELECT model_name, provider, description, capabilities, trained_data_snippet FROM ai_model_knowledge").fetchall()
                matched_mods = []
                for row in mod_rows:
                    score = sum(1 for w in query_words if w in row["model_name"].lower() or w in row["provider"].lower() or w in row["description"].lower())
                    if score > 0:
                        matched_mods.append((dict(row), score))
                        
                matched_mods.sort(key=lambda x: x[1], reverse=True)
                for mod, s in matched_mods[:3]:
                    context_blocks.append(
                        f"[AI MODEL TRAINED SPECS]: {mod['model_name']} by {mod['provider']}\n"
                        f"Capabilities: {mod['capabilities']} | {mod['trained_data_snippet']}"
                    )

        if context_blocks:
            return "\n\n[COLLECTED TRAINED AI DATASETS & MODEL KNOWLEDGE]\n" + "\n---\n".join(context_blocks) + "\n[END OF TRAINED DATASET CONTEXT]\n"
        return ""
    except Exception as e:
        print(f"Error searching AI model knowledge: {e}")
        return ""

def get_model_data_stats() -> dict:
    """
    Returns statistics on ingested trained AI models and datasets in LAF storage.
    """
    try:
        with get_db_connection() as conn:
            model_count = conn.execute("SELECT COUNT(*) FROM ai_model_knowledge").fetchone()[0]
            dataset_count = conn.execute("SELECT COUNT(*) FROM trained_datasets").fetchone()[0]
            return {
                "total_ai_models_ingested": model_count,
                "total_trained_datasets": dataset_count,
                "status": "active",
                "accuracy_engine": "Multi-Model Ensembled Grounding & Semantic Search"
            }
    except Exception as e:
        return {"error": str(e)}

