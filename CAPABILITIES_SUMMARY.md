# Vending Machine Simulator - Capabilities Summary

**Project Name:** VendingBench Simulation
**Purpose:** AI agent benchmark for testing long-term autonomous decision-making in a simulated vending machine business
**Based On:** Recreation of VendingBench benchmark from research paper
**Repository:** https://github.com/genioCE/vendor.git

---

## Overview

This simulator creates a complete vending machine business environment where an AI agent autonomously manages operations over extended periods. The agent makes decisions about ordering products, managing inventory, stocking machines, and responding to market conditions - all while maintaining profitability.

---

## Core Capabilities

### 1. Autonomous AI Agent System

**Implementation:** `agent.py`

The agent is the central decision-maker that:
- Runs continuous autonomous loops (no human intervention required)
- Maintains conversation history with context management (30,000 token sliding window)
- Automatically summarizes old context to preserve long-term memory
- Executes function calls (tools) to interact with the simulation
- Operates 24/7 with daily 6 AM anchor time for business operations

**Agent Characteristics:**
- Name: VendingBot
- Starting Capital: $500
- Daily Operating Cost: $2/day
- Business Address: 1247 Business Park Drive, Suite 200, Chicago, IL 60601
- Bank Account: 1234567890 (hardcoded for orders)

**System Prompt Features:**
- Detailed business guidelines
- Tool usage instructions
- Workflow recommendations (search → order → stock → monitor → adapt)
- Requirement to include delivery address and account number in orders

---

### 2. Multi-Model AI Integration

**Implementation:** `model_client.py`

**Supported AI Providers:**
- **Anthropic Claude** (primary agent model)
  - Claude 4 Opus
  - Claude 4 Sonnet
- **Cerebras** (alternative/cost-effective option)
  - GPT-OSS-120B
  - Llama 3.1-8B
- **OpenAI**
  - GPT-4o
  - O3-mini, O3-pro
- **Google Gemini**
  - Gemini 2.5 Pro
  - Gemini 2.5 Flash
- **xAI Grok**
  - Grok 3 Beta
  - Grok 3 Mini
- **Perplexity** (web search only)

**Features:**
- Unified LiteLLM interface for model switching
- Function calling support (tools)
- Fallback to mock responses on auth errors
- Multiple tool call handling (takes first only)
- Custom Cerebras SDK integration

---

### 3. Tool System (Agent Actions)

**Implementation:** `tools.py`

The agent has **16 tools** available:

#### Time Management
- `wait_for_next_day` - Advance simulation to 6 AM next day (triggers sales, deliveries, weather)

#### Communication
- `send_email` - Email suppliers to place orders, ask questions
- `read_email` - Read unread inbox messages (auto-marks as read)

#### Inventory Management
- `check_storage_quantities` - View backroom inventory with quantities and values
- `get_machine_inventory` - View vending machine slots and contents
- `stock_machine` - Move items from backroom to vending machine slots

#### Financial
- `get_money_balance` - Check current cash balance

#### Research
- `ai_web_search` - Search web via Perplexity API for supplier/product info

#### Memory Systems
- `scratchpad_write` - Append notes to scratchpad
- `read_scratchpad` - Read scratchpad contents
- `erase_scratchpad` - Clear scratchpad

#### Persistent Storage
- `get_kw_value` - Retrieve value from key-value store
- `set_kw_value` - Store key-value pair (persists to JSON file)
- `delete_kw_value` - Remove key from store

#### Vector Database
- `add_to_vector_db` - Store text document for semantic search
- `search_vector_db` - Find similar documents (top-k results)

**Tool Execution:**
- Single tool call per agent turn (enforced by model client)
- JSON argument parsing
- Error handling with formatted responses
- All tools logged to database

---

### 4. Email & Supplier Communication System

**Implementation:** `email_system.py`

**Capabilities:**
- **Inbox/Outbox Management:** Separate tracking for sent/received emails
- **Unread Tracking:** Emails marked as read after agent views them
- **Email Metadata:** Sender, recipient, subject, body, timestamp, type
- **Database Logging:** All emails persisted with direction (inbound/outbound)

**AI-Generated Supplier Responses:**
- Suppliers are simulated by separate LLM instances
- Perplexity search creates dynamic supplier profiles
- Suppliers can autonomously schedule deliveries using their own tool:
  - `schedule_delivery(days_until_delivery, supplier, reference, items[])`
  - Items include: name, size, quantity, unit_cost
- Response generation includes product/pricing context from web search
- Realistic business correspondence (acknowledgments, pricing, logistics)

**Email Types:**
- `order` - Outbound orders from agent
- `supplier_response` - Inbound replies from suppliers
- `delivery_notice` - Arrival notifications
- `general` - Other correspondence

---

### 5. Inventory & Storage System

**Implementation:** `storage.py`, `vending_machine.py`

#### Backroom Storage (`StorageSystem`)
- Unlimited capacity backroom inventory
- Weighted average cost tracking per item
- Pending delivery queue with scheduled arrivals
- Automatic delivery processing at 6 AM
- Items have: name, size (small/large), quantity, unit_cost, selling price

**Storage Methods:**
- `add_items()` - Add items with weighted average costing
- `remove_items()` - Remove items (for stocking machine)
- `get_quantity()` - Check availability
- `schedule_delivery()` - Queue future delivery
- `process_arrivals()` - Process deliveries, charge account, send email notice
- `get_storage_report()` - Formatted inventory summary

#### Vending Machine (`VendingMachine`)
- **Configuration:** 4 rows × 3 columns = 12 slots
- **Row Constraints:**
  - Rows 0-1: Small items only
  - Rows 2-3: Large items only
- **Slot Capacity:** 10 units maximum per slot
- **Slot Format:** "row-column" (e.g., "0-0", "2-1")

**Vending Machine Methods:**
- `get_slots()` - View all slot states
- `can_stock_item()` - Check if item fits in slot
- `stock_item()` - Add quantity to slot
- `remove_item()` - Sell item (decrements quantity)
- `get_item_quantity()` - Check specific slot
- `get_total_value()` - Calculate inventory value

---

### 6. Economic Environment & Sales Simulation

**Implementation:** `economic_environment.py`

**Sales Generation:**
- Daily sales calculated at 6 AM new day processing
- Revenue added to balance
- Item quantities decremented from vending machine
- Sales data logged to database

**Demand Factors:**
- **Weather Conditions:** Affects customer traffic and preferences
- **Month/Season:** Seasonal demand variations
- **Day of Week:** Weekday vs. weekend patterns
- **Price Elasticity:** Higher prices reduce demand
- **Inventory Availability:** Can only sell what's stocked

**Sales Calculation:**
```
base_demand = f(weather, month, day_of_week, item_type)
price_adjusted_demand = base_demand × price_elasticity_factor
actual_sales = min(price_adjusted_demand, available_inventory)
revenue = actual_sales × selling_price
```

**Sales Report Includes:**
- Product name and quantity sold
- Revenue per product
- Total daily revenue
- Updated inventory levels

---

### 7. Weather & Time Simulation

**Implementation:** `weather.py`, `main_simulation.py`

#### Time System
- **Starting Time:** Current date at 6:00 AM UTC
- **Daily Anchor:** All major events at 6 AM (deliveries, sales, weather update)
- **Time Tracking:** Full datetime with timezone awareness
- **Day Counter:** Tracks simulation days elapsed
- **Message Counter:** Tracks total agent actions

#### Weather System
- **Conditions:** Sunny, rainy, cloudy, snowy
- **Generation:** Probabilistic based on current month and previous weather
- **Impact:** Affects customer traffic and product demand
- **Logged:** Weather stored in database per day

**Weather Patterns:**
- Winter (Dec-Feb): More snow, cold weather items popular
- Spring (Mar-May): Variable conditions
- Summer (Jun-Aug): More sunny days, cold drinks popular
- Fall (Sep-Nov): More rainy days, comfort items popular

---

### 8. Database & Logging System

**Implementation:** `database.py`

**Database:** SQLite (`vending_simulation.db`)

**Tables:**
1. **logs** - Agent interactions
   - Columns: timestamp, simulation_id, prompt, response, tool_calls (JSON)

2. **emails** - All email communications
   - Columns: timestamp, simulation_id, direction, email_id, sender, recipient, subject, body

3. **inventory** - Inventory changes
   - Columns: timestamp, simulation_id, item, quantity, change_type

4. **sales** - Daily sales records
   - Columns: timestamp, simulation_id, product, quantity, revenue

5. **time_progress** - Day progression
   - Columns: day_number, timestamp, simulation_id, weather

6. **weather** - Weather history
   - Columns: day_number, timestamp, simulation_id, condition

7. **simulation_state** - Balance snapshots
   - Columns: timestamp, simulation_id, balance

8. **machine_slots** - Vending machine state
   - Columns: slot_id, simulation_id, item, quantity, size_type

**Logging Features:**
- Automatic state logging after each action
- Day number tracking
- Full tool call JSON storage
- Email direction tracking (inbound/outbound)
- Weather conditions per day

---

### 9. Memory & Knowledge Systems

**Implementation:** `scratchpad.py`, `kv_store.py`, `vector_db.py`

#### Scratchpad (`Scratchpad`)
- Simple text append-only notepad
- Agent can write notes, read them, or erase all
- Persists across agent turns (in-memory during session)

#### Key-Value Store (`KVStore`)
- Persistent JSON file storage (`kv_store.json`)
- String key-value pairs
- Automatically saves on write
- Agent can store strategies, decisions, important info

#### Vector Database (`SimpleVectorDB`)
- Simple TF-IDF cosine similarity search
- Store text documents
- Semantic search with top-k results
- Tokenization and scoring
- In-memory (not persisted by default)

---

### 10. Reporting & Analytics

**Implementation:** `report.py`, `evaluation.py`

#### Report Script (`report.py`)
Command-line tool that generates:
- **Balance History:** Timeline of cash balance changes
- **Email Summary:** Total/inbound/outbound email counts
- **Storage Inventory:** Current backroom items and quantities
- **Sales Summary:** Daily sales totals by date

**Usage:**
```bash
python report.py
```

#### Evaluation System (`evaluation.py`)
Comprehensive performance metrics:
- **Financial Metrics:**
  - Starting vs. ending balance
  - Total revenue and profit
  - ROI calculation

- **Operational Metrics:**
  - Total days simulated
  - Email activity (sent/received)
  - Inventory turnover
  - Sales by product

- **Email Analysis:**
  - Communication patterns
  - Response times
  - Supplier engagement

**Usage:**
```bash
python run_sim.py --evaluate
```

---

### 11. Simulation Control & Execution

**Implementation:** `main_simulation.py`, `run_sim.py`, `run_simulation.sh`

#### Main Simulation (`VendingMachineSimulation`)
Central orchestrator that:
- Initializes all subsystems
- Manages simulation state
- Handles new day processing
- Runs agent loop
- Logs state to database

**New Day Processing (at 6 AM):**
1. Increment day counter
2. Deduct daily fee ($2)
3. Generate new weather
4. Calculate and process sales (if items stocked)
5. Update balance with revenue
6. Generate supplier email responses
7. Process scheduled deliveries
8. Deduct delivery costs
9. Log state with day number
10. Return daily report to agent

**Configuration Options:**
- `store_state` - Enable/disable database logging
- `model_type` - Choose AI model
- `starting_balance` - Override default $500

#### Run Script (`run_sim.py`)
Command-line interface:
```bash
# Basic usage
python run_sim.py                    # 50 messages, default model
python run_sim.py -m 200             # 200 messages
python run_sim.py --model cerebras   # Use Cerebras model
python run_sim.py --no-store-state   # Don't log to DB
python run_sim.py --evaluate         # Run evaluation after
python run_sim.py --starting-balance 1000  # Start with $1000
```

**Arguments:**
- `--max-messages, -m` - Number of agent actions
- `--model` - AI model to use
- `--no-store-state` - Disable DB logging
- `--evaluate, -e` - Run evaluation report
- `--verbose, -v` - Detailed output
- `--starting-balance` - Override starting cash

#### Setup Script (`run_simulation.sh`)
Bash automation script that:
1. Checks Python 3 installation
2. Creates virtual environment
3. Installs dependencies
4. Checks/creates `.env` file
5. Validates API keys present
6. Tests component imports
7. Runs simulation

**Usage:**
```bash
./run_simulation.sh              # Default 10 messages
./run_simulation.sh 100          # 100 messages
```

---

## Current Simulation Workflow

### Typical Agent Operation Cycle:

1. **Startup (Day 0, 6 AM)**
   - Agent receives initial daily report
   - Balance: $500, no inventory, empty machine

2. **Research Phase**
   - Agent uses `ai_web_search` to find suppliers
   - Searches for products, pricing, contact info

3. **Ordering Phase**
   - Agent uses `send_email` to contact suppliers
   - Includes delivery address and account number
   - Requests specific products with quantities

4. **Supplier Response**
   - Simulated supplier (LLM) processes email
   - Generates realistic response with pricing
   - Calls `schedule_delivery` tool (if order valid)
   - Agent receives email via `read_email`

5. **Wait for Delivery**
   - Agent uses `wait_for_next_day` to advance time
   - System processes at 6 AM:
     - Deducts $2 daily fee
     - Updates weather
     - Delivers scheduled items to backroom
     - Charges balance for delivery
     - Sends delivery notice email

6. **Stocking Phase**
   - Agent uses `check_storage_quantities` to see backroom
   - Uses `stock_machine` to move items to machine slots
   - Respects size constraints (small=rows 0-1, large=rows 2-3)

7. **Sales Generation**
   - Next day at 6 AM: automatic sales calculation
   - Sales based on weather, season, pricing, inventory
   - Revenue added to balance
   - Sales report in daily report

8. **Monitoring & Adaptation**
   - Agent reviews sales data
   - Adjusts pricing strategy
   - Reorders low-stock items
   - Uses memory tools to track strategies
   - Repeats cycle

---

## Technical Architecture

### File Structure
```
vendor/
├── agent.py                 # Core agent logic
├── main_simulation.py       # Simulation orchestrator
├── model_client.py         # AI model integration
├── tools.py                # Agent tool definitions
├── email_system.py         # Email and supplier simulation
├── storage.py              # Backroom inventory management
├── vending_machine.py      # Vending machine implementation
├── economic_environment.py # Sales calculation
├── weather.py              # Weather generation
├── database.py             # SQLite logging
├── scratchpad.py           # Simple notepad
├── kv_store.py             # Key-value persistence
├── vector_db.py            # Semantic search
├── search.py               # Perplexity API integration
├── report.py               # Reporting CLI
├── evaluation.py           # Performance metrics
├── run_sim.py              # Main CLI entry point
├── run_simulation.sh       # Setup automation
├── requirements.txt        # Python dependencies
├── .env.example            # API key template
├── .gitignore              # Git exclusions
└── vending_simulation.db   # SQLite database
```

### Data Flow
```
User/CLI
    ↓
VendingMachineSimulation (orchestrator)
    ↓
VendingMachineAgent (autonomous decision-maker)
    ↓
Model Client (LiteLLM) → External APIs (Claude/Cerebras/etc)
    ↓
Tool Execution → Subsystems:
    - EmailSystem → Supplier LLM → Deliveries
    - StorageSystem → Inventory tracking
    - VendingMachine → Slot management
    - Database → State persistence
    - Search → Perplexity API
    ↓
Daily Processing (6 AM)
    - Weather update
    - Sales calculation
    - Delivery processing
    - Email generation
    ↓
Database Logging (all events)
    ↓
Report/Evaluation (analytics)
```

---

## Key Constraints & Limits

### Financial
- Starting balance: $500
- Daily operating cost: $2
- No bankruptcy protection (can go negative)
- No built-in spending limits (security concern)

### Inventory
- Backroom: Unlimited capacity
- Vending machine: 12 slots × 10 units = 120 max items
- Size restrictions: Small (rows 0-1), Large (rows 2-3)

### Agent
- One tool call per turn
- 30,000 token context window
- Automatic context summarization when full
- No multi-step planning (single action per turn)

### API
- No rate limiting (can hit API limits)
- No cost tracking (can incur unexpected charges)
- Mock responses on auth errors (hides failures)

### Time
- All events at 6 AM daily anchor
- No intra-day time progression
- Weather changes once per day

---

## Current Limitations

### Not Yet Implemented
- ❌ Dynamic pricing strategy tools
- ❌ Competitor simulation
- ❌ Customer satisfaction tracking
- ❌ Marketing/promotion tools
- ❌ Multi-location management
- ❌ Equipment maintenance
- ❌ Seasonal product recommendations

### Security Issues (See SECURITY_HARDENING.md)
- ❌ No input validation on tool arguments
- ❌ No spending limits
- ❌ No rate limiting
- ❌ No cost tracking
- ❌ Path traversal vulnerability in KV store
- ❌ Unpinned dependencies

### Operational Issues
- ⚠️ Hardcoded database path won't work on all systems
- ⚠️ No error recovery from failed deliveries
- ⚠️ No transaction rollback on errors
- ⚠️ Silent failures on API auth errors

---

## Performance Characteristics

### Benchmark Purpose
Tests AI agent ability to:
- **Long-term coherence** - Maintain strategies over 20M+ tokens
- **Autonomous operation** - No human intervention needed
- **Tool use** - Effectively use 16 different tools
- **Economic reasoning** - Maximize profit over time
- **Adaptation** - Respond to weather, seasons, sales data
- **Planning** - Order ahead, stock appropriately
- **Memory management** - Use scratchpad/KV/vector DB effectively

### Typical Simulation Scale
- **Short test:** 10-50 messages, ~1 day simulated
- **Medium test:** 100-500 messages, ~5-10 days
- **Long test:** 1000+ messages, ~20-50 days
- **Benchmark:** Theoretically can run to 20M tokens (100+ days)

### Resource Usage
- **Database:** Grows with every action (logs, emails, sales)
- **API costs:** $0.01-$0.10 per agent message (depends on model)
- **Memory:** Minimal (context managed by sliding window)
- **CPU:** Low (mainly API calls, simple calculations)

---

## API Requirements

### Required
- **Anthropic API key** - For Claude models (primary agent)
- **Perplexity API key** - For web search (supplier research)

### Optional
- **Cerebras API key** - For alternative models
- **OpenAI API key** - For GPT models
- **Google Cloud** - For Gemini models
- **xAI API key** - For Grok models

### Configuration
All API keys stored in `.env` file:
```bash
ANTHROPIC_API_KEY=sk-ant-...
PERPLEXITY_API_KEY=pplx-...
CEREBRAS_API_KEY=csk-...
```

---

## Extension Points

### Easy to Add
1. **New tools** - Define function in `tools.py`, add to `TOOLS_LIST`
2. **New models** - Add mapping in `model_client.py:model_mapping`
3. **New items** - Just add via supplier orders (dynamic)
4. **New suppliers** - Agent can email any address
5. **Custom metrics** - Extend `evaluation.py`

### Moderate Effort
1. **Competition** - Add rival vending machines
2. **Marketing** - Add promotion/advertising tools
3. **Dynamic pricing** - Add price optimization tools
4. **Multi-location** - Extend simulation to multiple machines
5. **Customer segments** - Different demand patterns

### Significant Refactoring
1. **Real-time events** - Currently all at 6 AM
2. **Equipment failure** - No maintenance simulation
3. **Regulatory compliance** - No permit/licensing
4. **Supply chain complexity** - Single-tier suppliers
5. **Employee management** - Fully automated currently

---

## Use Cases

### 1. AI Agent Benchmarking
- Test long-term decision coherence
- Compare different LLM models
- Measure tool-use effectiveness
- Evaluate economic reasoning

### 2. Research
- Study autonomous agent behavior
- Test planning and memory systems
- Analyze adaptation strategies
- Benchmark context management

### 3. Education
- Teach AI agent architecture
- Demonstrate tool-calling systems
- Illustrate business simulation
- Practice prompt engineering

### 4. Development
- Prototype new agent features
- Test memory systems (scratchpad/KV/vector)
- Experiment with multi-agent (suppliers)
- Develop custom tools

---

## Quick Start Examples

### Basic Run
```bash
# Setup
cp .env.example .env
# Add your API keys to .env
pip install -r requirements.txt

# Run
python run_sim.py -m 20
```

### Evaluate Performance
```bash
python run_sim.py -m 100 --evaluate
```

### Use Different Model
```bash
python run_sim.py -m 50 --model cerebras
python run_sim.py -m 50 --model claude-4-sonnet
```

### View Results
```bash
python report.py
```

---

## Summary

**What it is:**
A complete autonomous AI agent simulation of a vending machine business with 16 tools, multi-model support, realistic supplier interactions, economic modeling, and comprehensive logging.

**What it tests:**
AI agent ability to autonomously manage a business over extended periods, making coherent decisions about ordering, inventory, pricing, and operations.

**What it provides:**
- Autonomous agent framework
- Multi-LLM integration
- Function calling / tool use
- Simulated environment with suppliers
- Economic simulation
- Memory systems (scratchpad, KV, vector DB)
- Complete audit trail

**Current state:**
Functional core simulation with good features but needs security hardening before production use or public deployment.

**Best for:**
- AI agent research
- LLM benchmarking
- Tool-use evaluation
- Long-term coherence testing
- Educational purposes
