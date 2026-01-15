"""Claude Virtual API Server - All endpoints."""
import uuid
from datetime import datetime, timedelta
from typing import Optional
import json

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import tiktoken

from .models import (
    MessagesRequest, MessagesResponse, ContentBlockResponse, Usage,
    CountTokensRequest, CountTokensResponse,
    CreateBatchRequest, BatchInfo,
    ModelInfo, ModelsListResponse,
    ErrorResponse
)
from .claude_bridge import claude_bridge

app = FastAPI(
    title="Claude Virtual API",
    description="Local API server that proxies requests to Claude Code CLI",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for batches and files
batches: dict[str, dict] = {}
files: dict[str, dict] = {}

# Available models (mapped to Claude Code supported models)
AVAILABLE_MODELS = [
    ModelInfo(id="claude-opus-4-5-20251101", display_name="Claude Opus 4.5"),
    ModelInfo(id="claude-sonnet-4-5-20251101", display_name="Claude Sonnet 4.5"),
    ModelInfo(id="claude-3-5-sonnet-20241022", display_name="Claude 3.5 Sonnet"),
    ModelInfo(id="claude-3-5-haiku-20241022", display_name="Claude 3.5 Haiku"),
    ModelInfo(id="claude-3-opus-20240229", display_name="Claude 3 Opus"),
    ModelInfo(id="claude-3-sonnet-20240229", display_name="Claude 3 Sonnet"),
    ModelInfo(id="claude-3-haiku-20240307", display_name="Claude 3 Haiku"),
]


def validate_api_key(x_api_key: Optional[str]) -> bool:
    """Validate API key (accepts any non-empty key for local use)."""
    return bool(x_api_key)


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Count tokens using tiktoken."""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        return len(text.split())


# --- Health Endpoint ---

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Claude Virtual API",
        "version": "1.0.0",
        "description": "Local proxy to Claude Code CLI",
        "endpoints": {
            "messages": "POST /v1/messages",
            "models": "GET /v1/models",
            "count_tokens": "POST /v1/messages/count_tokens",
            "batches": "POST /v1/messages/batches",
            "files": "POST /v1/files",
            "health": "GET /health"
        }
    }


# --- Messages API ---

@app.post("/v1/messages")
async def create_message(
    request: MessagesRequest,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
    anthropic_version: Optional[str] = Header(None, alias="anthropic-version")
):
    """Create a message (main endpoint)."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    messages = [msg.model_dump() for msg in request.messages]

    if request.stream:
        async def stream_response():
            async for event in claude_bridge.send_message_stream(
                messages=messages,
                model=request.model,
                system=request.system,
                max_tokens=request.max_tokens
            ):
                yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    result = await claude_bridge.send_message(
        messages=messages,
        model=request.model,
        system=request.system,
        max_tokens=request.max_tokens
    )

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result.get("message"))

    content_text = result.get("content", "")
    if isinstance(content_text, dict):
        content_text = content_text.get("text", str(content_text))

    input_tokens = sum(count_tokens(str(msg.get("content", ""))) for msg in messages)
    output_tokens = count_tokens(str(content_text))

    return MessagesResponse(
        content=[ContentBlockResponse(text=str(content_text))],
        model=request.model,
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens)
    )


# --- Token Counting ---

@app.post("/v1/messages/count_tokens")
async def count_message_tokens(
    request: CountTokensRequest,
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    """Count tokens in messages."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    total_tokens = 0
    if request.system:
        total_tokens += count_tokens(request.system)

    for msg in request.messages:
        content = msg.content
        if isinstance(content, str):
            total_tokens += count_tokens(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, str):
                    total_tokens += count_tokens(block)
                elif hasattr(block, "text"):
                    total_tokens += count_tokens(block.text)

    return CountTokensResponse(input_tokens=total_tokens)


# --- Models API ---

@app.get("/v1/models")
async def list_models(
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    """List available models."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    return ModelsListResponse(data=AVAILABLE_MODELS)


@app.get("/v1/models/{model_id}")
async def get_model(
    model_id: str,
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    """Get a specific model."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    for model in AVAILABLE_MODELS:
        if model.id == model_id:
            return model

    raise HTTPException(status_code=404, detail=f"Model {model_id} not found")


# --- Batches API ---

@app.post("/v1/messages/batches")
async def create_batch(
    request: CreateBatchRequest,
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    """Create a message batch."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    batch_id = f"batch_{uuid.uuid4().hex[:24]}"
    now = datetime.now()

    batch = {
        "id": batch_id,
        "type": "message_batch",
        "processing_status": "in_progress",
        "request_counts": {
            "processing": len(request.requests),
            "succeeded": 0,
            "errored": 0,
            "canceled": 0,
            "expired": 0
        },
        "created_at": now.isoformat(),
        "ended_at": None,
        "expires_at": (now + timedelta(days=1)).isoformat(),
        "results_url": None,
        "requests": [r.model_dump() for r in request.requests],
        "results": []
    }

    batches[batch_id] = batch
    return BatchInfo(**{k: v for k, v in batch.items() if k not in ["requests", "results"]})


@app.get("/v1/messages/batches")
async def list_batches(
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
    limit: int = 20
):
    """List all batches."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    batch_list = [
        BatchInfo(**{k: v for k, v in b.items() if k not in ["requests", "results"]})
        for b in list(batches.values())[:limit]
    ]
    return {"object": "list", "data": batch_list}


@app.get("/v1/messages/batches/{batch_id}")
async def get_batch(
    batch_id: str,
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    """Get a specific batch."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    if batch_id not in batches:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

    batch = batches[batch_id]
    return BatchInfo(**{k: v for k, v in batch.items() if k not in ["requests", "results"]})


@app.delete("/v1/messages/batches/{batch_id}")
async def cancel_batch(
    batch_id: str,
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    """Cancel a batch."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    if batch_id not in batches:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

    batches[batch_id]["processing_status"] = "canceling"
    batch = batches[batch_id]
    return BatchInfo(**{k: v for k, v in batch.items() if k not in ["requests", "results"]})


@app.get("/v1/messages/batches/{batch_id}/results")
async def get_batch_results(
    batch_id: str,
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    """Get batch results."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    if batch_id not in batches:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

    return {"batch_id": batch_id, "results": batches[batch_id].get("results", [])}


# --- Files API (Beta) ---

@app.post("/v1/files")
async def upload_file(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    """Upload a file."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    file_id = f"file_{uuid.uuid4().hex[:24]}"
    body = await request.body()

    file_info = {
        "id": file_id,
        "object": "file",
        "bytes": len(body),
        "created_at": int(datetime.now().timestamp()),
        "filename": "uploaded_file",
        "purpose": "assistants",
        "content": body
    }

    files[file_id] = file_info
    return {k: v for k, v in file_info.items() if k != "content"}


@app.get("/v1/files")
async def list_files(
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    """List all files."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    file_list = [{k: v for k, v in f.items() if k != "content"} for f in files.values()]
    return {"object": "list", "data": file_list}


@app.get("/v1/files/{file_id}")
async def get_file(
    file_id: str,
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    """Get file info."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    if file_id not in files:
        raise HTTPException(status_code=404, detail=f"File {file_id} not found")

    return {k: v for k, v in files[file_id].items() if k != "content"}


@app.delete("/v1/files/{file_id}")
async def delete_file(
    file_id: str,
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    """Delete a file."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    if file_id not in files:
        raise HTTPException(status_code=404, detail=f"File {file_id} not found")

    del files[file_id]
    return {"id": file_id, "object": "file", "deleted": True}


# --- Admin API (simplified) ---

@app.get("/v1/organizations/me")
async def get_organization(
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    """Get organization info."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    return {
        "id": "org_local",
        "name": "Local Virtual API",
        "type": "organization"
    }


@app.get("/v1/organizations/usage_report/messages")
async def get_usage_report(
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    """Get usage report."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    return {
        "object": "usage_report",
        "data": [],
        "has_more": False
    }


@app.get("/v1/organizations/cost_report")
async def get_cost_report(
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    """Get cost report."""
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    return {
        "object": "cost_report",
        "total_cost_usd": 0.0,
        "data": []
    }


# --- Error handler ---

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions in Claude API format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": "error",
            "error": {
                "type": "api_error" if exc.status_code >= 500 else "invalid_request_error",
                "message": exc.detail
            }
        }
    )
