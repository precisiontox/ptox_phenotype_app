# PrecisionTox Phenotype Data Explorer

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-orange.svg)](https://www.gnu.org/licenses/gpl-3.0.html)

A small Flask web application for browsing, exploring, and comparing PrecisionTox phenotype experiment data. The app fetches the data directly from the **PrecisionTox Central Database** [:link:](https://github.com/precisiontox/ptox_central_database) through an SSH tunnel, and presents dashboard summaries, experiment tables, endpoint exploration tools, and cross-organism comparison views.

## Features

- Dashboard with live data composition overview and endpoint coverage and classification.
- Experiment browser with filtering options based on different metadata.
- Endpoint exploration pages backed by API endpoints to visualize data distribution, chemical ranking and dose-response curves.
- Interactive heatmap view for multiple endpoint comparison and chemical grouping.


## Project structure

```text
.
├── app/
│   ├── routes/              # Flask blueprints and API routes
│   ├── templates/           # Jinja templates
│   ├── static/              # CSS, JS and local reference data
│   ├── db.py                # SSH tunnel and SQLAlchemy database helpers
│   └── __init__.py          # Flask app factory
├── config.py                # Environment-based configuration
├── requirements.txt         # Python dependencies
└── run.py                   # Local development entry point
```

## Setup

Create and activate a virtual environment, then install the dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the repository root with the SSH and the database settings:

```bash
SECRET_KEY=change-me

SSH_HOST=ssh.example.org
SSH_PORT=22
SSH_USERNAME=your-user
# Use either SSH_PASSWORD or SSH_PRIVATE_KEY
SSH_PASSWORD=your-password
# SSH_PRIVATE_KEY=/path/to/private/key
# SSH_PRIVATE_KEY_PASSWORD=optional-key-password

DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=ptox_central_db
DB_USER=psql_user
DB_PASSWORD=psql_password
```

IMPORTANT: you need access to a live version of the PrecisionTox Central Database.

## Running locally

From the repository root:

```bash
python run.py
```

The development server starts with Flask debug mode enabled and the reloader disabled.

## Main routes

- `/` — dashboard summary
- `/experiments/` — experiment table and filters
- `/explore/` — endpoint/chemical exploration UI
- `/compare/` — comparison heatmap UI
- `/api/health` — database connectivity check
- `/api/...` — JSON endpoints used by the explore and compare pages

