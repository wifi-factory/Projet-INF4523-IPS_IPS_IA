# Dashboard Streamlit

Le dossier `dashboard/` contient la console live du prototype IPS IA. La
dashboard consomme les endpoints exposes par le backend FastAPI et ne charge
pas directement le modele.

## Pages disponibles

- `Vue ensemble`
- `Runtime live`
- `Alertes`
- `Evenements`
- `Journal trafic`

La sidebar fournit egalement :

- un resume du backend et du runtime ;
- le demarrage ou l'arret du mode live ;
- un panneau de derniere alerte recente.

## Lancement

Depuis la racine du depot :

```powershell
.\.venv\Scripts\streamlit run dashboard/app.py
```

Le backend doit etre accessible au meme moment.

## Variables d'environnement utiles

- `IPS_DASHBOARD_BACKEND_URL` : URL du backend, par defaut `http://127.0.0.1:8000`
- `IPS_DASHBOARD_REQUEST_TIMEOUT_SECONDS` : timeout HTTP
- `IPS_DASHBOARD_REFRESH_SECONDS` : rafraichissement principal des pages
- `IPS_DASHBOARD_ALERT_PULSE_REFRESH_SECONDS` : cadence du panneau "derniere alerte"
- `IPS_DASHBOARD_EVENTS_LIMIT` : taille max de la table Evenements
- `IPS_DASHBOARD_ALERTS_LIMIT` : taille max de la page Alertes
- `IPS_DASHBOARD_BLOCKING_LIMIT` : taille max de l'historique de blocage
- `IPS_DASHBOARD_LOGS_LIMIT` : taille max du journal runtime

## Tests

```powershell
.\.venv\Scripts\python -m pytest dashboard/tests -q
```

## Limites connues

- La dashboard repose sur du polling HTTP, pas sur des WebSocket.
- L'affichage live depend de la finalisation des flux cote backend.
- Les donnees visibles refletent l'etat memoire du runtime courant ; elles ne
  constituent pas une persistance historique complete.
