"""Client simple pour Claude Virtual API."""
import httpx
from typing import Optional, Generator
import json


class ClaudeClient:
    """Client pour communiquer avec Claude Virtual API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8080", api_key: str = "local"):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            "x-api-key": api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01"
        }

    def message(
        self,
        prompt: str,
        model: str = "sonnet",
        max_tokens: int = 1024,
        system: Optional[str] = None
    ) -> str:
        """Envoyer un message et obtenir la réponse."""
        data = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system:
            data["system"] = system

        with httpx.Client(timeout=120) as client:
            response = client.post(
                f"{self.base_url}/v1/messages",
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            result = response.json()
            return result["content"][0]["text"]

    def message_stream(
        self,
        prompt: str,
        model: str = "sonnet",
        max_tokens: int = 1024,
        system: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Envoyer un message et streamer la réponse."""
        data = {
            "model": model,
            "max_tokens": max_tokens,
            "stream": True,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system:
            data["system"] = system

        with httpx.Client(timeout=120) as client:
            with client.stream(
                "POST",
                f"{self.base_url}/v1/messages",
                headers=self.headers,
                json=data
            ) as response:
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        event = json.loads(line[6:])
                        if event.get("type") == "content_block_delta":
                            text = event.get("delta", {}).get("text", "")
                            if text:
                                yield text

    def models(self) -> list[dict]:
        """Lister les modèles disponibles."""
        with httpx.Client() as client:
            response = client.get(
                f"{self.base_url}/v1/models",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()["data"]


# Instance par défaut
claude = ClaudeClient()


# Exemple d'utilisation
if __name__ == "__main__":
    # Test simple
    print("=== Test message simple ===")
    reponse = claude.message("Dis bonjour en une phrase")
    print(f"Réponse: {reponse}")

    # Test streaming
    print("\n=== Test streaming ===")
    print("Réponse: ", end="", flush=True)
    for chunk in claude.message_stream("Compte de 1 à 5"):
        print(chunk, end="", flush=True)
    print()

    # Test modèles
    print("\n=== Modèles disponibles ===")
    for m in claude.models():
        print(f"  - {m['id']}")
