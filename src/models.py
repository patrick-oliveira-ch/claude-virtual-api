"""Pydantic models for Claude API compatibility."""
from typing import Optional, Literal, Union
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


# --- Request Models ---

class ContentBlockText(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ContentBlockImage(BaseModel):
    type: Literal["image"] = "image"
    source: dict


ContentBlock = Union[ContentBlockText, ContentBlockImage, str]


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: Union[str, list[ContentBlock]]


class MessagesRequest(BaseModel):
    model: str
    messages: list[Message]
    max_tokens: int = 4096
    system: Optional[str] = None
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    stop_sequences: Optional[list[str]] = None
    stream: bool = False
    metadata: Optional[dict] = None


class CountTokensRequest(BaseModel):
    model: str
    messages: list[Message]
    system: Optional[str] = None


class BatchRequest(BaseModel):
    custom_id: str
    params: MessagesRequest


class CreateBatchRequest(BaseModel):
    requests: list[BatchRequest]


# --- Response Models ---

class Usage(BaseModel):
    input_tokens: int
    output_tokens: int


class ContentBlockResponse(BaseModel):
    type: Literal["text"] = "text"
    text: str


class MessagesResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:24]}")
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    content: list[ContentBlockResponse]
    model: str
    stop_reason: Optional[Literal["end_turn", "max_tokens", "stop_sequence"]] = "end_turn"
    stop_sequence: Optional[str] = None
    usage: Usage


class CountTokensResponse(BaseModel):
    input_tokens: int


class ModelInfo(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    owned_by: str = "anthropic"
    display_name: str
    type: Literal["model"] = "model"


class ModelsListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelInfo]


class BatchInfo(BaseModel):
    id: str
    type: Literal["message_batch"] = "message_batch"
    processing_status: Literal["in_progress", "ended", "canceling"]
    request_counts: dict
    created_at: str
    ended_at: Optional[str] = None
    expires_at: str
    results_url: Optional[str] = None


class ErrorResponse(BaseModel):
    type: Literal["error"] = "error"
    error: dict


# --- Streaming Models ---

class StreamEvent(BaseModel):
    type: str
    index: Optional[int] = None
    content_block: Optional[dict] = None
    delta: Optional[dict] = None
    message: Optional[dict] = None
    usage: Optional[dict] = None
