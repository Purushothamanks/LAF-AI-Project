import uvicorn
import sys

def main():
    print("Starting LAF API server on port 5001...")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=5001, reload=True)

if __name__ == "__main__":
    main()
