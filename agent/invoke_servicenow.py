#!/usr/bin/env python3
"""Invoke the deployed AgentCore runtime with a ServiceNow prompt and print the response."""
import json
import sys
import uuid
import boto3

REGION = "us-east-1"
RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-east-1:868287237678:runtime/firewall_automation_agent-rDUSNID5PX"

prompt = sys.argv[1] if len(sys.argv) > 1 else "List the 5 most recent ServiceNow change requests."

client = boto3.client("bedrock-agentcore", region_name=REGION)

print(f"PROMPT: {prompt}\n" + "=" * 64)

resp = client.invoke_agent_runtime(
    agentRuntimeArn=RUNTIME_ARN,
    runtimeSessionId=uuid.uuid4().hex + uuid.uuid4().hex,  # >=33 chars
    payload=json.dumps({"prompt": prompt}).encode("utf-8"),
    contentType="application/json",
    accept="application/json",
)

ct = resp.get("contentType", "")
body = resp.get("response")

# Case 1: streaming EventStream
if hasattr(body, "iter_chunks") or hasattr(body, "__iter__") and not isinstance(body, (bytes, bytearray)):
    try:
        for event in body:
            if isinstance(event, (bytes, bytearray)):
                sys.stdout.write(event.decode("utf-8", "replace"))
            elif isinstance(event, dict):
                chunk = event.get("chunk", {}).get("bytes") or event.get("bytes")
                if chunk:
                    sys.stdout.write(chunk.decode("utf-8", "replace"))
            sys.stdout.flush()
        print()
        sys.exit(0)
    except TypeError:
        pass

# Case 2: StreamingBody / bytes
if hasattr(body, "read"):
    data = body.read()
    print(data.decode("utf-8", "replace"))
elif isinstance(body, (bytes, bytearray)):
    print(body.decode("utf-8", "replace"))
else:
    print(repr(body))
