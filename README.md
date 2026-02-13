# VendingBench Simulation

This repository implements an **autonomous vending‑machine business simulation**.  The agent runs daily loops, uses tool‑calling (email, storage queries, waiting for next day, etc.), and logs everything to a SQLite database.

## New Features (Added in the latest update)

1. **Back‑room ➜ Vending‑Machine Restocking** – After a supplier delivery is processed, the simulation now automatically moves matching items from back‑room storage into empty vending‑machine slots.
2. **Sales Simulation** – When items are stocked, daily sales are calculated, logged in the `sales` table, and the balance is updated.
3. **Reporting Script (`report.py`)** – A lightweight CLI script that prints:
   - Balance history over time
   - Email activity summary (inbound/outbound counts)
   - Current back‑room storage inventory
   - Daily sales totals
4. **Tool‑Calling Support for Cerebras** – The model client now forwards `tools` schemas to the Cerebras endpoint, parses `tool_calls` correctly, and stores them as JSON.
5. **Database Enhancements** – Added a `machine_slots` table to persist the vending‑machine slot state each day.

## How to Run the Simulation
```bash
# Activate the virtual environment (already set up)
source venv/bin/activate

# Run a short simulation (e.g., 5 actions)
python run_sim.py --max-messages 5
```
The simulation prints daily reports, executes tools, and updates the SQLite DB at `/home/hnai/vending_simulation.db`.

## Generating a Report
```bash
python report.py
```
The script reads the same SQLite DB and outputs concise tables of balance, emails, storage, and sales.

## Repository Structure (relevant files)
- `agent.py` – Core autonomous agent logic.
- `main_simulation.py` – Orchestrates daily cycles, deliveries, restocking, and reporting.
- `model_client.py` – Handles calls to the Cerebras API with function‑calling support.
- `tools.py` – Implements `send_email`, `check_storage_quantities`, `wait_for_next_day`, etc.
- `storage.py` – Back‑room inventory and pending deliveries.
- `email_system.py` – Email sending/receiving with DB logging.
- `database.py` – SQLite schema (including `machine_slots`).
- `report.py` – Quick‑look reporting CLI.

## Setup & Dependencies
```bash
# Install dependencies (inside the repo)
pip install -r requirements.txt
```
Make sure the `.env` file contains a valid `CEREBRAS_API_KEY` (lower‑case `csk-…`).

---
*Feel free to extend the simulation (add more items, pricing, or richer supplier interactions) and use the `report.py` script to monitor performance over time.*
