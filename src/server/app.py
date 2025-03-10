from fastapi import FastAPI, HTTPException, BackgroundTasks
import time
import json
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import asyncio
import signal
import threading
from pathlib import Path
from src.cli import ZerePyCLI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server/app")

class ActionRequest(BaseModel):
    """Request model for agent actions"""
    connection: str
    action: str
    params: Optional[List[str]] = []

class ConfigureRequest(BaseModel):
    """Request model for configuring connections"""
    connection: str
    params: Optional[Dict[str, Any]] = {}

class EventSubmission(BaseModel):
    """Request model for agent messages"""
    content: Dict[str, Any]

class ServerState:
    """Simple state management for the server"""
    def __init__(self):
        self.cli = ZerePyCLI()
        self.agent_running = False
        self.agent_task = None
        self._stop_event = threading.Event()

    def _run_agent_loop(self):
        """Run agent loop in a separate thread"""
        try:
            log_once = False
            while not self._stop_event.is_set():
                if self.cli.agent:
                    try:
                        if not log_once:
                            logger.info("Loop logic not implemented")
                            log_once = True

                    except Exception as e:
                        logger.error(f"Error in agent action: {e}")
                        if self._stop_event.wait(timeout=30):
                            break
        except Exception as e:
            logger.error(f"Error in agent loop thread: {e}")
        finally:
            self.agent_running = False
            logger.info("Agent loop stopped")

    async def start_agent_loop(self):
        """Start the agent loop in background thread"""
        if not self.cli.agent:
            raise ValueError("No agent loaded")
        
        if self.agent_running:
            raise ValueError("Agent already running")

        self.agent_running = True
        self._stop_event.clear()
        self.agent_task = threading.Thread(target=self._run_agent_loop)
        self.agent_task.start()

    async def stop_agent_loop(self):
        """Stop the agent loop"""
        if self.agent_running:
            self._stop_event.set()
            if self.agent_task:
                self.agent_task.join(timeout=5)
            self.agent_running = False

class ZerePyServer:
    def __init__(self):
        self.app = FastAPI(title="ZerePy Server")
        self.state = ServerState()
        self.setup_routes()

    def setup_routes(self):
        @self.app.get("/")
        async def root():
            """Server status endpoint"""
            return {
                "status": "running",
                "agent": self.state.cli.agent.name if self.state.cli.agent else None,
                "agent_running": self.state.agent_running
            }

        @self.app.get("/agents")
        async def list_agents():
            """List available agents"""
            try:
                agents = []
                agents_dir = Path("agents")
                if agents_dir.exists():
                    for agent_file in agents_dir.glob("*.json"):
                        if agent_file.stem != "general":
                            agents.append(agent_file.stem)
                return {"agents": agents}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/agents/{name}/load")
        async def load_agent(name: str):
            """Load a specific agent"""
            try:
                self.state.cli._load_agent_from_file(name)
                return {
                    "status": "success",
                    "agent": name
                }
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/connections")
        async def list_connections():
            """List all available connections"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                connections = {}
                for name, conn in self.state.cli.agent.connection_manager.connections.items():
                    connections[name] = {
                        "configured": conn.is_configured(),
                        "is_llm_provider": conn.is_llm_provider
                    }
                return {"connections": connections}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/agent/action")
        async def agent_action(action_request: ActionRequest):
            """Execute a single agent action"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                result = await asyncio.to_thread(
                    self.state.cli.agent.perform_action,
                    connection=action_request.connection,
                    action=action_request.action,
                    params=action_request.params
                )
                return {"status": "success", "result": result}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/agent/start")
        async def start_agent():
            """Start the agent loop"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                await self.state.start_agent_loop()
                return {"status": "success", "message": "Agent loop started"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/agent/stop")
        async def stop_agent():
            """Stop the agent loop"""
            try:
                await self.state.stop_agent_loop()
                return {"status": "success", "message": "Agent loop stopped"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.post("/connections/{name}/configure")
        async def configure_connection(name: str, config: ConfigureRequest):
            """Configure a specific connection"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
            
            try:
                connection = self.state.cli.agent.connection_manager.connections.get(name)
                if not connection:
                    raise HTTPException(status_code=404, detail=f"Connection {name} not found")
                
                success = connection.configure(**config.params)
                if success:
                    return {"status": "success", "message": f"Connection {name} configured successfully"}
                else:
                    raise HTTPException(status_code=400, detail=f"Failed to configure {name}")
                    
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/connections/{name}/status")
        async def connection_status(name: str):
            """Get configuration status of a connection"""
            if not self.state.cli.agent:
                raise HTTPException(status_code=400, detail="No agent loaded")
                
            try:
                connection = self.state.cli.agent.connection_manager.connections.get(name)
                if not connection:
                    raise HTTPException(status_code=404, detail=f"Connection {name} not found")
                    
                return {
                    "name": name,
                    "configured": connection.is_configured(verbose=True),
                    "is_llm_provider": connection.is_llm_provider
                }
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/message")
        async def api_message(request: EventSubmission):
            """Handle agent messages"""
            try:
                content = request.content
                message_type = content.get("type")
                logging.info(f"Received agent message of type: {message_type}")
                print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Received agent message: {json.dumps(content, indent=2)}")
                
                # Base response structure
                response = {
                    "response": f"Successfully processed {message_type} request!"
                }
                
                # Handle different message types
                if message_type == "event_submission":
                    event_data = content.get("event_data", {})
                    event_name = event_data.get("eventName", "Unnamed Event")
                    logging.info(f"Processing event submission for: {event_name}")
                    
                    response = {
                        "response": f"Thank you for submitting your event: {event_name}! I'll help you organize it.",
                        "event_received": True,
                        "agent_wallet": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
                        "next_steps": [
                            "Search for venues near your location",
                            "Promote your event on Twitter and Warpcast",
                            "Transfer budget for event management"
                        ]
                    }
                    
                elif message_type == "venue_search":
                    response = {
                        "response": "I found several potential venues for your event.",
                        "venues": [
                            {
                                "name": "Blockchain Conference Center",
                                "description": "Perfect venue for tech events with capacity for 500 attendees",
                                "link": "https://example.com/venue1"
                            },
                            {
                                "name": "Crypto Convention Hall",
                                "description": "Modern space with advanced AV equipment and flexible layout",
                                "link": "https://example.com/venue2"
                            },
                            {
                                "name": "Web3 Workshop Space",
                                "description": "Intimate setting ideal for focused workshops and smaller gatherings",
                                "link": "https://example.com/venue3"
                            }
                        ],
                        "emails_sent": True
                    }
                    
                elif message_type == "social_promotion":
                    platforms = content.get("platforms", ["Twitter", "Warpcast"])
                    response = {
                        "response": f"I've promoted your event on {', '.join(platforms)}!",
                        "post_content": "Exciting new crypto event coming soon! Join us for discussions on blockchain, AI, and the future of tech. #blockchain #crypto #ethereum #ai",
                        "platforms": platforms,
                        "twitter_post_url": "https://twitter.com/Eth202541789/status/1234567890",
                        "warpcast_post_url": "https://warpcast.com/beerslothcoder/0x1234"
                    }
                    
                elif message_type == "budget_transfer":
                    response = {
                        "response": "Thank you for transferring CORAL for your event budget.",
                        "transaction_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                        "explorer_link": "https://explorer.sonic.zkevm.io/tx/0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
                    }
                    
                elif message_type == "custom_message":
                    user_message = content.get("message", "")
                    response["response"] = f"I received your message: '{user_message}'. How can I help with your event?"
                
                print(f"Sending response: {json.dumps(response, indent=2)}")
                return {"content": response}
                
            except Exception as e:
                logging.error(f"Error processing agent message: {str(e)}")
                return {
                    "content": {
                        "response": f"Error processing your request: {str(e)}",
                        "error": True
                    }
                }

def create_app():
    server = ZerePyServer()
    return server.app