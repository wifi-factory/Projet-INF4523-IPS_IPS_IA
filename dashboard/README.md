# Dashboard Live IPS IA

Cette dashboard Streamlit fournit une console live en francais au-dessus du backend IPS existant.

## Prerequis

- Python 3.11 recommande
- dependances installees via `requirements.txt`
- backend FastAPI disponible

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Lancer le backend

```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

## Lancer la dashboard

```powershell
streamlit run dashboard/app.py
```

Le pilotage du runtime live se fait directement depuis la sidebar :
- selection automatique de l'interface source
- activation / arret du runtime
- resume compact de l'etat backend et runtime

## Variables utiles

- `IPS_DASHBOARD_BACKEND_URL` : URL du backend, par defaut `http://127.0.0.1:8000`
- `IPS_DASHBOARD_REFRESH_SECONDS` : frequence de rafraichissement, par defaut `3`
- `IPS_DASHBOARD_REQUEST_TIMEOUT_SECONDS` : timeout HTTP, par defaut `5`
- `IPS_DASHBOARD_EVENTS_LIMIT` : volume max charge pour la page Evenements
- `IPS_DASHBOARD_ALERTS_LIMIT` : volume max charge pour la page Alertes
- `IPS_DASHBOARD_BLOCKING_LIMIT` : volume max charge pour les decisions de blocage
- `IPS_DASHBOARD_LOGS_LIMIT` : volume max charge pour le journal runtime

## Tests utiles

Validation dashboard :

```powershell
python -m pytest dashboard/tests -q
```

Validation backend live :

```powershell
python -m pytest backend/tests/test_api_live.py backend/tests/test_live_capture_service.py backend/tests/test_live_runtime_service.py -q
```

## Limites connues

- fonctionnement uniquement en mode live
- rafraichissement silencieux par polling en arriere-plan, sans WebSocket
- l'interface depend des endpoints live exposes par le backend
