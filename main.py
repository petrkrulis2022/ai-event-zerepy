import argparse
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
import json
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = FastAPI()

# Update CORS to allow requests from any origin during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In development, allow all origins
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

class EventSubmission(BaseModel):
    content: dict

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
    logging.info(f"Received message at {timestamp}: {message.message}")
    print(f"\n[{timestamp}] Received from frontend: {message.message}")
    print("-" * 50)
    return {"response": f"Server received: {message.message}"}

@app.post("/api/message")
async def api_message(request: EventSubmission):
    """
    This is the endpoint that Event Symphony's frontend is trying to reach.
    It needs to process various message types and return appropriate responses.
    """
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

# Health check endpoint
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

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
