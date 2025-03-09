import argparse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = FastAPI()

# Update CORS to allow localhost:8080
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AgentRequest(BaseModel):
    connection: str
    action: str
    params: list

class ChatMessage(BaseModel):
    message: str

@app.get("/agents")
async def list_agents():
    logging.info("Agent list requested")
    return {"agents": ["event-planner", "social-media"]}    

@app.post("/agent/action")
async def agent_action(request: AgentRequest):
    logging.info(f"Agent Action: {request.action} on {request.connection}")
    return {
        "status": "success",
        "result": f"Processed {request.action} via {request.connection}"
    }

@app.post("/chat")
async def chat(message: ChatMessage):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{timestamp}] Received from frontend: {message.message}")
    print("-" * 50)
    return {"response": f"Server received: {message.message}"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ZerePy - AI Agent Framework')
    parser.add_argument('--server', action='store_true', help='Run in server mode')
    parser.add_argument('--host', default='0.0.0.0', help='Server host')
    parser.add_argument('--port', type=int, default=8000, help='Server port')  
    args = parser.parse_args()

    if args.server:
        print(f"Server starting on port {args.port} - Messages from frontend will appear below:")
        print("=" * 50)
        uvicorn.run(
            "main:app",
            host=args.host,
            port=args.port,
            reload=True
        )
    else:
        from src.cli import ZerePyCLI
        cli = ZerePyCLI()
        cli.main_loop()