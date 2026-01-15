# Claude Virtual API

Serveur API local qui proxie les requêtes vers Claude Code CLI. Permet d'utiliser l'API Claude standard tout en passant par Claude Code.

## Architecture

```
Client HTTP → FastAPI Server (port 8080) → subprocess → Claude Code CLI
```

## Installation

```bash
# Cloner le repo
git clone https://github.com/patrick-oliveira-ch/claude-virtual-api.git
cd claude-virtual-api

# Installer les dépendances
pip install -r requirements.txt

# Installer le client (optionnel)
pip install -e .
```

**Prérequis** : Claude Code CLI doit être installé et configuré.

## Utilisation

### Lancer le serveur

```bash
python main.py
```

Le serveur tourne sur `http://127.0.0.1:8080`

### Endpoints disponibles

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/v1/messages` | POST | Envoyer un message |
| `/v1/messages` (stream) | POST | Streaming SSE |
| `/v1/messages/count_tokens` | POST | Compter les tokens |
| `/v1/messages/batches` | POST/GET/DELETE | Gestion des batches |
| `/v1/models` | GET | Lister les modèles |
| `/v1/files` | POST/GET/DELETE | Gestion des fichiers |
| `/health` | GET | Status du serveur |

### Exemples curl

```bash
# Message simple
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "x-api-key: any-key" \
  -H "content-type: application/json" \
  -d '{"model":"sonnet","max_tokens":1024,"messages":[{"role":"user","content":"Bonjour"}]}'

# Avec streaming
curl -N -X POST http://127.0.0.1:8080/v1/messages \
  -H "x-api-key: any-key" \
  -H "content-type: application/json" \
  -d '{"model":"sonnet","max_tokens":1024,"stream":true,"messages":[{"role":"user","content":"Raconte une histoire"}]}'

# Lister les modèles
curl http://127.0.0.1:8080/v1/models -H "x-api-key: any-key"
```

### Client Python

```python
from client import claude

# Message simple
reponse = claude.message("Explique Python en 2 phrases")
print(reponse)

# Avec options
reponse = claude.message(
    "Bonjour",
    model="haiku",
    system="Tu es un pirate",
    max_tokens=500
)

# Streaming
for chunk in claude.message_stream("Compte de 1 à 10"):
    print(chunk, end="", flush=True)

# Lister les modèles
modeles = claude.models()
```

### Modèles supportés

| Modèle API | Modèle CLI |
|------------|------------|
| `claude-opus-4-5-20251101` | opus |
| `claude-sonnet-4-5-20251101` | sonnet |
| `claude-3-5-haiku-20241022` | haiku |
| `opus` / `sonnet` / `haiku` | direct |

## Structure du projet

```
claude-virtual-api/
├── main.py              # Point d'entrée
├── client.py            # Client Python
├── requirements.txt     # Dépendances
├── setup.py             # Installation pip
└── src/
    ├── server.py        # Serveur FastAPI
    ├── claude_bridge.py # Bridge vers CLI
    └── models.py        # Modèles Pydantic
```

## Licence

MIT
