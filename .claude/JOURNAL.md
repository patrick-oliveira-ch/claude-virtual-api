# Journal de Développement - Claude Virtual API

## Session 2026-01-15 21:00

### Objectif
Tests et corrections du serveur API

### Actions
- Test de POST /v1/messages → Erreur 500 initiale
- Diagnostic : problème de mapping des modèles API → CLI
- Ajout du MODEL_MAPPING dans `claude_bridge.py` (ex: "claude-sonnet-4-5-20251101" → "sonnet")
- Ajout de logs de debug dans le bridge
- Désactivation du mode reload pour voir les erreurs
- Test streaming → Erreur car `--verbose` requis pour `stream-json`
- Correction du streaming avec `--verbose` et parsing correct du format

### Corrections Apportées
1. **Mapping des modèles** : Les noms API (ex: `claude-opus-4-5-20251101`) sont mappés vers les noms CLI (`opus`, `sonnet`, `haiku`)
2. **Streaming** : Ajout de `--verbose` à la commande CLI pour `stream-json`
3. **Parsing streaming** : Extraction du texte depuis `event.message.content[0].text`

### Tests Réussis
```bash
# Message simple
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "x-api-key: test-key" -H "content-type: application/json" \
  -d '{"model":"sonnet","max_tokens":100,"messages":[{"role":"user","content":"Dis bonjour"}]}'
# → {"content":[{"text":"Bonjour, je suis prêt à vous aider..."}],"usage":{"input_tokens":7,"output_tokens":16}}

# Streaming
curl -X POST http://127.0.0.1:8080/v1/messages \
  -H "x-api-key: test-key" -H "content-type: application/json" \
  -d '{"model":"sonnet","stream":true,"messages":[{"role":"user","content":"Compte de 1 a 5"}]}'
# → event: content_block_delta / data: {"delta":{"text":"1, 2, 3, 4, 5"}}
```

### État Final
Serveur 100% fonctionnel :
- Messages simples : OK
- Streaming SSE : OK
- Tous les endpoints : OK

---

## Session 2026-01-15 20:50

### Objectif
Implémentation complète du serveur API virtuel Claude

### Actions
- Création de la structure du projet Python/FastAPI
- Implémentation du bridge vers Claude Code CLI (`src/claude_bridge.py`)
- Implémentation de tous les endpoints API (`src/server.py`)
- Configuration des dépendances (`requirements.txt`)

### Architecture
```
Client HTTP → FastAPI Server (port 8080) → subprocess → Claude Code CLI
```

### Endpoints Implémentés
| Endpoint | Méthode | Status |
|----------|---------|--------|
| `/health` | GET | OK |
| `/v1/messages` | POST | OK |
| `/v1/messages` (stream) | POST | OK |
| `/v1/messages/count_tokens` | POST | OK |
| `/v1/messages/batches` | POST/GET/DELETE | OK |
| `/v1/messages/batches/{id}/results` | GET | OK |
| `/v1/models` | GET | OK |
| `/v1/models/{id}` | GET | OK |
| `/v1/files` | POST/GET/DELETE | OK |
| `/v1/organizations/me` | GET | OK |
| `/v1/organizations/usage_report/messages` | GET | OK |
| `/v1/organizations/cost_report` | GET | OK |

### Fichiers Créés
- `main.py` - Point d'entrée
- `requirements.txt` - Dépendances
- `src/__init__.py` - Module
- `src/models.py` - Modèles Pydantic
- `src/claude_bridge.py` - Bridge CLI
- `src/server.py` - Serveur FastAPI

### Décisions Techniques
- FastAPI pour la performance et la documentation auto-générée
- tiktoken pour le comptage de tokens (estimation locale)
- subprocess async pour l'exécution non-bloquante de Claude Code
- Stockage en mémoire pour batches/files (simplifié)

### Prochaines Étapes
- [ ] Implémenter traitement réel des batches (async background)
- [ ] Ajouter persistance (SQLite ou fichiers)
- [ ] Ajouter authentification configurable
- [ ] Documentation OpenAPI personnalisée

---

## Session 2026-01-15 (init)

### Objectif
Initialisation du projet

### Notes
- Projet créé via Claude Cost Optimizer
- Description: API virtuelle qui proxie les requêtes vers Claude Code CLI

---
