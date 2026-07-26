import uvicorn
import sys
import os

def main():
    print("Starting LAF API server on port 5001...")
    reload_opt = os.getenv("RELOAD", "false").lower() == "true"
    uvicorn.run("backend.main:app", host="0.0.0.0", port=5001, reload=reload_opt)

if __name__ == "__main__":
    main()
