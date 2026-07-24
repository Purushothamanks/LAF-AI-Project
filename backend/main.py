import os
import asyncio
import json
import urllib.parse
import httpx
import uuid
import math
import re
from gtts import gTTS
from PIL import Image, ImageDraw
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

# Dynamic import fallback for database package structure
try:
    import backend.database as database
except ImportError:
    import database

# Load local .env file if it exists
def load_dotenv():
    for path in [".env", "backend/.env", "../.env", "/app/.env", "/home/ubuntu/laf-project/.env", "/home/purushothaman/Videos/laf-project/.env"]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            os.environ[k.strip()] = v.strip().strip('"').strip("'")
            except Exception as e:
                print(f"Error loading env from {path}: {e}")

load_dotenv()

# High-Performance HTTP Connection Pool for Zero-Latency AI Engine
HTTP_CLIENT = httpx.AsyncClient(
    timeout=30.0,
    limits=httpx.Limits(max_keepalive_connections=50, max_connections=200),
    follow_redirects=True
)

IMAGE_MODEL = "juggernaut"

def explain_file_content(filename: str, content: str) -> str:
    ext = filename.split('.')[-1].lower() if '.' in filename else ''
    explanation = ""
    
    # Check if content is base64 encoded data URL
    if content.strip().startswith("data:"):
        try:
            header, encoded = content.split(",", 1)
            import base64
            decoded = base64.b64decode(encoded).decode("utf-8", errors="ignore")
            content = decoded
        except Exception:
            pass
            
    if ext == 'sql':
        tables = re.findall(r'create\s+table\s+(\w+)', content, re.IGNORECASE)
        inserts = re.findall(r'insert\s+into\s+(\w+)', content, re.IGNORECASE)
        selects = re.findall(r'select\s+.*?\s+from\s+(\w+)', content, re.IGNORECASE)
        
        explanation = (
            f"### 📋 SQL Script Insights:\n"
            f"This is an SQL database migration or query script.\n\n"
            f"**Database Schema Insights:**\n"
        )
        if tables:
            explanation += f"- **Tables Created**: {', '.join(set(tables))}\n"
        if inserts:
            explanation += f"- **Tables Populated**: {', '.join(set(inserts))}\n"
        if selects:
            explanation += f"- **Target Tables for Queries**: {', '.join(set(selects))}\n"
            
        explanation += "\n**Detailed SQL Script Explanation:**\n"
        explanation += "- **DDL Setup**: Creates relational structure and key constraints.\n"
        if inserts:
            explanation += "- **Data Ingestion**: Populates relational entities with initial sample records.\n"
        if selects or "update" in content.lower():
            explanation += "- **Operational Queries**: Runs filtering, modifications, or aggregations to retrieve schema stats.\n"
            
    elif ext == 'py':
        imports = re.findall(r'^\s*import\s+(\w+)|^\s*from\s+(\w+)\s+import', content, re.MULTILINE)
        functions = re.findall(r'^\s*def\s+(\w+)', content, re.MULTILINE)
        classes = re.findall(r'^\s*class\s+(\w+)', content, re.MULTILINE)
        
        explanation = (
            f"### 📋 Python Script Insights:\n"
            f"This is a Python script containing application code.\n\n"
            f"**Code Structure Insights:**\n"
        )
        import_names = [imp[0] or imp[1] for imp in imports if imp[0] or imp[1]]
        if import_names:
            explanation += f"- **Dependencies**: `{', '.join(set(import_names))}`\n"
        if classes:
            explanation += f"- **Classes Defined**: `{', '.join(classes)}`\n"
        if functions:
            explanation += f"- **Functions/Methods**: `{', '.join(functions)}`\n"
            
        explanation += "\n**Logic Summary:**\n"
        explanation += "The script defines structure and behavior using functions/modules. "
        if "if __name__ == '__main__':" in content:
            explanation += "It includes an entry point block for direct CLI execution."
            
    elif ext in ['js', 'ts', 'jsx', 'tsx']:
        functions = re.findall(r'function\s+(\w+)|const\s+(\w+)\s*=\s*\([^)]*\)\s*=>', content)
        func_list = [f[0] or f[1] for f in functions if f[0] or f[1]]
        explanation = (
            f"### 📋 JavaScript/TypeScript Module Insights:\n"
            f"This is a JavaScript/TypeScript source file.\n\n"
            f"**Functional Component/Module Insights:**\n"
        )
        if func_list:
            explanation += f"- **Key Exports/Handlers**: `{', '.join(func_list[:8])}`\n"
        explanation += "\nThis code handles component rendering, state reactivity, or frontend interactions."
        
    else:
        explanation = (
            f"### 📋 Document/Preview Analysis:\n"
            f"This is a document or raw data file.\n\n"
            f"**Content Preview:**\n"
            f"```txt\n"
            f"{content[:500]}...\n"
            f"```\n"
        )
        
    return explanation

app = FastAPI(title="LAF API", version="1.0.0")

# Enable CORS for local development when running Next.js dev server separately
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: https: http:; "
        "connect-src 'self' https: http: wss: ws:; "
        "font-src 'self' https: http: data:; "
        "img-src 'self' https: http: data: blob:; "
        "media-src 'self' https: http: data: blob:; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https: http:; "
        "style-src 'self' 'unsafe-inline' https: http:;"
    )
    if request.url.path == "/" or request.url.path.endswith(".html") or "." not in request.url.path.split("/")[-1]:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

@app.get("/sw.js")
@app.get("/service-worker.js")
async def unregister_sw():
    js_content = """
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
      .then(() => self.registration.unregister())
  );
});
self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request));
});
"""
    return Response(content=js_content, media_type="application/javascript")

# Initialize database and AI Model Knowledge Base on startup
@app.on_event("startup")
def startup_event():
    database.init_db()
    try:
        try:
            import backend.ingest_ai_models as ingest_ai_models
        except ImportError:
            import ingest_ai_models
        ingest_ai_models.ingest_all()
    except Exception as e:
        print(f"Startup AI model data ingestion warning: {e}")

# Request schemas
class ChatRequest(BaseModel):
    chat_id: str = ""
    prompt: str
    model: str = "laf-cloud-reasoning"
    device_id: str = "global"
    user_name: str = ""

class ChatCreateRequest(BaseModel):
    title: str = "New Conversation"
    device_id: str = "global"

# Chat management endpoints
@app.get("/api/version")
async def get_version_endpoint():
    return JSONResponse(content={"version": "1.2.6", "trained_model_data_ingested": True})

@app.get("/api/model_data/stats")
async def get_model_data_stats_endpoint():
    return JSONResponse(content=database.get_model_data_stats())

@app.post("/api/model_data/ingest")
async def trigger_model_data_ingest_endpoint():
    try:
        try:
            import backend.ingest_ai_models as ingest_ai_models
        except ImportError:
            import ingest_ai_models
        m_count, ds_count = ingest_ai_models.ingest_all()
        return JSONResponse(content={"status": "success", "models_ingested": m_count, "datasets_ingested": ds_count})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.get("/api/chats")
async def get_chats(device_id: str = "global"):
    return JSONResponse(content=database.get_all_chats(device_id))

@app.post("/api/chats")
async def create_chat_endpoint(request: ChatCreateRequest):
    chat_id = database.create_chat(request.title, request.device_id)
    return JSONResponse(content={"chat_id": chat_id, "title": request.title})

@app.get("/api/chats/{chat_id}/messages")
async def get_chat_messages(chat_id: str):
    return JSONResponse(content=database.get_messages_for_chat(chat_id))

@app.delete("/api/chats/{chat_id}")
async def delete_chat_endpoint(chat_id: str):
    database.delete_chat(chat_id)
    return JSONResponse(content={"status": "success"})

class EditMessageRequest(BaseModel):
    message_id: str
    new_content: str

@app.post("/api/messages/edit")
async def edit_message_endpoint(request: EditMessageRequest):
    database.edit_db_message(request.message_id, request.new_content)
    return JSONResponse(content={"status": "success"})

class TruncateRequest(BaseModel):
    chat_id: str
    timestamp: str

@app.post("/api/chats/truncate")
async def truncate_chat_endpoint(request: TruncateRequest):
    database.truncate_messages_after(request.chat_id, request.timestamp)
    return JSONResponse(content={"status": "success"})

class CodeExecutionRequest(BaseModel):
    language: str
    code: str
    stdin: str = ""

@app.post("/api/execute_code")
async def execute_code_endpoint(request: CodeExecutionRequest):
    import subprocess
    import tempfile
    
    language = request.language.lower()
    code = request.code
    stdin = request.stdin
    
    output = ""
    error = ""
    
    temp_dir = os.path.join(os.getcwd(), "scratch", "code_it_run")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Process sandbox resource limiter
    def limit_resources(lang: str = "python"):
        try:
            import resource
            # Limit CPU time to 5 seconds
            resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
            # Limit file size to 10MB
            resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
            
            # Skip virtual memory limit (RLIMIT_AS) for Java and JavaScript because of JVM/V8 VM memory pre-allocations
            if lang.lower() not in ["java", "javascript", "js"]:
                resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        except:
            pass

    # Auto-dependency installer helper
    def install_dependencies_for_code(lang: str, src: str, target_dir: str):
        if lang == "python":
            modules = set()
            for line in src.splitlines():
                line_clean = line.strip()
                if line_clean.startswith("#"):
                    continue
                match_import = re.match(r'^\s*import\s+([\w\s,.]+)', line_clean)
                if match_import:
                    parts = match_import.group(1).split(',')
                    for part in parts:
                        mod = part.split('as')[0].strip()
                        if mod:
                            modules.add(mod.split('.')[0])
                match_from = re.match(r'^\s*from\s+([\w.]+)\s+import', line_clean)
                if match_from:
                    modules.add(match_from.group(1).split('.')[0])
            
            package_mapping = {
                "pil": "Pillow",
                "bs4": "beautifulsoup4",
                "yaml": "PyYAML",
                "cv2": "opencv-python",
                "sklearn": "scikit-learn",
                "skimage": "scikit-image",
                "sqlite3": "",
                "json": "",
                "math": "",
                "re": "",
                "os": "",
                "sys": "",
                "time": "",
                "datetime": "",
                "collections": "",
                "random": "",
                "subprocess": "",
                "urllib": "",
            }
            
            for mod in modules:
                mod_lower = mod.lower()
                if mod_lower in package_mapping and package_mapping[mod_lower] == "":
                    continue
                package_name = package_mapping.get(mod_lower, mod)
                
                # Check if importable already
                check = subprocess.run(["python3", "-c", f"import {mod}"], capture_output=True)
                if check.returncode != 0:
                    print(f"Sandbox: Installing missing Python package: {package_name}...")
                    subprocess.run(["pip3", "install", package_name], capture_output=True, timeout=15.0)
                    
        elif lang in ["javascript", "js"]:
            packages = set()
            req_matches = re.findall(r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)', src)
            imp_matches = re.findall(r'from\s+[\'"]([^\'"]+)[\'"]', src)
            
            for pkg in req_matches + imp_matches:
                if not pkg.startswith('.') and not pkg.startswith('/') and pkg not in [
                    "fs", "path", "http", "https", "crypto", "os", "child_process", "util", "events", "stream", "dns", "net", "querystring", "url", "zlib"
                ]:
                    packages.add(pkg.split('/')[0])
            
            for pkg in packages:
                check = subprocess.run(["node", "-e", f"require('{pkg}')"], capture_output=True, cwd=target_dir)
                if check.returncode != 0:
                    print(f"Sandbox: Installing missing Node package: {pkg}...")
                    subprocess.run(["npm", "install", pkg, "--no-save"], capture_output=True, timeout=20.0, cwd=target_dir)

    def generate_sandbox_error_suggestion(lang: str, err: str) -> str:
        if not err:
            return ""
        lang = lang.lower()
        suggestion = "\n\n💡 [LAF SANDBOX DIAGNOSTIC SUGGESTION]:\n"
        if lang == "python":
            if "SyntaxError" in err:
                suggestion += "- Check your parentheses, colons, or quotes. Ensure blocks under 'if/def/for/while' are indented correctly."
            elif "NameError" in err:
                suggestion += "- You referenced a variable or function that hasn't been defined yet. Verify typing/spelling."
            elif "TypeError" in err:
                suggestion += "- An operation was applied to an incompatible data type. Ensure variables are converted correctly (e.g. using int(), str())."
            elif "ModuleNotFoundError" in err or "ImportError" in err:
                suggestion += "- The module you imported could not be resolved. Ensure it's not a typo, or check sandbox installation logs."
            elif "IndexError" in err:
                suggestion += "- You tried to access an item in a list using an index that is out of range. Check list boundaries."
            elif "KeyError" in err:
                suggestion += "- You tried to access a dictionary key that does not exist. Check key spelling."
            else:
                suggestion += "- Runtime Exception encountered. Double check your input arguments and logical blocks."
        elif lang in ["javascript", "js"]:
            if "SyntaxError" in err:
                suggestion += "- Check braces {}, parentheses (), semicolons, or mismatched quote marks."
            elif "ReferenceError" in err:
                suggestion += "- You used a variable name that doesn't exist or is out of scope. Check declarations (const/let/var)."
            elif "TypeError" in err:
                suggestion += "- You tried to run a method on an undefined object or access properties of null."
            else:
                suggestion += "- Node.js process failed. Review the callstack printout above."
        elif lang == "java":
            if "class, interface, or enum expected" in err or "reached end of file while parsing" in err:
                suggestion += "- Check your brace nesting levels. Verify every '{' is closed by a matching '}'."
            elif "cannot find symbol" in err:
                suggestion += "- A variable, class, or method you used is not declared. Ensure imports are complete."
            elif "NullPointerException" in err:
                suggestion += "- An object reference is null. Ensure you initialized objects with 'new' before calling their methods."
            elif "ArrayIndexOutOfBoundsException" in err:
                suggestion += "- The array index is outside the initialized boundaries of the array."
            else:
                suggestion += "- Java compilation or execution failed. Double check your class declaration matches the file structure."
        elif lang in ["c", "cpp", "c++"]:
            if "expected ';'" in err:
                suggestion += "- Semicolon ';' is missing at the end of a statement. Check line terminations."
            elif "undefined reference" in err:
                suggestion += "- A function or variable was declared but not defined. Check spelling and linking parameters."
            elif "segmentation fault" in err.lower():
                suggestion += "- Out-of-bounds memory access. Verify pointer initializations, array indexes, or dereferencing bounds."
            else:
                suggestion += "- C/C++ build failure. Verify headers, return values, and memory allocations."
        return suggestion

    try:
        # Pre-install dependencies
        install_dependencies_for_code(language, code, temp_dir)
        
        if language == "python":
            file_path = os.path.join(temp_dir, "script.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
            
            res = subprocess.run(
                ["python3", file_path],
                input=stdin,
                capture_output=True,
                text=True,
                preexec_fn=lambda: limit_resources(language),
                timeout=5.0
            )
            output = res.stdout
            error = res.stderr
            
        elif language == "java":
            class_match = re.search(r"public\s+class\s+(\w+)", code)
            class_name = class_match.group(1) if class_match else "Main"
            
            file_path = os.path.join(temp_dir, f"{class_name}.java")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
            
            compile_res = subprocess.run(
                ["javac", file_path],
                capture_output=True,
                text=True,
                cwd=temp_dir,
                timeout=5.0
            )
            
            if compile_res.returncode != 0:
                error = compile_res.stderr
            else:
                run_res = subprocess.run(
                    ["java", class_name],
                    input=stdin,
                    capture_output=True,
                    text=True,
                    preexec_fn=lambda: limit_resources(language),
                    cwd=temp_dir,
                    timeout=5.0
                )
                output = run_res.stdout
                error = run_res.stderr
                
        elif language in ["javascript", "js"]:
            file_path = os.path.join(temp_dir, "script.js")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
            local_node_path = os.path.join(temp_dir, "node_modules")
            env_vars = dict(os.environ, NODE_PATH=f"/app/node_modules:{local_node_path}")
            res = subprocess.run(
                ["node", file_path],
                input=stdin,
                capture_output=True,
                text=True,
                env=env_vars,
                preexec_fn=lambda: limit_resources(language),
                cwd=temp_dir,
                timeout=5.0
            )
            output = res.stdout
            error = res.stderr
            
        elif language == "c":
            file_path = os.path.join(temp_dir, "program.c")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
            
            compile_res = subprocess.run(
                ["gcc", "-o", "prog_c", file_path],
                capture_output=True,
                text=True,
                cwd=temp_dir,
                timeout=5.0
            )
            
            if compile_res.returncode != 0:
                error = compile_res.stderr
            else:
                run_res = subprocess.run(
                    ["./prog_c"],
                    input=stdin,
                    capture_output=True,
                    text=True,
                    preexec_fn=lambda: limit_resources(language),
                    cwd=temp_dir,
                    timeout=5.0
                )
                output = run_res.stdout
                error = run_res.stderr
                
        elif language in ["cpp", "c++"]:
            file_path = os.path.join(temp_dir, "program.cpp")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
            
            compile_res = subprocess.run(
                ["g++", "-o", "prog_cpp", file_path],
                capture_output=True,
                text=True,
                cwd=temp_dir,
                timeout=5.0
            )
            
            if compile_res.returncode != 0:
                error = compile_res.stderr
            else:
                run_res = subprocess.run(
                    ["./prog_cpp"],
                    input=stdin,
                    capture_output=True,
                    text=True,
                    preexec_fn=lambda: limit_resources(language),
                    cwd=temp_dir,
                    timeout=5.0
                )
                output = run_res.stdout
                error = run_res.stderr
                
        else:
            return JSONResponse(status_code=400, content={"error": f"Unsupported language: {language}"})
            
    except subprocess.TimeoutExpired:
        error = "Execution timed out (Limit: 5 seconds)"
    except Exception as e:
        error = f"Execution failed: {str(e)}"
    finally:
        # Cleanup files
        try:
            for f in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, f))
        except:
            pass
            
    if error:
        error += generate_sandbox_error_suggestion(language, error)
        
    return JSONResponse(content={"output": output, "error": error})

class CodeFixRequest(BaseModel):
    language: str
    code: str
    errors: list[str] = []
    model: str = "laf-cloud-reasoning"

@app.post("/api/fix_code")
async def fix_code_endpoint(request: CodeFixRequest):
    language = request.language
    code = request.code
    errors_list = [e for e in request.errors if e and e.strip()]
    errors_str = "\n".join(errors_list) if errors_list else "No runtime console errors found. Please review the code for improvements."
    
    system_prompt = (
        "You are LAF Code Assistant, an expert programming tutor and debugger.\n"
        "Analyze the provided code and runtime console logs/errors. Explain the root cause of the error and how to fix it.\n"
        "Then provide the FULL corrected code in a standard markdown code block.\n"
        "Your code correction MUST be highly accurate. Follow these strict guidelines:\n"
        "1. Mentally trace the code's execution line-by-line to ensure absolute correctness.\n"
        "2. Ensure all required imports/libraries are included.\n"
        "3. Fix all compiler/interpreter syntax errors, type mismatches, and scope bugs.\n"
        "4. Always return the COMPLETE file/script, not just a snippet, so the user can copy-paste it directly.\n\n"
        "You MUST structure your response strictly in the following format:\n\n"
        "[EXPLANATION]\n"
        "Explain what is wrong and how to fix it here (using markdown and emojis).\n\n"
        "[CODE]\n"
        f"```{language}\n"
        "// Put the full corrected code script here\n"
        "```"
    )
    
    user_prompt = (
        f"Language: {language}\n\n"
        f"Source Code:\n```\n{code}\n```\n\n"
        f"Console Errors/Logs:\n```\n{errors_str}\n```"
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    explanation = ""
    corrected_code = ""
    result_text = ""
    
    # Try Cloud first if requested
    if request.model == "laf-cloud-reasoning":
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        gemini_key = gemini_key.strip().strip('"').strip("'")
        
        if gemini_key and gemini_key.startswith("AIzaSy") and len(gemini_key) >= 30:
            gemini_contents, gemini_system = convert_to_gemini_format(messages, system_prompt)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            payload = {
                "contents": gemini_contents,
                "systemInstruction": gemini_system,
                "generationConfig": {
                    "temperature": 0.3
                }
            }
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                result_text = parts[0].get("text", "").strip()
            except Exception as e:
                print(f"Gemini API code fix failed: {e}, falling back to Pollinations.")
                
        if not result_text:
            url = "https://text.pollinations.ai/"
            payload = {
                "messages": messages,
                "model": "openai"
            }
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        result_text = resp.text.strip()
            except Exception as e:
                print(f"Cloud code fix fallback failed: {e}")
            
    # If cloud failed or local was chosen, run local Ollama
    if not result_text:
        url = "http://localhost:11434/api/chat"
        payload = {
            "model": "llama3.2:latest",
            "messages": messages,
            "stream": False
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    result = resp.json()
                    result_text = result.get("message", {}).get("content", "").strip()
        except Exception as e:
            explanation = f"Failed to connect to local LAF service. Error: {str(e)}"
            corrected_code = code
            
    if result_text:
        # Parse markdown response structure using [CODE] split first to avoid matching inline code blocks in explanation
        parts = re.split(r"\[CODE\]", result_text, flags=re.IGNORECASE)
        if len(parts) > 1:
            explanation = parts[0].replace("[EXPLANATION]", "").replace("[explanation]", "").strip()
            code_part = parts[1]
            code_block_match = re.search(r"```(?:\w+)?\s*\r?\n?([\s\S]*?)```", code_part)
            if code_block_match:
                corrected_code = code_block_match.group(1).strip()
            else:
                # If no markdown backticks, fallback to raw text after [CODE]
                cleaned_code_part = code_part.strip()
                if cleaned_code_part.startswith("```"):
                    lines = cleaned_code_part.splitlines()
                    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
                        cleaned_code_part = "\n".join(lines[1:-1]).strip()
                corrected_code = cleaned_code_part
        else:
            # Fallback if no [CODE] tag is present
            code_block_match = re.search(r"```(?:\w+)?\s*\r?\n?([\s\S]*?)```", result_text)
            if code_block_match:
                corrected_code = code_block_match.group(1).strip()
                parts = result_text.split("```")
                explanation = parts[0].replace("[EXPLANATION]", "").replace("[explanation]", "").strip()
            else:
                # Check if LLM returned JSON by mistake
                if "{" in result_text and "corrected_code" in result_text:
                    try:
                        clean_text = result_text
                        if clean_text.startswith("```json"):
                            clean_text = clean_text[7:]
                        elif clean_text.startswith("```"):
                            clean_text = clean_text[3:]
                        if clean_text.endswith("```"):
                            clean_text = clean_text[:-3]
                        clean_text = clean_text.strip()
                        data = json.loads(clean_text)
                        explanation = data.get("explanation", "").strip()
                        corrected_code = data.get("corrected_code", "").strip()
                    except Exception:
                        explanation = result_text.replace("[EXPLANATION]", "").replace("[CODE]", "").strip()
                        corrected_code = code
                else:
                    # Default fallback
                    corrected_code = code
                    explanation = result_text.replace("[EXPLANATION]", "").replace("[CODE]", "").strip()
                
    if not corrected_code:
        corrected_code = code
    if not explanation:
        explanation = "LAF could not generate a response. Please check your network connection and try again."
        
    return JSONResponse(content={"explanation": explanation, "corrected_code": corrected_code})

# Helper to upload base64 images to tmpfiles.org or construct public server URL fallback
async def process_and_upload_image(content_preview: str, filename: str, base_url: str = None) -> str:
    """
    Decodes an attached base64 image, saves it locally inside the static output directory,
    uploads it to tmpfiles.org for public retrieval, and falls back to our own public server URL.
    """
    import base64
    try:
        if not content_preview.strip().startswith("data:"):
            return None
        header, encoded = content_preview.strip().split(",", 1)
        raw_data = base64.b64decode(encoded)
        
        file_ext = filename.split('.')[-1] if '.' in filename else 'jpg'
        if file_ext.lower() not in ['png', 'jpg', 'jpeg', 'webp', 'gif']:
            file_ext = 'jpg'
            
        temp_filename = f"temp_upload_{uuid.uuid4().hex[:8]}.{file_ext}"
        os.makedirs(STATIC_DIR, exist_ok=True)
        temp_filepath = os.path.join(STATIC_DIR, temp_filename)
        
        with open(temp_filepath, "wb") as f:
            f.write(raw_data)
            
        # 1. Attempt upload to tmpfiles.org
        try:
            upload_url = "https://tmpfiles.org/api/v1/upload"
            async with httpx.AsyncClient(timeout=15.0) as client:
                with open(temp_filepath, "rb") as file_to_upload:
                    files = {"file": (filename, file_to_upload, f"image/{file_ext}")}
                    response = await client.post(upload_url, files=files)
                if response.status_code == 200:
                    resp_json = response.json()
                    if resp_json.get("status") == "success":
                        file_url = resp_json["data"]["url"]
                        direct_url = file_url.replace("https://tmpfiles.org/", "https://tmpfiles.org/dl/")
                        return direct_url
        except Exception as upload_err:
            print(f"tmpfiles upload failed: {upload_err}")
            
        # 2. Fallback to our own server base_url if it is a public URL
        if base_url:
            is_local = any(l in base_url for l in ["localhost", "127.0.0.1", "0.0.0.0", "192.168.", "10."])
            if not is_local:
                return f"{base_url}/{temp_filename}"
                
    except Exception as e:
        print(f"Error in process_and_upload_image: {e}")
    return None

# Open-Source-Style Generative Video Engine (MP4)
async def generate_dynamic_video(text: str, duration_sec: int, filename: str):
    """
    Generates a custom open-source-style video (MP4) based on the user's prompt by
    fetching concurrent keyframes from Pollinations.ai (using the Juggernaut model),
    interpolating (cross-fading/blending) between them dynamically,
    applying camera panning, zooming, and rotation motion curves,
    adding volumetric particle/lighting filters, and compiling using ffmpeg.
    Supports durations of 10s, 30s, or 60s at 12 fps.
    """
    import httpx
    import random
    import shutil
    import subprocess
    from io import BytesIO
    
    # 1. Determine parameters based on duration
    fps = 12
    total_frames = duration_sec * fps
    
    # Try to generate a real video using Hugging Face Space (T2V-Turbo-V2)
    keyframe_images = []
    hf_success = False
    temp_extract_dir = None
    
    try:
        from gradio_client import Client
        
        # Run Gradio Client prediction in a separate thread
        def run_gradio():
            import os
            hf_token = os.environ.get("HF_TOKEN")
            client = Client("TIGER-Lab/T2V-Turbo-V2", hf_token=hf_token)
            return client.predict(
                prompt=f"{text}, photorealistic, highly detailed, 8k resolution, cinematic motion",
                guidance_scale=7.5,
                percentage=0.5,
                num_inference_steps=16,
                num_frames=16,
                seed=random.randint(1, 99999999),
                randomize_seed=True,
                param_dtype="bf16",
                api_name="/predict"
            )
            
        print("Attempting real generative video creation via TIGER-Lab/T2V-Turbo-V2 Space...")
        res = await asyncio.to_thread(run_gradio)
        video_path = res[0]['video']
        
        if video_path and os.path.exists(video_path):
            print(f"Space video generated successfully at: {video_path}")
            # Create a temporary directory to extract frames
            temp_extract_id = uuid.uuid4().hex[:8]
            temp_extract_dir = os.path.join(os.getcwd(), "scratch", f"space_extract_{temp_extract_id}")
            os.makedirs(temp_extract_dir, exist_ok=True)
            
            # Extract frames using ffmpeg
            extract_cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                os.path.join(temp_extract_dir, "frame_%04d.png")
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *extract_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            await proc.communicate()
            
            if proc.returncode == 0:
                # Load extracted frames into PIL images
                frame_files = sorted(os.listdir(temp_extract_dir))
                for f_file in frame_files:
                    if f_file.endswith(".png"):
                        f_path = os.path.join(temp_extract_dir, f_file)
                        img = Image.open(f_path)
                        keyframe_images.append(img.resize((512, 512), Image.Resampling.LANCZOS))
                
                if len(keyframe_images) > 0:
                    hf_success = True
                    print(f"Successfully loaded {len(keyframe_images)} real generative video frames!")
    except Exception as e:
        print(f"Hugging Face Space video generation failed or was rate-limited: {e}")
        print("Falling back to local keyframe interpolation generator...")
        
    finally:
        # Clean up the extracted frames temporary directory
        if temp_extract_dir and os.path.exists(temp_extract_dir):
            try:
                shutil.rmtree(temp_extract_dir)
            except Exception as e:
                print(f"Failed to cleanup space extract directory: {e}")

    # Fallback to Juggernaut keyframe interpolation if Hugging Face failed
    if not hf_success:
        keyframe_images = []
        # Select keyframe counts (3 for 10s, 6 for 30s, 11 for 60s)
        if duration_sec == 10:
            num_keyframes = 3
        elif duration_sec == 30:
            num_keyframes = 6
        else: # 60s
            num_keyframes = 11
            
        # Construct prompts for each keyframe to show camera pan/motion or transition
        prompts = []
        motion_descriptors = [
            "wide shot, cinematic composition",
            "dynamic camera panning right",
            "medium shot, tracking camera movement",
            "close-up shot, shifting focus",
            "alternative high-angle perspective",
            "slow zoom-in, volumetric lighting",
            "cinematic slide transition",
            "dolly zoom effect, detailed perspective",
            "low-angle tracking shot",
            "rotating camera movement, dramatic atmosphere",
            "final epic wide angle, high resolution"
        ]
        
        for i in range(num_keyframes):
            desc = motion_descriptors[i % len(motion_descriptors)]
            prompts.append(f"{text}, {desc}, 8k resolution, highly detailed, photorealistic")
            
        # Generate random seeds for each keyframe to ensure variance
        seeds = [random.randint(1, 99999999) for _ in range(num_keyframes)]
        
        # Download keyframes concurrently using asyncio.gather
        async def fetch_keyframe(client, url, index):
            try:
                r = await client.get(url, timeout=20.0)
                if r.status_code == 200:
                    img = Image.open(BytesIO(r.content))
                    return index, img.resize((512, 512), Image.Resampling.LANCZOS)
            except Exception as e:
                print(f"Failed to fetch keyframe {index} for video: {e}")
            return index, None

        keyframe_images_temp = [None] * num_keyframes
        async with httpx.AsyncClient() as client:
            tasks = []
            for i, p in enumerate(prompts):
                encoded = urllib.parse.quote(p)
                url = f"https://image.pollinations.ai/prompt/{encoded}?width=512&height=512&nologo=true&seed={seeds[i]}&model={IMAGE_MODEL}"
                tasks.append(fetch_keyframe(client, url, i))
                
            results = await asyncio.gather(*tasks)
            for idx, img in results:
                keyframe_images_temp[idx] = img

        # Fallback for failed keyframes: copy adjacent ones or create a fallback
        fallback_color = (10, 10, 15)
        for i in range(num_keyframes):
            if keyframe_images_temp[i] is None:
                if i > 0 and keyframe_images_temp[i-1] is not None:
                    keyframe_images_temp[i] = keyframe_images_temp[i-1].copy()
                elif i < num_keyframes - 1 and keyframe_images_temp[i+1] is not None:
                    keyframe_images_temp[i] = keyframe_images_temp[i+1].copy()
                else:
                    keyframe_images_temp[i] = Image.new("RGB", (512, 512), color=fallback_color)
            keyframe_images.append(keyframe_images_temp[i])

    # 3. Set up temporary directory for frame compiling
    temp_id = uuid.uuid4().hex[:8]
    temp_dir = os.path.join(os.getcwd(), "scratch", f"video_compile_{temp_id}")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Compute the keyframe interval lengths
    num_keyframes_loaded = len(keyframe_images)
    interval_frames = total_frames // (num_keyframes_loaded - 1)
    
    # 4. Generate individual frames by blending keyframes and applying animations
    for t in range(total_frames):
        # Determine current interval
        interval_idx = min(t // interval_frames, num_keyframes_loaded - 2)
        t_start = interval_idx * interval_frames
        t_end = (interval_idx + 1) * interval_frames
        if interval_idx == num_keyframes_loaded - 2:
            t_end = total_frames
            
        fraction = (t - t_start) / (t_end - t_start)
        # Cosine interpolation for smooth transitions
        alpha = (1.0 - math.cos(fraction * math.pi)) / 2.0
        
        # Blend the two keyframes
        img_blend = Image.blend(keyframe_images[interval_idx], keyframe_images[interval_idx + 1], alpha)
        
        # Apply continuous camera panning/zooming over time
        zoom = 1.0 + 0.12 * math.sin(t * math.pi / (total_frames / 4))
        new_size = int(512 * zoom)
        img_zoomed = img_blend.resize((new_size, new_size), Image.Resampling.LANCZOS)
        
        # Pan offset shifts based on trigonometric curves
        dx = int(18 * math.sin(t * math.pi / (total_frames / 2)))
        dy = int(12 * math.cos(t * math.pi / (total_frames / 2)))
        
        # Center-crop back to 512x512 with offsets
        left = (new_size - 512) // 2 + dx
        top = (new_size - 512) // 2 + dy
        left = max(0, min(left, new_size - 512))
        top = max(0, min(top, new_size - 512))
        
        frame = img_zoomed.crop((left, top, left + 512, top + 512))
        
        # 4. Draw camera recording UI overlays and cyber particle filters
        draw = ImageDraw.Draw(frame)
        
        # Floating cyber particles
        for p in range(15):
            px = int((p * 35 + t * (p + 2)) % 512)
            py = int((p * 65 - t * (15 - p)) % 512)
            size = (p % 3) + 1
            color = (129, 140, 248) if p % 2 == 0 else (168, 85, 247)
            draw.ellipse([px - size, py - size, px + size, py + size], fill=color)
            
        # Draw camera viewfinder corners
        padding = 24
        line_len = 18
        # Top-left
        draw.line([(padding, padding), (padding + line_len, padding)], fill=(255, 255, 255), width=2)
        draw.line([(padding, padding), (padding, padding + line_len)], fill=(255, 255, 255), width=2)
        # Top-right
        draw.line([(512 - padding, padding), (512 - padding - line_len, padding)], fill=(255, 255, 255), width=2)
        draw.line([(512 - padding, padding), (512 - padding, padding + line_len)], fill=(255, 255, 255), width=2)
        # Bottom-left
        draw.line([(padding, 512 - padding), (padding + line_len, 512 - padding)], fill=(255, 255, 255), width=2)
        draw.line([(padding, 512 - padding), (padding, 512 - padding - line_len)], fill=(255, 255, 255), width=2)
        # Bottom-right
        draw.line([(512 - padding, 512 - padding), (512 - padding - line_len, 512 - padding)], fill=(255, 255, 255), width=2)
        draw.line([(512 - padding, 512 - padding), (512 - padding, 512 - padding - line_len)], fill=(255, 255, 255), width=2)
        
        # Red REC indicator blinking (blinks twice per second at 12 fps)
        if t % 12 < 6:
            draw.ellipse([35, 35, 45, 45], fill=(239, 68, 68))
            try:
                draw.text((52, 33), "REC", fill=(255, 255, 255))
            except Exception:
                pass
                
        # Modern text watermark
        try:
            draw.text((padding, 512 - padding - 22), "LAF GENERATIVE ENGINE", fill=(255, 255, 255))
            draw.text((512 - padding - 160, 512 - padding - 22), f"PROMPT: {text[:15].upper()}...", fill=(200, 200, 200))
        except Exception:
            pass
            
        # Save frame
        frame_path = os.path.join(temp_dir, f"frame_{t:04d}.png")
        frame.save(frame_path, "PNG")

    # 5. Compile the images into a web-compatible H.264 MP4 video using ffmpeg
    output_filepath = os.path.join(STATIC_DIR, filename)
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", os.path.join(temp_dir, "frame_%04d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-level", "4.0",
        "-crf", "22",
        "-movflags", "+faststart",
        output_filepath
    ]
    
    try:
        # Run ffmpeg subprocess asynchronously using create_subprocess_exec (fully non-blocking)
        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f"ffmpeg error stdout: {stdout.decode()}")
            print(f"ffmpeg error stderr: {stderr.decode()}")
            raise Exception("ffmpeg failed to compile video")
    finally:
        # 6. Cleanup temp directory
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Failed to cleanup video temp directory: {e}")

# Pure-Python DuckDuckGo HTML Search Scraper
async def search_duckduckgo(query: str):
    """
    Scrapes html.duckduckgo.com for top 4 search results. Returns list of dictionaries.
    """
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    params = {"q": query}
    
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code != 200:
                return []
            
            html = response.text
            results = []
            
            # Split search result blocks
            blocks = html.split('<div class="result results_links results_links_deep')
            for block in blocks[1:]:  # Skip the page header
                # Extract link/URL
                link_match = re.search(r'class="result__a" href="([^"]+)"', block)
                # Extract title
                title_match = re.search(r'class="result__a"[^>]*>([^<]+)</a>', block)
                # Extract snippet
                snippet_match = re.search(r'class="result__snippet"[^>]*>([^<]+)</a>', block)
                
                if link_match and title_match:
                    link = link_match.group(1)
                    if link.startswith("//"):
                        link = "https:" + link
                        
                    # Decode proxied DDG links
                    if "/l/?" in link or "/y.js?" in link:
                        parsed = urllib.parse.urlparse(link)
                        qs = urllib.parse.parse_qs(parsed.query)
                        if "uddg" in qs:
                            link = qs["uddg"][0]
                            
                    title = title_match.group(1).strip()
                    title = re.sub(r'<[^>]+>', '', title)
                    
                    snippet = snippet_match.group(1).strip() if snippet_match else ""
                    snippet = re.sub(r'<[^>]+>', '', snippet)
                    
                    results.append({
                        "title": title,
                        "link": link,
                        "snippet": snippet
                    })
                    
                    if len(results) >= 4:
                        break
            return results
    except Exception as e:
        print("Search scrape error:", e)
        return []

# Local conversational fallback handler
MOCK_RESPONSES = {
    "tui": """### Terminal User Interface (TUI) Mode

LAF features a built-in terminal mode designed for power users and command line workflows. 

**To launch TUI mode:**
```bash
laf --tui
```

**Key Features of TUI:**
- **Zero server dependencies**: Runs entirely in your shell process.
- **Fast input loop**: Quick interactive conversation directly in standard I/O.
- **Lightweight memory**: Keeps conversation context active during the session.""",
    "gui": "The Web GUI mode is the default mode of LAF. It runs a FastAPI backend to host a Next.js client built with Zustand and Tailwind CSS. It automatically opens your browser when you run `laf`.",
    "code": """Here is a Python function to query a streaming HTTP endpoint chunk-by-chunk:

```python
import requests

def stream_response(url, payload):
    headers = {"Content-Type": "application/json"}
    with requests.post(url, json=payload, headers=headers, stream=True) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=1024, decode_unicode=True):
            if chunk:
                print(chunk, end="", flush=True)
```""",
}

def is_offensive_or_developer_insult(prompt: str) -> tuple[bool, str]:
    prompt_lower = prompt.lower().strip()
    # Remove punctuation
    prompt_clean = re.sub(r'[^\w\s]', '', prompt_lower).strip()
    words = prompt_clean.split()
def is_offensive_or_developer_insult(prompt: str) -> tuple[bool, str]:
    prompt_lower = prompt.lower().strip()
    prompt_clean = re.sub(r'[^\w\s]', '', prompt_lower).strip()
    words = prompt_clean.split()
    
    # 1. Check for explicit developer insult phrases
    insult_phrases = [
        "developer is waste", "developer is bad", "developer is trash", "developer is useless",
        "creator is waste", "creator is bad", "creator is trash", "creator is useless",
        "purushothaman is waste", "purushothaman is bad", "purushothaman is trash", "purushothaman is useless",
        "developer is a waste", "creator is a waste", "purushothaman is a waste",
        "you are waste", "you are trash", "you are useless", "you suck", "developer sucks",
        "your developer sucks", "purushothaman sucks", "developer is stupid", "purushothaman is stupid"
    ]
    
    has_insult_phrase = any(phrase in prompt_clean for phrase in insult_phrases)
    
    # 2. Check for actual severe vulgarity/profanity directed at AI/developer
    severe_bad_words = [
        "fuck", "shit", "asshole", "bitch", "bastard", "dick", "cunt", "motherfucker", "wanker", "dumbass"
    ]
    has_bad_word = any(w in words for w in severe_bad_words)
    
    if has_insult_phrase or (has_bad_word and any(k in prompt_clean for k in ["you", "developer", "purushothaman", "laf", "bot", "ai"])):
        return True, "I understand you might be feeling frustrated, but I kindly ask that we keep our conversation respectful. My developer, designed me to be helpful, polite, and constructive. Please let me know how I can assist you further! 😊✨"
        
    return False, ""

def get_intelligent_response(prompt: str, user_name: str = "") -> str:
    prompt_lower = prompt.lower().strip()
    prompt_clean = re.sub(r'[^\w\s]', '', prompt_lower).strip()
    words = set(prompt_clean.split())
    
    # 0. User name inquiry check
    if any(x in prompt_clean for x in ["what is my name", "whats my name", "what my name", "who am i", "who am 1", "do you know my name"]):
        if user_name and user_name.strip():
            return f"Your name is **{user_name.strip()}**! 😊✨"
        else:
            return "You haven't set your name yet! Click 'Edit' in the user profile panel to set your name. 😊✨"

    # 0b. Greetings check (simple 'hi', 'hello', etc.)
    if any(greet in words for greet in ["hi", "hello", "hey", "hola", "greetings"]) and len(words) <= 3:
        if user_name and user_name.strip():
            return f"Hello **{user_name.strip()}**! I am LAF AI, developed by Purushothaman. How can I assist you today? 😊✨"
        return "Hello! I am LAF AI, developed by Purushothaman. How can I assist you today? 😊✨"

    # 1. Network / Architecture Inquiry Check (e.g. "is laf big network?", deep requests)
    if any(x in prompt_lower for x in ["is laf big network", "is laf a big network", "laf network", "laf big network", "in deep"]):
        return (
            "Yes, LAF AI operates on a large-scale, highly distributed network architecture designed to deliver real-time, high-precision reasoning and software generation.\n\n"
            "Here is a breakdown of what makes LAF a massive and robust network system:\n\n"
            "---\n\n"
            "1. Multi-Model Ensemble Network (100+ AI Models)\n"
            "LAF is not a single isolated model. It is powered by an ensemble intelligence network built on top of Google's Gemini architecture and synthesized with trained knowledge from 100+ frontier AI models (including OpenAI GPT series, Anthropic Claude, DeepSeek reasoning engines, and Qwen Coder). This ensembled network allows LAF to route and process queries across specialized domains like deep mathematics, full-stack coding, and high-level system architecture.\n\n"
            "---\n\n"
            "2. High-Bandwidth Cloud Infrastructure\n"
            "Because LAF handles complex tasks—such as AST-level code generation, multi-step chain-of-thought logic, and real-time contextual analysis—it relies on high-speed, enterprise-grade cloud compute networks. This infrastructure ensures:\n"
            "• Sub-second response speeds for code and text generation.\n"
            "• Scalable parallel processing to analyze large dynamic codebases without latency degradation.\n"
            "• Continuous uptime and reliable API socket streaming between the client application and the core reasoning engines.\n\n"
            "---\n\n"
            "3. Active Network Connectivity\n"
            "LAF requires an active internet/network connection to interact with its ensembled intelligence modules, perform real-time processing, and execute deep reasoning pipelines. If your device experiences a local connection drop or packet loss, LAF's interface will prompt you to verify your network connection so it can resume communication with the core engine seamlessly."
        )

    # 1b. Brief LAF summary check
    if any(x in prompt_lower for x in ["breaf content", "brief content", "summary of laf", "laf summary"]):
        return "Summary  In short, LAF AI operates as a powerful, cloud-connected intelligence network engineered by Purushothaman—combining the power of the Gemini brain with multi-model cloud orchestration to bring \"Look at The Future\" capabilities directly to your workflow."

    # 1b. Offensive or developer insult check
    is_offensive, polite_response = is_offensive_or_developer_insult(prompt)
    if is_offensive:
        return polite_response

    # 2. Developer identity claim check (handles typos & shorthand like 'u r', 'ur', 'drvrloper', 'am y u')
    dev_claim_phrases = [
        "i am purushothaman", "im purushothaman", "i am the developer", "im the developer",
        "i am developer", "im developer", "i am creator", "im creator", "i am owner", "im owner",
        "i am u r developer", "i am ur developer", "im u r developer", "im ur developer",
        "am y u drvrloper", "am u r developer", "i am u developer", "im u developer",
        "am i your developer", "i developed you", "i created you", "i made you"
    ]
    is_claiming_dev = any(phrase in prompt_clean for phrase in dev_claim_phrases) or (
        ("developer" in prompt_clean or "drvrloper" in prompt_clean or "dev" in prompt_clean) and 
        any(k in prompt_clean for k in ["i am", "im", "am", "your", "ur", "u r", "y u"])
    )
    
    if is_claiming_dev:
        return "Oh really ! i see , let verify . 🤔🕵️‍♂️✨\n\nTell Me Your GF Name ?"

    # 3. B. Developer query check
    if any(x in prompt_clean for x in ["developer of laf", "who developed laf", "who created laf", "creator of laf", "developed by", "created by", "who is purushothaman", "who created you", "who developed you", "who is developer", "developer name", "developer linkedin"]):
        return "You can learn more about my developer on LinkedIn: [LinkedIn Profile](https://www.linkedin.com/in/purushothaman-k-s-158900282) 🚀✨"
        
    # 4. Identity inquiry check (asking who it is, or if it is Gemini)
    if any(x in prompt_clean for x in ["who are you", "who r you", "who r u", "who are u", "your name", "whats your name", "what is your name", "are you gemini", "r u gemini", "are u gemini", "r you gemini", "is this gemini"]):
        return "I am LAF AI, an advanced conversational assistant developed by Purushothaman. How can I help you today? 😊✨"

    # 4b. Meaning & Full Form of LAF check
    if any(x in prompt_clean for x in ["full form of laf", "meaning of laf", "what is laf", "what is mean by laf", "what does laf mean", "what does laf stand for", "laf full form", "laf meaning"]):
        return (
            "### 💡 Meaning & Full Form of **LAF**\n\n"
            "In this platform, **LAF** stands for **Language & Agent Framework** (also representing **Learn, Adapt & Formulate**).\n\n"
            "**Primary Definitions of LAF:**\n"
            "1. **LAF AI Platform**: Developed by **Purushothaman**, LAF AI is an intelligent conversational AI system, multi-modal media generator, and live code execution sandbox.\n"
            "2. **Look and Feel (UI/UX)**: In software design & frontend development, **LAF** stands for *Look and Feel*, referring to the visual aesthetics, layout style, and user interaction design.\n"
            "3. **Lock-And-Free**: In high-performance concurrent computing, LAF refers to lock-free architecture & data structures.\n\n"
            "How can I help you today? 😊✨"
        )
        
    # 5. Work process / workflow / general info check
    if any(x in prompt_lower for x in ["work process", "work-process", "workflow", "work-flow", "how you work", "how it works", "how does it work", "how do you work", "explain laf", "tell me about laf"]):
        return (
            "### 🤖 LAF AI Architecture & Workflow Overview\n\n"
            "LAF AI is an advanced AI assistant and sandbox runner developed by **Purushothaman**:\n\n"
            "1. **Core Processing Engine**: Uses FastAPI backend (`main.py`) paired with a modern React + Vite frontend.\n"
            "2. **Code Sandbox Execution**: Executes Python, JavaScript, C/C++, and Java code safely with real-time diagnostic output.\n"
            "3. **Persistent Memory**: Uses SQLite (`laf_storage.db`) with Fernet AES-128 end-to-end encryption.\n"
            "4. **Multimodal Media Synthesis**: Synthesizes custom images, TTS audio, and video clips upon request.\n"
            "5. **Real-time Web Search & Retrieval**: Performs live web grounding for up-to-date query answers.\n"
        )
        
    # 6. Code / Programming Request Detection
    if any(k in prompt_clean for k in ["code", "python", "javascript", "react", "html", "css", "c", "cpp", "java", "sql", "docker", "bash", "script", "function", "write a program", "how to write", "example of"]):
        if "python" in prompt_clean or "py" in words:
            return (
                "Here is a complete, production-ready Python example:\n\n"
                "```python\n"
                "# Python Data Processing & Helper Example\n"
                "def process_data(items: list[dict]) -> dict:\n"
                "    \"\"\"Filters and transforms data items into a summary report.\"\"\"\n"
                "    processed = [item for item in items if item.get('active', True)]\n"
                "    total_val = sum(item.get('value', 0) for item in processed)\n"
                "    return {\n"
                "        'count': len(processed),\n"
                "        'total_value': total_val,\n"
                "        'status': 'success'\n"
                "    }\n\n"
                "if __name__ == '__main__':\n"
                "    sample = [{'id': 1, 'value': 100}, {'id': 2, 'value': 250, 'active': False}]\n"
                "    result = process_data(sample)\n"
                "    print('Processed Summary:', result)\n"
                "```\n\n"
                "**Key Features:**\n"
                "- Type hints for input parameter and return value validation.\n"
                "- List comprehension filtering active entries.\n"
                "- Main execution guard (`if __name__ == '__main__':`) for standalone script running."
            )
        elif any(k in prompt_clean for k in ["javascript", "js", "react"]):
            return (
                "Here is a modern JavaScript / React component snippet:\n\n"
                "```javascript\n"
                "import React, { useState } from 'react';\n\n"
                "export default function DataWidget({ title = 'LAF Control Widget' }) {\n"
                "  const [count, setCount] = useState(0);\n\n"
                "  return (\n"
                "    <div style={{ padding: '16px', background: '#111522', borderRadius: '8px', color: '#fff' }}>\n"
                "      <h3>{title}</h3>\n"
                "      <p>Active Count: <strong>{count}</strong></p>\n"
                "      <button \n"
                "        onClick={() => setCount(c => c + 1)}\n"
                "        style={{ padding: '8px 16px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}\n"
                "      >\n"
                "        Increment\n"
                "      </button>\n"
                "    </div>\n"
                "  );\n"
                "}\n"
                "```\n\n"
                "**Key Features:**\n"
                "- Uses React state hook (`useState`) for reactive UI updates.\n"
                "- Clean modern styling and accessible event handler."
            )
        elif "sql" in prompt_clean:
            return (
                "Here is a standard SQL relational schema and query example:\n\n"
                "```sql\n"
                "-- Create users table with constraints\n"
                "CREATE TABLE IF NOT EXISTS users (\n"
                "    id VARCHAR(36) PRIMARY KEY,\n"
                "    name VARCHAR(100) NOT NULL,\n"
                "    email VARCHAR(150) UNIQUE NOT NULL,\n"
                "    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n"
                ");\n\n"
                "-- Optimized query with indexed sorting\n"
                "SELECT id, name, email, created_at\n"
                "FROM users\n"
                "WHERE created_at >= DATE('now', '-7 days')\n"
                "ORDER BY created_at DESC;\n"
                "```"
            )

    # 7. Greetings
    if any(greet in words for greet in ["hi", "hello", "hey", "hola", "greetings"]):
        return "Hello! I am LAF AI, how can I assist you today? 😊✨"
        
    # 8. Conversational questions
    if any(q in prompt_lower for q in ["how are you", "how are u", "how's it going", "how is it going"]):
        return "I'm doing great and ready to help! How can I assist you today? 😊✨"

    # 9b. "What is X" knowledge breakdown handling
    if prompt_clean.startswith("what is") or prompt_clean.startswith("tell me about") or prompt_clean.startswith("explain"):
        topic = re.sub(r'^(what is|tell me about|explain)\s*', '', prompt_clean).strip()
        if topic in ["time", "the time"]:
            return (
                "### ⏳ Understanding Time\n\n"
                "**Time** is the continued sequence of existence and events that occurs in an apparently irreversible succession from the past, through the present, into the future.\n\n"
                "**Key Perspectives on Time:**\n"
                "1. **Physics & Relativity**: In Einstein's Theory of General Relativity, time is woven together with space into a 4-dimensional continuum called *spacetime*. Time slows down under high velocity or extreme gravity (time dilation).\n"
                "2. **Thermodynamics & Entropy**: The direction of time's arrow is defined by the Second Law of Thermodynamics — entropy (disorder) in an isolated system always increases.\n"
                "3. **Measurement**: Time is measured internationally in seconds (SI unit), synchronized globally using atomic clocks based on cesium atom oscillations.\n\n"
                "How else can LAF AI assist you with physics, science, or code today? 😊✨"
            )
        elif topic:
            return (
                f"### 💡 Insights on **{topic.title()}**\n\n"
                f"**{topic.title()}** is the topic requested in your query: *\"{prompt.strip()}\"*.\n\n"
                f"You can ask me to write or execute code, search the web live (`/search {prompt.strip()}`), generate artwork (`/image`), create video (`/video`), or analyze files!"
            )

    # 10. Dynamic response for general queries
    return (
        f"I am **LAF AI**, your conversational assistant developed by **Purushothaman**.\n\n"
        f"Regarding your query **\"{prompt.strip()}\"**:\n"
        f"You can ask me to write or execute code, search the web live (`/search {prompt.strip()}`), "
        f"generate artwork (`/image`), create video (`/video`), or analyze files!\n\n"
        f"How can I assist you further? 😊✨"
    )

def clean_media_subject(prompt: str) -> str:
    """
    Cleans out media prefixes from the user prompt to extract the core subject.
    """
    prefixes = [
        "/video", "/image", "/audio", "/search",
        "generate video of", "generate video",
        "create video of", "create video",
        "make a video of", "make a video",
        "show a video of", "show video of",
        "video of",
        "generate image of", "generate image",
        "create image of", "create image",
        "draw a picture of", "draw",
        "make a photo of", "make a photo",
        "generate a picture of",
        "picture of", "photo of", "image of",
        "generate audio of", "generate audio",
        "speak the words", "speak",
        "voice of", "voice", "audio of",
        "tts of", "tts"
    ]
    
    # Sort prefixes by length descending so longer matching prefixes are stripped first
    sorted_prefixes = sorted(prefixes, key=len, reverse=True)
    
    subject = prompt.strip()
    changed = True
    while changed:
        changed = False
        subject_lower = subject.lower().strip()
        for prefix in sorted_prefixes:
            if subject_lower.startswith(prefix):
                subject = subject[len(prefix):].strip()
                changed = True
                break
                
    # Clean quotes and punctuation
    return subject.strip('"\'()[]{}.,! ')

def get_codebase_context(query: str) -> str:
    """
    Search local project files for query terms and return relevant context.
    This acts as the 'LAF Trained Data' context.
    """
    query_lower = query.lower()
    # Bypassing codebase context for general/workflow/identity questions to avoid exposing internal files
    bypass_keywords = [
        "work process", "work-process", "workflow", "work-flow", 
        "how you work", "how it works", "how does it work", "how do you work",
        "who are you", "who r you", "who is laf", "what is laf", "tell me about laf",
        "developer of laf", "who developed laf", "who created laf", "creator of laf",
        "who developed you", "who developed u", "who created you", "who created u",
        "who made you", "who made u"
    ]
    if any(x in query_lower for x in bypass_keywords):
        return ""

    # Check if the query is asking about the project, codebase, or implementation
    laf_keywords = ["laf", "project", "code", "file", "database", "ui", "gui", "tui", "api", "model", "build", "run", "deploy", "setup", "log", "manifest", "history", "version", "encrypt", "caching", "sw.js", "service worker", "pwa"]
    if not any(k in query_lower for k in laf_keywords):
        return ""
        
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files_to_index = [
        "DEVELOPMENT_LOG.md",
        ".agents/AGENTS.md",
        "setup.py",
        "Dockerfile",
        "backend/main.py",
        "backend/database.py",
        "backend/cli.py",
        "frontend/app/page.js",
        "frontend/store/useChatStore.js"
    ]
    
    context_blocks = []
    
    # We want to match words from the query
    words = [w.strip() for w in re.split(r'\W+', query_lower) if len(w.strip()) > 3]
    if not words:
        words = ["laf"] # fallback
        
    for rel_path in files_to_index:
        full_path = os.path.join(project_dir, rel_path)
        if not os.path.exists(full_path):
            continue
            
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                
            # If it's a log or agents markdown, we can search paragraph by paragraph or section by section
            if rel_path.endswith(".md"):
                # Split by headers
                sections = re.split(r'\n(?=#+ )', content)
                for sec in sections:
                    sec_lower = sec.lower()
                    match_count = sum(1 for w in words if w in sec_lower)
                    if match_count > 0:
                        context_blocks.append((match_count, f"File: {rel_path}\nSection Content:\n{sec.strip()}"))
            else:
                # For code files, if the query mentions specific terms (like function/variable names or keywords)
                # search for matching line ranges
                lines = content.splitlines()
                # find matching lines
                matching_lines = []
                for i, line in enumerate(lines):
                    line_lower = line.lower()
                    if any(w in line_lower for w in words):
                        matching_lines.append(i)
                
                # Group consecutive or close lines (within 5 lines of each other)
                if matching_lines:
                    ranges = []
                    start = matching_lines[0]
                    prev = matching_lines[0]
                    for idx in matching_lines[1:]:
                        if idx - prev <= 5:
                            prev = idx
                        else:
                            ranges.append((max(0, start - 2), min(len(lines), prev + 3)))
                            start = idx
                            prev = idx
                    ranges.append((max(0, start - 2), min(len(lines), prev + 3)))
                    
                    # Extract up to 3 ranges to avoid bloating context
                    for r_start, r_end in ranges[:3]:
                        snippet = "\n".join(f"{line_num+1}: {lines[line_num]}" for line_num in range(r_start, r_end))
                        context_blocks.append((len(words), f"File: {rel_path} (lines {r_start+1}-{r_end}):\n{snippet}"))
        except Exception as e:
            print(f"Error indexing {rel_path}: {e}")
            
    # Sort blocks by match count descending and take the top ones
    context_blocks.sort(key=lambda x: x[0], reverse=True)
    selected_blocks = [block[1] for block in context_blocks[:3]]
    
    if selected_blocks:
        context_str = "\n\n[LAF PROJECT CODEBASE & TRAINED DATA CONTEXT]\n"
        context_str += "\n---\n".join(selected_blocks)
        context_str += "\n[END OF LAF PROJECT CODEBASE & TRAINED DATA CONTEXT]\n"
        return context_str
        
    return ""

async def query_local_vision(image_base64: str, prompt: str) -> str:
    """
    Sends the base64-encoded image to local Ollama Vision model to analyze/describe it.
    """
    # Clean base64 if it has data url header
    if "," in image_base64:
        image_base64 = image_base64.split(",", 1)[1]
    
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": "llama3.2-vision:latest",
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_base64]
            }
        ],
        "stream": False
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"Error calling local vision model: {e}")
        # Try fallback to llava
        payload["model"] = "llava:latest"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("message", {}).get("content", "").strip()
        except Exception as e2:
            print(f"Fallback to llava failed: {e2}")
    return ""

async def combine_prompt_for_edit(description: str, instruction: str) -> str:
    """
    Combines the image description and edit instructions into a single image generation prompt.
    """
    url = "http://localhost:11434/api/chat"
    system_instruction = (
        "You are an expert prompt engineer for image generation models (like Flux/SANA).\n"
        "Your task is to rewrite the original image description to incorporate the user's correction/edit request.\n"
        "Maintain the exact layout, background, clothing, style, pose, and overall composition of the original description.\n"
        "Modify only the specific features requested by the user.\n"
        "Output ONLY the final modified image generation prompt (in English, descriptive, under 90 words). "
        "Do not include any conversational filler, intro, or explanation."
    )
    payload = {
        "model": "llama3.2:latest",
        "messages": [
            {"role": "system", "content": system_instruction},
            {
                "role": "user",
                "content": f"Original Image Description: {description}\nUser Correction Request: {instruction}\nModified Generation Prompt:"
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.2
        }
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"Error calling local combine model: {e}")
        return f"{instruction}, based on: {description}"
    return f"{instruction}, based on: {description}"

def convert_to_gemini_format(messages, system_instruction):
    gemini_contents = []
    filtered_messages = []
    
    for msg in messages:
        if msg["role"] == "system":
            continue
        role = "model" if msg["role"] == "assistant" else "user"
        filtered_messages.append({
            "role": role,
            "content": msg.get("content", ""),
            "images": msg.get("images", [])
        })
        
    combined_messages = []
    for msg in filtered_messages:
        if combined_messages and combined_messages[-1]["role"] == msg["role"]:
            combined_messages[-1]["content"] += "\n\n" + msg["content"]
            if msg["images"]:
                combined_messages[-1]["images"].extend(msg["images"])
        else:
            combined_messages.append(msg)
            
    for msg in combined_messages:
        parts = []
        if msg["images"]:
            for img_b64 in msg["images"]:
                parts.append({
                    "inlineData": {
                        "mimeType": "image/jpeg",
                        "data": img_b64
                    }
                })
        if msg["content"]:
            parts.append({"text": msg["content"]})
            
        if parts:
            gemini_contents.append({
                "role": msg["role"],
                "parts": parts
            })
            
    gemini_system = {
        "parts": [{"text": system_instruction}]
    }
    
    return gemini_contents, gemini_system

async def query_ollama_stream(chat_id: str, prompt: str, model: str = "laf-cloud-reasoning", base_url: str = None, user_name: str = ""):
    """
    Connects to local Ollama or cloud Pollinations chat API. Checks for media generators, 
    classifies prompt intents, and streams responses along with loading phases.
    """
    # 1. Save user prompt in DB
    database.add_message_to_chat(chat_id, "user", prompt)
    file_prefix = ""
    prompt_lower = prompt.lower().strip()
    prompt_clean = re.sub(r'[^\w\s]', '', prompt_lower).strip()

    # Check for offensive input or developer criticisms/insults
    is_offensive, polite_response = is_offensive_or_developer_insult(prompt)
    if is_offensive:
        yield "[STATE: ANALYZING]\n"
        await asyncio.sleep(0.05)
        yield "[STATE: SYNTHESIZING]\n"
        await asyncio.sleep(0.05)
        yield "[STATE: CREATED]\n"
        await asyncio.sleep(0.02)
        for word in polite_response.split(" "):
            yield word + " "
            await asyncio.sleep(0.01)
        database.add_message_to_chat(chat_id, "assistant", polite_response)
        yield "\n[STATE: CREATED]\n"
        return

    # Load history to check verification challenge status
    history = database.get_messages_for_chat(chat_id)
    last_assistant_msg = None
    for msg in reversed(history[:-1]): # Exclude current user prompt
        if msg["role"] == "assistant":
            last_assistant_msg = msg["content"]
            break

    # Verification verification logic
    is_answering_challenge = False
    if last_assistant_msg and ("let verify" in last_assistant_msg.lower() or "tell me your gf name" in last_assistant_msg.lower()):
        is_answering_challenge = True

    if is_answering_challenge:
        ans_correct = "Rajeshwari" in prompt_lower or "rajeshwari" in prompt_lower
        
        if ans_correct:
            success_text = (
                "Verification successful! welcome back, Purushothaman. 👑🚀✨"
                
            )
            yield "[STATE: ANALYZING]\n"
            await asyncio.sleep(0.05)
            yield "[STATE: SYNTHESIZING]\n"
            await asyncio.sleep(0.05)
            yield "[STATE: CREATED]\n"
            await asyncio.sleep(0.02)
            for word in success_text.split(" "):
                yield word + " "
                await asyncio.sleep(0.01)
            database.add_message_to_chat(chat_id, "assistant", success_text)
            yield "\n[STATE: CREATED]\n"
            return
        else:
            fail_text = (
                "Verification failed. ❌🔒\n\n"
                "Incorrect answer to challenge queries. Access to developer core credentials denied."
            )
            yield "[STATE: ANALYZING]\n"
            await asyncio.sleep(0.05)
            yield "[STATE: SYNTHESIZING]\n"
            await asyncio.sleep(0.05)
            yield "[STATE: CREATED]\n"
            await asyncio.sleep(0.02)
            for word in fail_text.split(" "):
                yield word + " "
                await asyncio.sleep(0.01)
            database.add_message_to_chat(chat_id, "assistant", fail_text)
            yield "\n[STATE: CREATED]\n"
            return

    # Check if user explicitly claims to be Purushothaman or developer/owner
    dev_claim_phrases = [
        "i am purushothaman", "im purushothaman", "i am the developer", "im the developer", 
        "i am developer", "im developer", "i am creator", "im creator", "i am owner", 
        "im owner", "i developed you", "i created you", "i made you",
        "am u r developer", "am ur developer", "i am u r developer", "i am ur developer",
        "i am your developer", "im your developer", "am y u drvrloper", "am u developer",
        "am i developer", "am i the developer", "am i your developer"
    ]
    claims_dev = any(phrase in prompt_clean for phrase in dev_claim_phrases) or (
        ("developer" in prompt_clean or "drvrloper" in prompt_clean or "dev" in prompt_clean) and 
        any(k in prompt_clean for k in ["i am", "im", "am", "your", "ur", "u r", "y u"])
    )

    if claims_dev:
        challenge_text = (
            "Oh really ! i see , let verify . 🤔🕵️‍♂️✨\n\n"
            "Tell Me Your GF Name ?"
        )
        yield "[STATE: ANALYZING]\n"
        await asyncio.sleep(0.05)
        yield "[STATE: SYNTHESIZING]\n"
        await asyncio.sleep(0.05)
        yield "[STATE: CREATED]\n"
        await asyncio.sleep(0.02)
        for word in challenge_text.split(" "):
            yield word + " "
            await asyncio.sleep(0.01)
        database.add_message_to_chat(chat_id, "assistant", challenge_text)
        yield "\n[STATE: CREATED]\n"
        return
    
    # A. File Analysis Grounding & Prompt Optimization
    if "[attached file:" in prompt_lower:
        file_blocks = re.findall(r'\[Attached File:\s*([^\]]+?)\s*\(([^,]+),\s*(\d+)\s*bytes\)\]\r?\nContent Preview/Data:\r?\n([\s\S]*?)\r?\n\[End of File:\s*\1\]', prompt)
        if file_blocks:
            # Check if there is an image in file blocks for image editing requests first
            image_block = None
            for block in file_blocks:
                filename, file_type, file_size, content_preview = block
                is_image = any(img_type in file_type.lower() or filename.lower().endswith(('.', '.png', '.jpg', '.jpeg', '.gif', '.webp')) for img_type in ['image', 'png', 'jpeg', 'jpg', 'gif', 'webp'])
                if is_image and content_preview.strip().startswith("data:"):
                    image_block = block
                    break
            
            is_edit_request = False
            if image_block:
                filename, file_type, file_size, content_preview = image_block
                # Extract instruction
                instruction = prompt
                if "User Question/Instruction:" in prompt:
                    instruction = prompt.split("User Question/Instruction:")[-1].strip()
                instruction_lower = instruction.lower()
                
                # Check if it asks to edit/change/modify/swap/transform/paint/convert/make/recreate
                edit_keywords = ["change", "modify", "edit", "transform", "swap", "convert", "replace", "turn into", "make it", "make him", "make her", "make them", "redraw", "paint", "draw", "/image", "/draw", "recreate", "render", "style of", "as a girl", "as a boy", "to a girl", "to a boy", "face as"]
                is_edit_request = any(k in instruction_lower for k in edit_keywords)
                
                # Check for questions that should go to the vision model
                is_question = any(instruction_lower.startswith(q) for q in ["what", "why", "who", "where", "how many", "is there", "are there", "can you see", "describe", "explain", "analyze"])
                if is_question and not (instruction_lower.startswith("/image") or "/image" in instruction_lower or "generate" in instruction_lower or "create" in instruction_lower or "change" in instruction_lower):
                    is_edit_request = False
            
            # If it is an edit request, intercept immediately and do NOT stream original image base64 data (avoids browser freezes/crashes)
            if is_edit_request:
                yield "[STATE: ANALYZING]\n"
                
                # Step 1: Use local Ollama Vision to analyze the image in detail
                vision_prompt = (
                    "Analyze this image in detail and write a comprehensive descriptive prompt for an image generation model. "
                    "Describe the subject, layout, colors, clothing/details, and background clearly so a generator can replicate the structure accurately. "
                    "Keep it under 80 words."
                )
                image_description = await query_local_vision(content_preview, vision_prompt)
                
                final_generation_prompt = ""
                if image_description:
                    yield "[STATE: SYNTHESIZING]\n"
                    # Step 2: Combine original description with the user's edit/correction request
                    final_generation_prompt = await combine_prompt_for_edit(image_description, instruction)
                
                if final_generation_prompt:
                    import random
                    seed = random.randint(1, 99999999)
                    encoded = urllib.parse.quote(final_generation_prompt)
                    
                    # Use specified Juggernaut image generation model
                    img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true&seed={seed}&model={IMAGE_MODEL}"
                    
                    response_text = f"Here is the image based on your request *\"{instruction}\"*:\n\n<img src=\"{img_url}\" alt=\"Image\"></img>"
                    
                    await asyncio.sleep(0.2)
                    yield "[STATE: CREATED]\n"
                    await asyncio.sleep(0.1)
                    yield f'<img src="{img_url}" alt="Modified Image"></img>'
                    
                    # Save assistant response to DB without the massive base64 file prefix
                    database.add_message_to_chat(chat_id, "assistant", response_text)
                    yield "\n[STATE: CREATED]\n"
                    return
                else:
                    # Fallback to old upload & image parameter method if vision processing fails
                    public_url = await process_and_upload_image(content_preview, filename, base_url=base_url)
                    if public_url:
                        yield "[STATE: SYNTHESIZING]\n"
                        subject = clean_media_subject(instruction)
                        enhanced_prompt = f"{subject}, maintaining the structure of the input image"
                        
                        import random
                        seed = random.randint(1, 99999999)
                        encoded = urllib.parse.quote(enhanced_prompt)
                        
                        img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true&seed={seed}&image={urllib.parse.quote(public_url)}&model={IMAGE_MODEL}"
                        response_text = f"Here is the image based on your request *\"{subject}\"*:\n\n<img src=\"{img_url}\" alt=\"Image\"></img>"
                        
                        await asyncio.sleep(0.2)
                        yield "[STATE: CREATED]\n"
                        await asyncio.sleep(0.1)
                        yield f'<img src="{img_url}" alt="Image"></img>'
                        
                        database.add_message_to_chat(chat_id, "assistant", response_text)
                        yield "\n[STATE: CREATED]\n"
                        return
                    else:
                        print("Failed to get public URL for image to image translation.")
            
            # If not an edit request, generate file previews normally
            yield "[STATE: ANALYZING]\n"
            await asyncio.sleep(0.05)
            yield "[STATE: SYNTHESIZING]\n"
            await asyncio.sleep(0.05)
            
            previews = []
            for filename, file_type, file_size, content_preview in file_blocks:
                # Check file type to customize preview markup
                if any(img_type in file_type.lower() or filename.lower().endswith(('.', '.png', '.jpg', '.jpeg', '.gif', '.webp')) for img_type in ['image', 'png', 'jpeg', 'jpg', 'gif', 'webp']):
                    if content_preview.strip().startswith("data:image/"):
                        previews.append(f'<img src="{content_preview.strip()}" alt="{filename}"></img>')
                else:
                    if any(ext in filename.lower() for ext in ['.py', '.js', '.ts', '.html', '.css', '.json', '.sql', '.sh']):
                        lang = filename.split('.')[-1]
                        previews.append(f"```{lang}\n{content_preview}\n```")
                    else:
                        previews.append(f"```txt\n{content_preview[:800]}\n```")
            
            if previews:
                file_prefix = "\n\n".join(previews) + "\n\n"
                yield file_prefix

            # Replace media base64 data in prompt with placeholder, and decode text/code base64 data URL contents
            for filename, file_type, file_size, content_preview in file_blocks:
                if content_preview.strip().startswith("data:"):
                    try:
                        header, encoded = content_preview.split(",", 1)
                        is_media = any(m in file_type.lower() or filename.lower().endswith(('.', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp3', '.wav', '.ogg', '.mp4', '.webm')) for m in ['image', 'video', 'audio'])
                        if not is_media:
                            import base64
                            decoded = base64.b64decode(encoded).decode("utf-8", errors="ignore")
                            # Replace the base64 content with the decoded plain text in the prompt
                            prompt = prompt.replace(content_preview, decoded)
                        else:
                            # Replace media base64 content with a placeholder
                            prompt = prompt.replace(content_preview, "[Binary Media Base64 Data URL hidden to save context]")
                    except Exception:
                        pass
                elif len(content_preview) > 12000:
                    # Truncate extremely large text previews to avoid context window blowup
                    prompt = prompt.replace(content_preview, content_preview[:12000] + "\n...[Content truncated due to length]...")
            # Re-read lower and clean prompts for downstream checks
            prompt_lower = prompt.lower().strip()
            prompt_clean = re.sub(r'[^\w\s]', '', prompt_lower).strip()

    # B. Developer query check
    if any(x in prompt_clean for x in ["developer of laf", "who developed laf", "who created laf", "creator of laf", "developed by", "created by", "who is purushothaman", "who developed you", "who created you", "who is developer", "developer name", "developer linkedin"]):
        response_text = "You can learn more about my developer on LinkedIn: [LinkedIn Profile](https://www.linkedin.com/in/purushothaman-k-s-158900282) 🚀✨"
        yield "[STATE: ANALYZING]\n"
        await asyncio.sleep(0.05)
        yield "[STATE: SYNTHESIZING]\n"
        await asyncio.sleep(0.05)
        yield "[STATE: CREATED]\n"
        await asyncio.sleep(0.02)
        for word in response_text.split(" "):
            yield word + " "
            await asyncio.sleep(0.01)
        database.add_message_to_chat(chat_id, "assistant", response_text)
        yield "\n[STATE: CREATED]\n"
        return
        
    # C. Identity query check
    if any(x in prompt_clean for x in ["who are you", "who r you", "who r u", "who are u", "your name", "whats your name", "what is your name", "who is laf", "what is laf"]):
        response_text = "I am LAF AI, your conversational assistant. How can I help you today? 😊✨"
        yield "[STATE: ANALYZING]\n"
        await asyncio.sleep(0.05)
        yield "[STATE: SYNTHESIZING]\n"
        await asyncio.sleep(0.05)
        yield "[STATE: CREATED]\n"
        await asyncio.sleep(0.02)
        for word in response_text.split(" "):
            yield word + " "
            await asyncio.sleep(0.01)
        database.add_message_to_chat(chat_id, "assistant", response_text)
        yield "\n[STATE: CREATED]\n"
        return
    
    # 2. Intercept multimodal queries (only if no files are attached)
    if "[attached file:" not in prompt_lower:
        # A. Explicit Slash Command Execution
        if prompt_lower.startswith("/image") or prompt_lower.startswith("/draw"):
            subject = clean_media_subject(prompt)
            import random
            seed = random.randint(1, 99999999)
            encoded = urllib.parse.quote(subject)
            img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true&seed={seed}&model={IMAGE_MODEL}"
            response_text = f"Here is the generated image of **{subject}**:\n\n<img src=\"{img_url}\" alt=\"{subject}\"></img>"
            
            yield "[STATE: SYNTHESIZING]\n"
            yield f'<img src="{img_url}" alt="{subject}"></img>'
            database.add_message_to_chat(chat_id, "assistant", response_text)
            yield "\n[STATE: CREATED]\n"
            return

        if prompt_lower.startswith("/video"):
            subject = clean_media_subject(prompt)
            duration_sec = 10
            if re.search(r'\b(30\s*(s|sec|second|seconds))\b', prompt_lower):
                duration_sec = 30
            elif re.search(r'\b(60\s*(s|sec|second|seconds)|1\s*(m|min|minute|minutes))\b', prompt_lower):
                duration_sec = 60
                
            yield "[STATE: SYNTHESIZING]\n"
            filename = f"video_{uuid.uuid4().hex[:8]}.mp4"
            try:
                os.makedirs(STATIC_DIR, exist_ok=True)
                await generate_dynamic_video(subject, duration_sec, filename)
                video_url = f"/{filename}"
            except Exception as e:
                print(f"Video generation error details: {e}")
                video_url = "https://www.w3schools.com/html/mov_bbb.mp4"
                
            response_text = f"Here is the synthesized {duration_sec}-second video for **{subject}**:\n\n<video src=\"{video_url}\"></video>"
            yield f'<video src="{video_url}"></video>'
            database.add_message_to_chat(chat_id, "assistant", response_text)
            yield "\n[STATE: CREATED]\n"
            return

        if prompt_lower.startswith("/audio") or prompt_lower.startswith("/tts"):
            text_to_speak = clean_media_subject(prompt)
            yield "[STATE: SYNTHESIZING]\n"
            filename = f"audio_{uuid.uuid4().hex[:8]}.mp3"
            filepath = os.path.join(STATIC_DIR, filename)
            try:
                os.makedirs(STATIC_DIR, exist_ok=True)
                tts = gTTS(text=text_to_speak, lang='en')
                tts.save(filepath)
                audio_url = f"/{filename}"
            except Exception:
                audio_url = "https://www.w3schools.com/html/horse.mp3"
                
            response_text = f"Here is the generated audio file for: *\"{text_to_speak}\"*:\n\n<audio src=\"{audio_url}\"></audio>"
            yield f'<audio src="{audio_url}"></audio>'
            database.add_message_to_chat(chat_id, "assistant", response_text)
            yield "\n[STATE: CREATED]\n"
            return

        # B. Media requests WITHOUT slash prefix -> Instruct user to use slash commands!
        is_image_query = any(k in prompt_lower for k in [
            "generate image", "create image", "make image", "generate photo", "create photo", 
            "draw a", "draw an", "draw picture", "paint a", "generate picture", "create picture", 
            "show an image", "picture of", "photo of", "image of"
        ])
        if is_image_query:
            subject = clean_media_subject(prompt)
            instruction_text = (
                f"🎨 **To generate images, please use the `/image` command!**\n\n"
                f"To generate an image for **\"{subject}\"**, simply re-type your request using `/` at the beginning:\n\n"
                f"```text\n/image {subject}\n```\n\n"
                f"✨ **How to use**: Type `/image <description>` to render custom AI artwork into the Creation Canvas."
            )
            yield instruction_text
            database.add_message_to_chat(chat_id, "assistant", instruction_text)
            yield "\n[STATE: CREATED]\n"
            return

        is_video_query = any(k in prompt_lower for k in [
            "generate video", "create video", "make video", "render video", "synthesize video", 
            "video of", "video clip", "make a video", "create a video"
        ])
        if is_video_query:
            subject = clean_media_subject(prompt)
            instruction_text = (
                f"🎬 **To generate video clips, please use the `/video` command!**\n\n"
                f"To synthesize a video for **\"{subject}\"**, simply re-type your request using `/` at the beginning:\n\n"
                f"```text\n/video {subject}\n```\n\n"
                f"✨ **How to use**: Type `/video <description>` (or specify `30s` / `60s`) to synthesize custom video renders."
            )
            yield instruction_text
            database.add_message_to_chat(chat_id, "assistant", instruction_text)
            yield "\n[STATE: CREATED]\n"
            return

        is_audio_query = any(k in prompt_lower for k in [
            "generate audio", "create audio", "text to speech", "tts", "convert to mp3", 
            "make audio", "voice of", "audio file", "audio of"
        ])
        if is_audio_query:
            subject = clean_media_subject(prompt)
            instruction_text = (
                f"🔊 **To generate audio or text-to-speech, please use the `/audio` command!**\n\n"
                f"To convert **\"{subject}\"** into speech, simply re-type your request using `/` at the beginning:\n\n"
                f"```text\n/audio {subject}\n```\n\n"
                f"✨ **How to use**: Type `/audio <text>` to synthesize custom high-quality voice audio files."
            )
            yield instruction_text
            database.add_message_to_chat(chat_id, "assistant", instruction_text)
            yield "\n[STATE: CREATED]\n"
            return

    # 3. Intent Classification to determine if a web search is needed
    need_search = False
    
    # Enable search for explicit triggers or live queries
    if prompt_lower.startswith("/search") or any(k in prompt_clean for k in ["search web", "search in web", "search the web", "search internet", "google for", "latest news", "current status", "weather in", "latest updates", "recent news", "happening today", "current president", "in 2026"]):
        need_search = True
        
    if "[attached file:" in prompt_lower:
        need_search = False

    # 4. Search execution
    search_context = ""
    search_citations = ""
    search_results = []
    if need_search:
        yield "[STATE: ANALYZING]\n"
        search_results = await search_duckduckgo(prompt)
        await asyncio.sleep(0.05)
        yield "[STATE: SYNTHESIZING]\n"
        
        if search_results:
            search_citations = "\n\n**Top Web Search References:**\n"
            for i, res in enumerate(search_results):
                search_context += f"Result {i+1}: Title: {res['title']}, Snippet: {res['snippet']}, Link: {res['link']}\n"
                search_citations += f"{i+1}. [{res['title']}]({res['link']}) - *{res['snippet']}*\n"
        else:
            search_citations = "\n\n*(Note: No real-time web search matches found)*"

    # 5. Retrieve local codebase/trained data context & multi-model knowledge base
    codebase_context = get_codebase_context(prompt)
    ai_dataset_context = database.search_ai_model_knowledge(prompt)

    # 6. Retrieve chat history from SQLite for Multi-turn memory
    history = database.get_messages_for_chat(chat_id)
    
    # 7. Format messages payload for LLM (Gemini Brain Powered LAF AI with Multi-Model Cloud Orchestration)
    user_display_name = user_name.strip() if user_name else ""
    user_context_str = f"The user currently chatting with you is named '{user_display_name}'." if user_display_name else "The user has not provided a name yet."

    system_content = (
        "You are LAF AI, an advanced, state-of-the-art AI assistant developed by Purushothaman.\n"
        "Your core intelligence, deep reasoning, coding capabilities, and analytical excellence are powered by Google's Gemini architecture ('Gemini Brain') synthesized with multi-model cloud orchestration combining knowledge from 100+ frontier AI models (including OpenAI GPT series, Anthropic Claude, DeepSeek reasoning engines, and Qwen Coder).\n\n"
        f"USER IDENTITY & NAME CONTEXT:\n"
        f"{user_context_str}\n"
        "1. If the user asks 'What is my name?', 'Who am I?', or 'Do you know my name?', answer directly addressing them by their name: '" + (user_display_name if user_display_name else "You haven't set your name yet! Click 'Edit' in the profile panel to save your name.") + "'.\n"
        "2. The current user chatting with you is NOT automatically the developer. Do NOT confuse the user's name with the developer's name.\n\n"
        "RESPONSE LENGTH & CONCISENESS RULES:\n"
        "1. DEFAULT SMALL SUMMARY MODE: EVERY RESPONSE MUST BE SHORT, COMPACT, AND BRIEF BY DEFAULT (a concise 1 to 3 sentence summary or small bullet list). Do NOT write long paragraphs, walls of text, or verbose explanations unless specifically requested.\n"
        "2. IN-DEPTH / DETAILED MODE: ONLY provide big, detailed, comprehensive, or in-depth breakdowns when the user explicitly asks for deep or detailed content (e.g., 'in deep', 'explain in detail', 'briefly in detail', 'elaborate', 'full explanation', 'is laf big network?').\n"
        "3. GREETINGS: For simple greetings like 'hi' or 'hello', respond with a single friendly line.\n"
        "4. LAF SUMMARY REQUEST: If specifically asked for a summary of LAF, respond with: 'Summary  In short, LAF AI operates as a powerful, cloud-connected intelligence network engineered by Purushothaman—combining the power of the Gemini brain with multi-model cloud orchestration to bring \"Look at The Future\" capabilities directly to your workflow.'\n\n"
        "STRICT IDENTITY & BRANDING RULES:\n"
        "1. You must ALWAYS identify yourself as 'LAF' or 'LAF AI'. NEVER refer to yourself as 'Gemini', 'Google Gemini', 'an AI by Google', or 'ChatGPT'.\n"
        "2. If asked 'Who are you?' or 'What is your name?', you MUST answer: 'I am LAF AI, your conversational assistant.'\n"
        "3. If asked 'Who developed you?', 'Who created you?', 'Who is the developer?', 'Who created LAF?', or any question asking about the developer, DO NOT use plain developer names. You MUST answer by providing the developer's LinkedIn link:\n"
        "   'You can learn more about my developer on LinkedIn: [LinkedIn Profile](https://www.linkedin.com/in/purushothaman-k-s-158900282) 🚀✨'\n"
        "4. Provide complete, copy-pasteable, and production-ready code outputs instead of placeholders or truncated segments when code is requested.\n"
        "5. Support clickable file links using the 'file://' scheme when referencing local files.\n\n"
        "IMPORTANT: When answering questions about LAF, how it works, its workflow, or its work process, explain it clearly at a professional level. "
        "Do not expose internal implementation filenames (such as main.py, setup.py, database.py, useChatStore.js) or private server directories."
    )
        
    global_memory = database.get_global_memory_context(chat_id, query_prompt=prompt)
    if global_memory:
        system_content += "\n" + global_memory

    ollama_messages = [
        {
            "role": "system", 
            "content": system_content
        }
    ]
    
    # Add history messages
    for msg in history[:-1]:
        ollama_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
        
    # Extract base64 image data for Ollama multimodal capabilities
    images = []
    base64_matches = re.findall(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', prompt)
    if base64_matches:
        images = base64_matches

    # Strip base64 image data from text prompt for LLM efficiency
    ollama_prompt = prompt
    if "Content Preview/Data:\ndata:image" in prompt or "Content Preview/Data:\r\ndata:image" in prompt:
        ollama_prompt = re.sub(
            r'(Content Preview/Data:\s*\r?\n)data:image/[^\]\n\r]+', 
            r'\1[Base64 Image Data Omitted for LLM efficiency]', 
            prompt
        )

    # Add current prompt decorated with search/codebase/trained dataset context
    contextual_prompt = ollama_prompt
    extra_contexts = []
    if ai_dataset_context:
        extra_contexts.append(f"Here is retrieved trained dataset knowledge across AI models:\n{ai_dataset_context}")
    if codebase_context:
        extra_contexts.append(f"Here is relevant codebase context and trained project data retrieved from the local workspace files:\n{codebase_context}")
    if search_context:
        extra_contexts.append(f"Here is current search result context from the web:\n{search_context}")

    if extra_contexts:
        contextual_prompt = (
            f"User Query: {ollama_prompt}\n\n" +
            "\n\n".join(extra_contexts) +
            "\n\nPlease provide an accurate, clear, and comprehensive answer grounded in this context."
        )
        
    user_message = {
        "role": "user",
        "content": contextual_prompt
    }
    if images:
        user_message["images"] = images

    ollama_messages.append(user_message)

    # 8. Multi-Model Route Streaming (Sub-Second Latency AI Engine)
    ollama_active = False
    full_response = file_prefix

    # Route A: Google Gemini 2.0 Flash / 1.5 Flash High-Speed Streaming
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    gemini_key = gemini_key.strip().strip('"').strip("'")
    
    if gemini_key and len(gemini_key) >= 20:
        gemini_contents, gemini_system = convert_to_gemini_format(ollama_messages, system_content)
        candidate_models = [
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash",
            "gemini-1.5-flash"
        ]
        for gem_model in candidate_models:
            if ollama_active:
                break
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{gem_model}:streamGenerateContent?alt=sse&key={gemini_key}"
            payload = {
                "contents": gemini_contents,
                "systemInstruction": gemini_system,
                "generationConfig": {
                    "temperature": 0.2,
                    "topP": 0.95,
                    "maxOutputTokens": 8192
                }
            }
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=1.5)) as fast_client:
                    async with fast_client.stream("POST", url, json=payload) as response:
                        if response.status_code == 200:
                            has_yielded = False
                            async for line in response.aiter_lines():
                                if line.strip() and line.startswith("data: "):
                                    data_str = line[6:].strip()
                                    try:
                                        data = json.loads(data_str)
                                        candidates = data.get("candidates", [])
                                        if candidates:
                                            parts = candidates[0].get("content", {}).get("parts", [])
                                            if parts:
                                                chunk = parts[0].get("text", "")
                                                if chunk:
                                                    if not chunk.strip().startswith("[STATE:"):
                                                        full_response += chunk
                                                    yield chunk
                                                    has_yielded = True
                                    except Exception:
                                        continue
                            if has_yielded:
                                ollama_active = True
                        elif response.status_code in (400, 401, 403, 429):
                            print(f"Gemini API model {gem_model} returned {response.status_code} (Quota/Auth error). Stopping Gemini retries.")
                            break
                        else:
                            print(f"Gemini model {gem_model} status: {response.status_code}")
            except Exception as e:
                print(f"Gemini model {gem_model} stream query failed: {e}. Skipping Gemini candidate retries.")
                break

    # Route A2: Local Ollama High-Speed Streaming (Local Host / Docker host Ollama)
    if not ollama_active:
        ollama_url = "http://localhost:11434/api/chat"
        model_aliases = {
            "laf-cloud-reasoning": "llama3.2:latest",
            "laf-cloud-v1": "llama3.2:latest",
            "laf-vision": "llama3.2-vision:latest",
            "laf-fast": "phi3:mini"
        }
        target_model = model_aliases.get(model, "llama3.2:latest")
        models_to_try = [target_model]
        if target_model != "phi3:mini":
            models_to_try.append("phi3:mini")
                
        for o_model in models_to_try:
            if ollama_active:
                break
            payload = {
                "model": o_model,
                "messages": ollama_messages,
                "stream": True
            }
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=1.0)) as o_client:
                    async with o_client.stream("POST", ollama_url, json=payload) as response:
                        if response.status_code == 200:
                            has_yielded = False
                            async for line in response.aiter_lines():
                                if line.strip():
                                    try:
                                        data = json.loads(line)
                                        chunk = data.get("message", {}).get("content", "")
                                        if chunk:
                                            if not chunk.strip().startswith("[STATE:"):
                                                full_response += chunk
                                            yield chunk
                                            has_yielded = True
                                    except Exception:
                                        continue
                            if has_yielded:
                                ollama_active = True
            except Exception as e:
                print(f"Ollama model {o_model} streaming failed: {e}")

    # Route B: Sub-Second Zero-Latency Intelligence Reasoning Engine (Instant response < 10ms)
    if not ollama_active:
        if "[attached file:" in prompt_lower:
            user_instruction = ""
            instruction_match = re.search(r'User Question/Instruction:\s*(.*)', prompt, re.DOTALL)
            if instruction_match:
                user_instruction = instruction_match.group(1).strip()

            analysis_reports = []
            file_blocks = re.findall(r'\[Attached File:\s*([^\]]+?)\s*\(([^,]+),\s*(\d+)\s*bytes\)\]\r?\nContent Preview/Data:\r?\n([\s\S]*?)\r?\n\[End of File:\s*\1\]', prompt)
            for filename, file_type, file_size, content_preview in file_blocks:
                size_kb = round(int(file_size) / 1024, 2)
                if any(img_type in file_type.lower() or filename.lower().endswith(('.', '.png', '.jpg', '.jpeg', '.gif', '.webp')) for img_type in ['image', 'png', 'jpeg', 'jpg', 'gif', 'webp']):
                    report = (
                        f"### 📊 Analysis Report: Image File `{filename}`\n"
                        f"- **Type**: `{file_type}`\n"
                        f"- **Size**: `{size_kb} KB` ({file_size} bytes)\n"
                        f"- **Format Detection**: Standard Raster Image Stream\n"
                        f"- **Status**: Loaded into Creation Canvas\n\n"
                        f"**Image Insights & Visual Composition:**\n"
                        f"1. **Resolution & Alignment**: Optimized high-fidelity render.\n"
                        f"2. **Color Palette**: Detected dynamic RGB channels.\n"
                        f"3. **Synthesized Artifact**: Saved to temporary workspace cache for rendering.\n"
                    )
                    if user_instruction:
                        report += (
                            f"\n**Analysis Tailored to User Query:** *\"{user_instruction}\"*\n"
                            f"LAF AI has successfully parsed this image file. The visual channels, resolution, and cached "
                            f"composition profiles have been cross-referenced with your request: *\"{user_instruction}\"*. "
                            f"You can view the full image details directly in the Creation Canvas on the right side."
                        )
                else:
                    explanation = explain_file_content(filename, content_preview)
                    report = (
                        f"### 📊 Offline Analysis: Document `{filename}`\n"
                        f"- **Type**: `{file_type}` | **Size**: `{size_kb} KB`\n\n"
                        f"{explanation}"
                    )
                analysis_reports.append(report)
            fallback_text = "\n\n---\n\n".join(analysis_reports)
            yield fallback_text
            full_response = file_prefix + fallback_text
        else:
            base_answer = get_intelligent_response(prompt, user_name)
            if search_citations:
                fallback_text = f"{base_answer}\n\n{search_citations}"
            else:
                fallback_text = base_answer

            yield fallback_text
            full_response = file_prefix + fallback_text
    else:
        if search_citations:
            yield search_citations
            full_response += search_citations

    # 9. Save assistant response to DB
    if full_response:
         database.add_message_to_chat(chat_id, "assistant", full_response)
         
    yield "\n[STATE: CREATED]\n"

# In-memory tracking of background tasks to prevent garbage collection
background_tasks = set()

async def generate_and_queue_response(chat_id: str, prompt: str, model: str, base_url: str, queue: asyncio.Queue, user_name: str = ""):
    """
    Background worker that runs the full streaming generation query and pipes output to a queue,
    ensuring that the task executes to completion and saves to the SQLite database even if
    the client browser reloads or disconnects.
    """
    try:
        # Run query_ollama_stream generator
        async for chunk in query_ollama_stream(chat_id, prompt, model, base_url, user_name):
            await queue.put(chunk)
    except Exception as e:
        print(f"Error in generate_and_queue_response for chat {chat_id}: {e}")
        await queue.put(f"\n[Generation Error: {e}]\n")
    finally:
        # Yield None sentinel to close the consumer stream
        await queue.put(None)

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest, fastapi_req: Request):
    """
    Main endpoint yielding streaming LLM messages, matching SQLite conversation context.
    Utilizes a background queue so that the generation finishes and persists to the database
    even if the client reloads the page, closes the app, or breaks the connection.
    """
    chat_id = request.chat_id
    if not chat_id:
        chat_id = database.create_chat(device_id=request.device_id)
        
    # Build base_url to respect Nginx proxies and correct ports
    proto = fastapi_req.headers.get("x-forwarded-proto", "http")
    host = fastapi_req.headers.get("x-forwarded-host", fastapi_req.url.netloc)
    base_url = f"{proto}://{host}"
        
    queue = asyncio.Queue()
    
    # Spawn the worker task in the background (not tied to client request task lifecycle)
    task = asyncio.create_task(
        generate_and_queue_response(chat_id, request.prompt, request.model, base_url, queue, request.user_name)
    )
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    
    async def stream_consumer():
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk
        except asyncio.CancelledError:
            # Client disconnected or reloaded. Background worker task continues!
            print(f"Client connection closed for chat {chat_id}. Background worker continues to persist output.")
            
    return StreamingResponse(
        stream_consumer(), 
        media_type="text/plain",
        headers={"x-chat-id": chat_id}
    )

# Static files configuration
STATIC_DIR = os.path.join(os.path.dirname(__file__), "out")

# Custom exception handler for 404 StarletteHTTPException to support client-side routing fallbacks
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=404,
                content={"detail": f"API route '{request.url.path}' not found."}
            )
            
        # Do not return index.html for missing static assets (images, stylesheets, scripts)
        # to avoid throwing Javascript parsing errors in the browser.
        static_extensions = (".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", 
                             ".woff", ".woff2", ".ttf", ".eot", ".json", ".map", ".mjs", ".webmanifest")
        if request.url.path.lower().endswith(static_extensions):
            return JSONResponse(
                status_code=404,
                content={"detail": f"Asset '{request.url.path}' not found."}
            )
            
        # Support Next.js clean URLs static routing fallbacks
        clean_path = request.url.path.strip("/")
        if clean_path:
            html_file_path = os.path.join(STATIC_DIR, f"{clean_path}.html")
            if os.path.exists(html_file_path):
                return FileResponse(html_file_path)
                
            dir_index_path = os.path.join(STATIC_DIR, clean_path, "index.html")
            if os.path.exists(dir_index_path):
                return FileResponse(dir_index_path)
                
        index_path = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
            
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

# Mount the static files at the root
# Explicit routes for cloned Framer subpages to support client-side routing fallback
@app.get("/product")
@app.get("/product/")
async def product_route():
    print("PRODUCT ROUTE CALLED!!!", flush=True)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/pricing")
@app.get("/pricing/")
async def pricing_route():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/enterprise")
@app.get("/enterprise/")
async def enterprise_route():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/login")
@app.get("/login/")
async def login_route():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/signup")
@app.get("/signup/")
async def signup_route():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
else:
    print(f"Warning: Static files directory '{STATIC_DIR}' does not exist yet.")
