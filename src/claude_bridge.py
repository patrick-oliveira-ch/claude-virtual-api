"""Bridge to Claude Code CLI."""
import subprocess
import json
import asyncio
from typing import AsyncGenerator, Optional
import uuid
import sys


# Model mapping: API model names to Claude Code CLI model names
MODEL_MAPPING = {
    "claude-opus-4-5-20251101": "opus",
    "claude-sonnet-4-5-20251101": "sonnet",
    "claude-3-5-sonnet-20241022": "sonnet",
    "claude-3-5-haiku-20241022": "haiku",
    "claude-3-opus-20240229": "opus",
    "claude-3-sonnet-20240229": "sonnet",
    "claude-3-haiku-20240307": "haiku",
    # Short names
    "opus": "opus",
    "sonnet": "sonnet",
    "haiku": "haiku",
}


class ClaudeBridge:
    """Handles communication with Claude Code CLI."""

    def __init__(self):
        self.sessions: dict[str, str] = {}

    def _map_model(self, model: str) -> str:
        """Map API model name to CLI model name."""
        return MODEL_MAPPING.get(model, "sonnet")

    def _build_command(
        self,
        prompt: str,
        output_format: str = "json",
        session_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> list[str]:
        """Build the claude CLI command."""
        cmd = ["claude", "-p", prompt, "--output-format", output_format]

        if session_id:
            cmd.extend(["--session-id", session_id])

        if model:
            mapped_model = self._map_model(model)
            cmd.extend(["--model", mapped_model])

        return cmd

    def _format_messages_as_prompt(self, messages: list[dict], system: Optional[str] = None) -> str:
        """Convert API messages format to a prompt string."""
        parts = []

        if system:
            parts.append(f"[System: {system}]")

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, str):
                        text_parts.append(block)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                content = "\n".join(text_parts)

            if role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")

        return "\n\n".join(parts)

    async def send_message(
        self,
        messages: list[dict],
        model: str,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        session_id: Optional[str] = None
    ) -> dict:
        """Send a message and get response (non-streaming)."""
        prompt = self._format_messages_as_prompt(messages, system)
        cmd = self._build_command(prompt, "json", session_id, model)

        print(f"[ClaudeBridge] Executing: {' '.join(cmd[:4])}...", file=sys.stderr)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            print(f"[ClaudeBridge] Return code: {process.returncode}", file=sys.stderr)

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                print(f"[ClaudeBridge] Error: {error_msg}", file=sys.stderr)
                return {
                    "error": True,
                    "message": error_msg
                }

            output = stdout.decode().strip()
            print(f"[ClaudeBridge] Output length: {len(output)}", file=sys.stderr)

            try:
                result = json.loads(output)
                content = result.get("result", "")
                print(f"[ClaudeBridge] Success, content length: {len(str(content))}", file=sys.stderr)
                return {
                    "error": False,
                    "content": content,
                    "session_id": result.get("session_id"),
                    "cost_usd": result.get("total_cost_usd", 0),
                    "duration_ms": result.get("duration_ms", 0),
                    "usage": result.get("usage", {})
                }
            except json.JSONDecodeError as e:
                print(f"[ClaudeBridge] JSON decode error: {e}", file=sys.stderr)
                return {
                    "error": False,
                    "content": output,
                    "session_id": None
                }

        except FileNotFoundError:
            print("[ClaudeBridge] CLI not found", file=sys.stderr)
            return {
                "error": True,
                "message": "Claude Code CLI not found. Please install it first."
            }
        except Exception as e:
            print(f"[ClaudeBridge] Exception: {e}", file=sys.stderr)
            return {
                "error": True,
                "message": str(e)
            }

    async def send_message_stream(
        self,
        messages: list[dict],
        model: str,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        session_id: Optional[str] = None
    ) -> AsyncGenerator[dict, None]:
        """Send a message and stream the response."""
        prompt = self._format_messages_as_prompt(messages, system)

        # Build command with --verbose for stream-json
        mapped_model = self._map_model(model)
        cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose"]
        if session_id:
            cmd.extend(["--session-id", session_id])
        if model:
            cmd.extend(["--model", mapped_model])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            message_id = f"msg_{uuid.uuid4().hex[:24]}"

            yield {
                "type": "message_start",
                "message": {
                    "id": message_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": model,
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0}
                }
            }

            yield {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""}
            }

            buffer = ""
            output_tokens = 0
            async for line in process.stdout:
                decoded = line.decode().strip()
                if not decoded:
                    continue

                try:
                    event = json.loads(decoded)
                    event_type = event.get("type", "")

                    if event_type == "assistant":
                        # Extract text from message.content[0].text
                        msg = event.get("message", {})
                        content = msg.get("content", [])
                        if content and len(content) > 0:
                            text = content[0].get("text", "")
                            if text and text != buffer:
                                # Send only the new part
                                new_text = text[len(buffer):] if text.startswith(buffer) else text
                                if new_text:
                                    yield {
                                        "type": "content_block_delta",
                                        "index": 0,
                                        "delta": {"type": "text_delta", "text": new_text}
                                    }
                                buffer = text
                        # Get usage info
                        usage = msg.get("usage", {})
                        output_tokens = usage.get("output_tokens", output_tokens)
                    elif event_type == "result":
                        # Final result
                        usage = event.get("usage", {})
                        output_tokens = usage.get("output_tokens", output_tokens)
                except json.JSONDecodeError:
                    pass

            yield {
                "type": "content_block_stop",
                "index": 0
            }

            yield {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": output_tokens}
            }

            yield {
                "type": "message_stop"
            }

            await process.wait()

        except FileNotFoundError:
            yield {
                "type": "error",
                "error": {"type": "api_error", "message": "Claude Code CLI not found"}
            }
        except Exception as e:
            yield {
                "type": "error",
                "error": {"type": "api_error", "message": str(e)}
            }


claude_bridge = ClaudeBridge()
