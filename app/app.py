"""
Flask API backend for the AWS Network Firewall Automation Agent.
Provides REST endpoints for chat, agent discovery, and session management.
Integrates with Amazon Cognito for authentication via ALB headers.
"""

import json
import logging
import os
import uuid

import boto3
from botocore.config import Config
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static", static_url_path="/static")

# Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BOTO_CONFIG = Config(read_timeout=900, connect_timeout=60)


# --- Authentication ---

def get_current_user():
    """
    Extract user identity from ALB + Cognito auth headers.
    In production, ALB injects these headers after Cognito authentication.
    In local dev, returns a default user.
    """
    # ALB-injected headers when Cognito auth is enabled
    user_claims = request.headers.get("x-amzn-oidc-data")
    user_email = request.headers.get("x-amzn-oidc-identity")

    if user_email:
        return {"email": user_email, "authenticated": True}

    # Local development fallback
    if os.getenv("FLASK_ENV") == "development" or os.getenv("LOCAL_DEV") == "true":
        return {"email": "local-dev@example.com", "authenticated": False}

    return None


# --- API Routes ---

@app.route("/")
def index():
    """Serve the main HTML page"""
    return send_from_directory("static", "index.html")


@app.route("/health")
def health():
    """Health check endpoint for ALB/ECS"""
    return jsonify({"status": "healthy"}), 200


@app.route("/api/user", methods=["GET"])
def get_user():
    """Return current authenticated user info"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(user)


@app.route("/api/agents", methods=["GET"])
def list_agents():
    """Fetch available agent runtimes from Bedrock AgentCore"""
    region = request.args.get("region", AWS_REGION)
    try:
        client = boto3.client("bedrock-agentcore-control", region_name=region, config=BOTO_CONFIG)
        response = client.list_agent_runtimes(maxResults=100)

        ready_agents = [
            {
                "name": agent.get("agentRuntimeName", "Unknown"),
                "id": agent.get("agentRuntimeId", ""),
                "status": agent.get("status", ""),
                "lastUpdatedAt": agent.get("lastUpdatedAt", "").isoformat()
                if hasattr(agent.get("lastUpdatedAt", ""), "isoformat")
                else str(agent.get("lastUpdatedAt", "")),
            }
            for agent in response.get("agentRuntimes", [])
            if agent.get("status") == "READY"
        ]

        ready_agents.sort(key=lambda x: x.get("lastUpdatedAt", ""), reverse=True)
        return jsonify({"agents": ready_agents})

    except Exception as e:
        logger.error(f"Error fetching agents: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/<agent_runtime_id>/versions", methods=["GET"])
def list_agent_versions(agent_runtime_id):
    """Fetch versions for a specific agent runtime"""
    region = request.args.get("region", AWS_REGION)
    try:
        client = boto3.client("bedrock-agentcore-control", region_name=region, config=BOTO_CONFIG)
        response = client.list_agent_runtime_versions(
            agentRuntimeId=agent_runtime_id, maxResults=100
        )

        ready_versions = [
            {
                "version": v.get("agentRuntimeVersion", ""),
                "arn": v.get("agentRuntimeArn", ""),
                "description": v.get("description", ""),
                "lastUpdatedAt": v.get("lastUpdatedAt", "").isoformat()
                if hasattr(v.get("lastUpdatedAt", ""), "isoformat")
                else str(v.get("lastUpdatedAt", "")),
            }
            for v in response.get("agentRuntimes", [])
            if v.get("status") == "READY"
        ]

        ready_versions.sort(key=lambda x: x.get("lastUpdatedAt", ""), reverse=True)
        return jsonify({"versions": ready_versions})

    except Exception as e:
        logger.error(f"Error fetching versions: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions", methods=["POST"])
def create_session():
    """Generate a new session ID"""
    return jsonify({"sessionId": str(uuid.uuid4())})


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Send a message to the agent and stream the response.
    Returns Server-Sent Events (SSE) for real-time streaming.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    prompt = data.get("prompt", "").strip()
    agent_arn = data.get("agentArn", "")
    session_id = data.get("sessionId", str(uuid.uuid4()))
    region = data.get("region", AWS_REGION)

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    if not agent_arn:
        return jsonify({"error": "agentArn is required"}), 400

    def generate():
        try:
            client = boto3.client("bedrock-agentcore", region_name=region, config=BOTO_CONFIG)

            boto3_response = client.invoke_agent_runtime(
                agentRuntimeArn=agent_arn,
                qualifier="DEFAULT",
                runtimeSessionId=session_id,
                payload=json.dumps({"prompt": prompt}),
            )

            content_type = boto3_response.get("contentType", "")

            if "text/event-stream" in content_type:
                for line in boto3_response["response"].iter_lines(chunk_size=1):
                    if line:
                        line = line.decode("utf-8")
                        if line.startswith("data: "):
                            chunk_data = line[6:]
                            parsed = _parse_chunk(chunk_data)
                            if parsed.strip():
                                yield f"data: {json.dumps({'text': parsed})}\n\n"
            else:
                # Non-streaming response
                response_obj = boto3_response.get("response")
                if hasattr(response_obj, "read"):
                    content = response_obj.read()
                    if isinstance(content, bytes):
                        content = content.decode("utf-8")
                    parsed = _parse_chunk(content)
                    yield f"data: {json.dumps({'text': parsed})}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            logger.error(f"Error in chat stream: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _parse_chunk(chunk: str) -> str:
    """Parse a response chunk and extract text content"""
    try:
        if chunk.strip().startswith("{"):
            data = json.loads(chunk)
            if isinstance(data, dict):
                if "role" in data and "content" in data:
                    content = data["content"]
                    if isinstance(content, list) and len(content) > 0:
                        first_item = content[0]
                        if isinstance(first_item, dict) and "text" in first_item:
                            return first_item["text"]
                        return str(first_item)
                    return str(content)
                if "text" in data:
                    return str(data["text"])
                if "result" in data:
                    result = data["result"]
                    if isinstance(result, dict):
                        return _parse_chunk(json.dumps(result))
                    return str(result)
            return str(data)
    except json.JSONDecodeError:
        pass
    return chunk


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8501"))
    debug = os.getenv("FLASK_ENV") == "development" or os.getenv("LOCAL_DEV") == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
