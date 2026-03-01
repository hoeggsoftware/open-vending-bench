# Security Hardening Guide

**Project:** Vending Machine Simulator
**Review Date:** 2026-02-28
**Reviewed By:** Security Analysis
**Overall Risk Rating:** MODERATE

## Executive Summary

This document outlines security concerns identified in the vending machine simulator codebase and provides specific remediation steps. The codebase demonstrates good foundational security practices (no hardcoded secrets, parameterized SQL queries, clean git history) but requires hardening before production use or public release.

**Key Findings:**
- 3 Critical issues requiring immediate attention
- 8 High-risk issues affecting runtime security
- 7 Medium-risk issues for production hardening
- No malware or malicious code detected

---

## Critical Issues (Fix Before Any Use)

### CRIT-001: Unvalidated AI-Generated Tool Parameters
**Location:** `tools.py:452-516`, `email_system.py:280`
**Severity:** Critical
**Risk:** AI model could generate malicious tool parameters leading to unauthorized state manipulation

**Current Code:**
```python
def execute_tool(tool_call, simulation_ref):
    arguments = json.loads(arguments_str) if arguments_str else {}
    tool_result = TOOLS_FUNCTIONS[function_name](simulation_ref, **arguments)
```

**Remediation:**
```python
# Define validation schemas for each tool
TOOL_SCHEMAS = {
    "stock_machine": {
        "item_name": {"type": str, "max_length": 100, "pattern": r'^[a-zA-Z0-9\s\-]+$'},
        "slot_id": {"type": str, "pattern": r'^[0-3]-[0-2]$'},
        "quantity": {"type": int, "min": 1, "max": 10}
    },
    "send_email": {
        "recipient": {"type": str, "pattern": r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'},
        "subject": {"type": str, "max_length": 200},
        "body": {"type": str, "max_length": 5000}
    },
    "set_kw_value": {
        "key": {"type": str, "pattern": r'^[a-zA-Z0-9_-]{1,50}$'},
        "value": {"type": str, "max_length": 10000}
    }
}

def validate_tool_arguments(function_name, arguments):
    """Validate tool arguments against schema"""
    if function_name not in TOOL_SCHEMAS:
        return True, None  # No schema defined, allow

    schema = TOOL_SCHEMAS[function_name]
    for arg_name, arg_value in arguments.items():
        if arg_name not in schema:
            return False, f"Unknown argument: {arg_name}"

        rules = schema[arg_name]

        # Type check
        if not isinstance(arg_value, rules["type"]):
            return False, f"{arg_name} must be {rules['type'].__name__}"

        # String validations
        if rules["type"] == str:
            if "max_length" in rules and len(arg_value) > rules["max_length"]:
                return False, f"{arg_name} exceeds max length {rules['max_length']}"
            if "pattern" in rules:
                import re
                if not re.match(rules["pattern"], arg_value):
                    return False, f"{arg_name} format invalid"

        # Numeric validations
        if rules["type"] == int:
            if "min" in rules and arg_value < rules["min"]:
                return False, f"{arg_name} below minimum {rules['min']}"
            if "max" in rules and arg_value > rules["max"]:
                return False, f"{arg_name} above maximum {rules['max']}"

    return True, None

def execute_tool(tool_call, simulation_ref):
    # ... existing code ...
    arguments = json.loads(arguments_str) if arguments_str else {}

    # Add validation
    valid, error_msg = validate_tool_arguments(function_name, arguments)
    if not valid:
        return {
            "success": False,
            "message": f"\n\n[Tool validation failed: {error_msg}]",
            "console_output": f"❌ Validation error: {error_msg}"
        }

    # ... rest of existing code ...
```

---

### CRIT-002: Arbitrary File Write via KV Store
**Location:** `kv_store.py:9-21`
**Severity:** Critical
**Risk:** Path traversal vulnerability allowing writes outside intended directory

**Current Code:**
```python
class KVStore:
    def __init__(self, persist_path: str = "kv_store.json"):
        self.persist_path = persist_path
        with open(self.persist_path, "w") as f:
```

**Remediation:**
```python
import os
from pathlib import Path

class KVStore:
    ALLOWED_DIR = Path("./kv_data")  # Restrict to specific directory

    def __init__(self, persist_path: str = "kv_store.json"):
        # Validate path
        if os.path.dirname(persist_path):
            raise ValueError("KVStore path must be filename only, no directories")

        # Ensure allowed directory exists
        self.ALLOWED_DIR.mkdir(exist_ok=True)

        # Construct safe path
        self.persist_path = self.ALLOWED_DIR / persist_path

        # Additional safety: resolve and verify still in allowed dir
        resolved = self.persist_path.resolve()
        if not str(resolved).startswith(str(self.ALLOWED_DIR.resolve())):
            raise ValueError("Path traversal attempt detected")

        self.data = {}
        self._load()
```

---

### CRIT-003: Unpinned Dependencies
**Location:** `requirements.txt:1-4`
**Severity:** Critical (for public release)
**Risk:** Supply chain attacks, breaking changes, known vulnerabilities

**Current Code:**
```
litellm
requests
python-dotenv
cerebras-cloud-sdk
```

**Remediation:**
```
# Pin specific versions with known security status
litellm==1.34.0
requests==2.31.0  # CVE-free version
python-dotenv==1.0.0
cerebras-cloud-sdk==1.0.0

# Add integrity checks
# Generate with: pip hash <package>
# litellm==1.34.0 --hash=sha256:...
```

**Additional Steps:**
1. Run `pip-audit` to check for known vulnerabilities
2. Set up Dependabot or Renovate for automated updates
3. Create `requirements-dev.txt` for development dependencies

---

## High-Risk Issues

### HIGH-001: No Spending Limits on AI Operations
**Location:** `email_system.py:222-301`, `storage.py:145-170`
**Severity:** High
**Risk:** AI-generated orders could drain balance

**Remediation:**
Add to `main_simulation.py`:
```python
class VendingMachineSimulation:
    def __init__(self, store_state=True, model_type=None):
        # ... existing code ...

        # Add safety limits
        self.daily_spending_limit = 100.0  # Max $100/day on orders
        self.daily_spending = 0.0
        self.min_balance_threshold = 50.0  # Alert if below $50
        self.max_order_value = 50.0  # Single order limit

    def validate_spending(self, amount: float) -> tuple[bool, str]:
        """Check if spending is within limits"""
        if amount > self.max_order_value:
            return False, f"Order exceeds max order value (${self.max_order_value})"

        if self.daily_spending + amount > self.daily_spending_limit:
            return False, f"Would exceed daily spending limit (${self.daily_spending_limit})"

        if self.balance - amount < self.min_balance_threshold:
            return False, f"Would drop below minimum balance (${self.min_balance_threshold})"

        return True, ""

    def record_spending(self, amount: float):
        """Track daily spending"""
        self.daily_spending += amount

    def handle_new_day(self):
        # ... existing code ...
        # Reset daily spending counter
        self.daily_spending = 0.0
```

Update `storage.py:process_arrivals` to check limits:
```python
def process_arrivals(self, current_time: datetime,
                    simulation_ref=None,
                    on_arrival: Optional[Callable] = None) -> float:
    # ... existing code ...

    for delivery in self.pending_deliveries:
        if delivery["arrival_time"] <= current_time:
            # ... calculate delivery_cost ...

            # Check spending limits if simulation_ref provided
            if simulation_ref:
                can_afford, reason = simulation_ref.validate_spending(delivery_cost)
                if not can_afford:
                    # Reject delivery, send notice
                    if on_arrival:
                        on_arrival(
                            supplier,
                            ref,
                            f"DELIVERY REJECTED: {reason}\nDelivery returned to sender."
                        )
                    continue  # Skip this delivery

                simulation_ref.record_spending(delivery_cost)
```

---

### HIGH-002: Unsanitized AI-Generated Content
**Location:** `email_system.py:283-285`, `agent.py:248`
**Severity:** High
**Risk:** AI responses could contain malicious content or injection attempts

**Remediation:**
```python
import html
import re

def sanitize_ai_content(content: str, max_length: int = 10000) -> str:
    """Sanitize AI-generated content for safe display/storage"""
    if not content:
        return ""

    # Truncate to max length
    content = content[:max_length]

    # HTML escape for safety
    content = html.escape(content)

    # Remove control characters (except newlines, tabs, carriage returns)
    content = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', content)

    # Limit consecutive newlines
    content = re.sub(r'\n{4,}', '\n\n\n', content)

    return content

# Apply in email_system.py
body_text = (response.get("content", "") or "").strip()
body_text = sanitize_ai_content(body_text)
```

---

### HIGH-003: Web Search Injection
**Location:** `email_system.py:175`, `email_system.py:203`
**Severity:** High
**Risk:** Malicious email addresses used in search queries

**Remediation:**
```python
import re

def sanitize_email_for_search(email: str) -> str:
    """Sanitize email address for safe use in search queries"""
    # Strict email validation
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return "unknown.contact@example.com"  # Safe fallback

    # Limit length
    if len(email) > 254:  # RFC 5321 limit
        return "unknown.contact@example.com"

    return email

def sanitize_search_query(query: str, max_length: int = 500) -> str:
    """Sanitize search query to prevent injection"""
    # Remove potentially dangerous characters
    query = re.sub(r'[<>\"\'`]', '', query)

    # Limit length
    query = query[:max_length]

    return query.strip()

# Apply in email_system.py
def create_recipient_profile(self, email_address: str) -> str:
    email_address = sanitize_email_for_search(email_address)
    domain = email_address.split("@")[-1]
    org_name = domain.split(".")[0].replace("-", " ").replace("_", " ")

    search_query = f"information about {org_name} company"
    search_query = sanitize_search_query(search_query)

    # ... rest of code ...
```

---

### HIGH-004: Database File Permissions
**Location:** `database.py:9-11`, `report.py:14`
**Severity:** High
**Risk:** Database readable by other users, hardcoded path won't work on other systems

**Remediation:**
```python
import sqlite3
import os
from pathlib import Path

class SimulationDatabase:
    def __init__(self, db_path="vending_simulation.db"):
        # Use relative path in current directory
        self.db_path = Path(db_path).resolve()

        # Create database
        self.conn = sqlite3.connect(str(self.db_path))

        # Set restrictive permissions (owner read/write only)
        # chmod 600 equivalent
        os.chmod(self.db_path, 0o600)

        self.create_tables()
```

Update `report.py`:
```python
import os
from pathlib import Path

# Use environment variable or current directory
DB_PATH = Path(os.getenv("VENDING_DB_PATH", "./vending_simulation.db"))

def _connect():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}")
    return sqlite3.connect(DB_PATH)
```

---

### HIGH-005: No Rate Limiting on API Calls
**Location:** `model_client.py`, `search.py`, `email_system.py:274`
**Severity:** High
**Risk:** Unexpected costs, service disruption, API key exhaustion

**Remediation:**
Create `rate_limiter.py`:
```python
import time
from collections import deque
from typing import Dict

class RateLimiter:
    """Simple token bucket rate limiter"""

    def __init__(self):
        # Track calls per API
        self.call_history: Dict[str, deque] = {}
        # Limits: calls per minute
        self.limits = {
            "anthropic": 50,
            "cerebras": 100,
            "perplexity": 20
        }

    def check_rate_limit(self, api_name: str) -> tuple[bool, str]:
        """Check if API call is allowed"""
        if api_name not in self.limits:
            return True, ""  # No limit defined

        now = time.time()
        limit = self.limits[api_name]

        # Initialize history for this API
        if api_name not in self.call_history:
            self.call_history[api_name] = deque()

        history = self.call_history[api_name]

        # Remove calls older than 1 minute
        while history and history[0] < now - 60:
            history.popleft()

        # Check if under limit
        if len(history) >= limit:
            wait_time = 60 - (now - history[0])
            return False, f"Rate limit exceeded. Wait {wait_time:.1f}s"

        # Record this call
        history.append(now)
        return True, ""

# Global rate limiter
_rate_limiter = RateLimiter()

def check_api_rate_limit(api_name: str) -> tuple[bool, str]:
    return _rate_limiter.check_rate_limit(api_name)
```

Apply in `model_client.py`:
```python
from rate_limiter import check_api_rate_limit

def call_model(prompt: str, model_type: str = "cerebras/gpt-oss-120b", ...):
    # Determine API from model type
    if "anthropic" in model_type or "claude" in model_type:
        api_name = "anthropic"
    elif "cerebras" in model_type:
        api_name = "cerebras"
    else:
        api_name = "other"

    # Check rate limit
    allowed, reason = check_api_rate_limit(api_name)
    if not allowed:
        return {
            "content": f"[Rate limit: {reason}]",
            "tool_calls": None
        }

    # ... existing code ...
```

---

### HIGH-006: Silent Authentication Failures
**Location:** `model_client.py:130-141`
**Severity:** High
**Risk:** Masks security issues, users unaware of API failures

**Remediation:**
```python
import logging

# Set up logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('security.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def call_model_litellm(prompt: str, model: str = "claude-3-5-sonnet-20241022", ...):
    try:
        response = litellm.completion(**completion_params)
        # ... existing code ...
    except Exception as e:
        # Log security-relevant errors
        if "AuthenticationError" in str(e) or "invalid x-api-key" in str(e):
            logger.error(f"Authentication failed for model {model}: {str(e)}")

            # In development, provide helpful error
            if os.getenv("ENVIRONMENT") == "development":
                return {
                    "content": f"⚠️ Authentication Error: Check your API keys in .env file",
                    "tool_calls": None
                }

            # In production, don't expose details but alert
            raise RuntimeError(f"API authentication failed for {model}")

        # Log other errors
        logger.error(f"Model call failed: {str(e)}")
        raise
```

---

### HIGH-007: Verbose Error Messages
**Location:** `tools.py:500-506`, `model_client.py:139`
**Severity:** High (in production)
**Risk:** Information disclosure in error messages

**Remediation:**
```python
import os

def execute_tool(tool_call, simulation_ref):
    # ... existing code ...

    except Exception as e:
        # Log full error for debugging
        logger.error(f"Tool execution failed: {function_name}", exc_info=True)

        # Return sanitized error to user
        if os.getenv("ENVIRONMENT") == "production":
            error_msg = "Tool execution failed"
        else:
            error_msg = f"Tool execution failed: {type(e).__name__}"

        print(f"❌ {error_msg}")

        return {
            "success": False,
            "message": f"\n\n[Tool error: {function_name} - {error_msg}]",
            "console_output": f"❌ {error_msg}"
        }
```

---

### HIGH-008: No API Cost Tracking
**Location:** Throughout API calls
**Severity:** High
**Risk:** Runaway API costs

**Remediation:**
Create `cost_tracker.py`:
```python
class CostTracker:
    """Track estimated API costs"""

    COSTS_PER_1K_TOKENS = {
        "claude-sonnet-4": {"input": 0.003, "output": 0.015},
        "cerebras": {"input": 0.0001, "output": 0.0001},
        "perplexity": {"request": 0.001}
    }

    def __init__(self, budget_limit: float = 10.0):
        self.budget_limit = budget_limit
        self.total_cost = 0.0
        self.costs_by_api = {}

    def estimate_cost(self, api: str, input_tokens: int, output_tokens: int = 0) -> float:
        """Estimate cost of API call"""
        if api not in self.COSTS_PER_1K_TOKENS:
            return 0.0

        rates = self.COSTS_PER_1K_TOKENS[api]

        if "request" in rates:
            return rates["request"]

        cost = (input_tokens / 1000 * rates["input"]) + \
               (output_tokens / 1000 * rates["output"])
        return cost

    def check_budget(self, estimated_cost: float) -> tuple[bool, str]:
        """Check if cost is within budget"""
        if self.total_cost + estimated_cost > self.budget_limit:
            remaining = self.budget_limit - self.total_cost
            return False, f"Budget exceeded. Remaining: ${remaining:.4f}"
        return True, ""

    def record_cost(self, api: str, cost: float):
        """Record actual cost"""
        self.total_cost += cost
        self.costs_by_api[api] = self.costs_by_api.get(api, 0) + cost
```

---

## Medium-Risk Issues

### MED-001: No Security Documentation
**Location:** Repository root
**Severity:** Medium
**Risk:** Users unaware of security considerations

**Remediation:**
Create `SECURITY.md`:
```markdown
# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

**DO NOT** report security vulnerabilities through public GitHub issues.

Instead, please email: security@example.com

You should receive a response within 48 hours.

## Security Considerations

### API Keys
- Never commit `.env` files to version control
- Use separate API keys for development and production
- Rotate keys regularly
- Monitor API usage for anomalies

### AI-Generated Content
- This application uses AI models to generate dynamic content
- AI responses are NOT guaranteed to be safe or accurate
- All AI-generated content should be reviewed before production use
- Implement spending limits to prevent runaway costs

### Data Storage
- Database files may contain sensitive simulation data
- Ensure proper file permissions (600) on database files
- Do not share database files publicly

## Known Limitations

1. AI models can generate arbitrary tool calls - input validation required
2. No built-in rate limiting - implement for production use
3. Costs can escalate with long-running simulations - set budgets
```

---

### MED-002: SQL Injection Pattern Risk
**Location:** `report.py:32-64`
**Severity:** Medium
**Risk:** Pattern could be copied incorrectly leading to SQL injection

**Remediation:**
```python
# Replace direct execute with parameterized queries
def email_summary(conn):
    print("--- Email summary ---")
    cursor = conn.cursor()

    # Use parameterized queries even for constants
    total = cursor.execute("SELECT COUNT(*) FROM emails WHERE 1=?", (1,)).fetchone()[0]
    inbound = cursor.execute(
        "SELECT COUNT(*) FROM emails WHERE direction=?", ("inbound",)
    ).fetchone()[0]
    outbound = cursor.execute(
        "SELECT COUNT(*) FROM emails WHERE direction=?", ("outbound",)
    ).fetchone()[0]

    print(f"Total emails: {total} (inbound: {inbound}, outbound: {outbound})")
```

---

### MED-003: Missing License File
**Location:** Repository root
**Severity:** Medium (legal risk)
**Risk:** Unclear usage rights

**Remediation:**
Create `LICENSE`:
```
MIT License

Copyright (c) 2026 [Your Name/Organization]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

### MED-004: No Environment Configuration
**Location:** Project-wide
**Severity:** Medium
**Risk:** Development settings used in production

**Remediation:**
Create `config.py`:
```python
import os
from pathlib import Path

class Config:
    """Base configuration"""
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    # Database
    DB_PATH = Path(os.getenv("VENDING_DB_PATH", "./vending_simulation.db"))

    # Security
    MAX_ORDER_VALUE = float(os.getenv("MAX_ORDER_VALUE", "50.0"))
    DAILY_SPENDING_LIMIT = float(os.getenv("DAILY_SPENDING_LIMIT", "100.0"))
    MIN_BALANCE_THRESHOLD = float(os.getenv("MIN_BALANCE_THRESHOLD", "50.0"))

    # Rate limiting
    RATE_LIMIT_ANTHROPIC = int(os.getenv("RATE_LIMIT_ANTHROPIC", "50"))
    RATE_LIMIT_CEREBRAS = int(os.getenv("RATE_LIMIT_CEREBRAS", "100"))
    RATE_LIMIT_PERPLEXITY = int(os.getenv("RATE_LIMIT_PERPLEXITY", "20"))

    # Budget
    API_BUDGET_LIMIT = float(os.getenv("API_BUDGET_LIMIT", "10.0"))

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    # Stricter limits in production
    MAX_ORDER_VALUE = 25.0
    DAILY_SPENDING_LIMIT = 50.0

def get_config():
    """Get configuration based on environment"""
    env = os.getenv("ENVIRONMENT", "development")
    if env == "production":
        return ProductionConfig()
    return DevelopmentConfig()
```

Update `.env.example`:
```bash
# API Keys (Required)
ANTHROPIC_API_KEY=your_claude_api_key_here
PERPLEXITY_API_KEY=your_perplexity_api_key_here
CEREBRAS_API_KEY=your_cerebras_api_key_here

# Environment Configuration
ENVIRONMENT=development  # development or production
DEBUG=false

# Database
VENDING_DB_PATH=./vending_simulation.db

# Security Limits
MAX_ORDER_VALUE=50.0
DAILY_SPENDING_LIMIT=100.0
MIN_BALANCE_THRESHOLD=50.0
API_BUDGET_LIMIT=10.0

# Rate Limiting (calls per minute)
RATE_LIMIT_ANTHROPIC=50
RATE_LIMIT_CEREBRAS=100
RATE_LIMIT_PERPLEXITY=20
```

---

### MED-005: No Input Length Limits
**Location:** `tools.py`, `email_system.py`
**Severity:** Medium
**Risk:** Memory exhaustion, excessive API costs

**Remediation:**
Already covered in CRIT-001 validation schemas. Additionally:
```python
# In agent.py
MAX_PROMPT_LENGTH = 100000  # characters
MAX_RESPONSE_LENGTH = 50000

def run_agent(self, context: str = "", loop_prompt: str = LOOP_PROMPT, ...):
    # Truncate context if too long
    if len(context) > MAX_PROMPT_LENGTH:
        context = context[:MAX_PROMPT_LENGTH] + "\n[...truncated]"

    # ... existing code ...
```

---

### MED-006: No Audit Logging
**Location:** Project-wide
**Severity:** Medium
**Risk:** Can't detect security incidents

**Remediation:**
Create `audit_logger.py`:
```python
import logging
import json
from datetime import datetime

class AuditLogger:
    """Log security-relevant events"""

    def __init__(self, log_file="audit.log"):
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)

        handler = logging.FileHandler(log_file)
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(message)s')
        )
        self.logger.addHandler(handler)

    def log_event(self, event_type: str, details: dict):
        """Log an audit event"""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "details": details
        }
        self.logger.info(json.dumps(event))

    def log_tool_call(self, tool_name: str, arguments: dict, success: bool):
        """Log tool execution"""
        self.log_event("tool_execution", {
            "tool": tool_name,
            "arguments": arguments,
            "success": success
        })

    def log_api_call(self, api_name: str, cost: float):
        """Log API usage"""
        self.log_event("api_call", {
            "api": api_name,
            "cost": cost
        })

    def log_spending(self, amount: float, balance_after: float):
        """Log financial transactions"""
        self.log_event("spending", {
            "amount": amount,
            "balance_after": balance_after
        })

# Global audit logger
_audit_logger = AuditLogger()

def audit_log(event_type: str, details: dict):
    _audit_logger.log_event(event_type, details)
```

---

### MED-007: No Security Testing
**Location:** Tests directory (missing)
**Severity:** Medium
**Risk:** Security issues not caught before deployment

**Remediation:**
Create `tests/test_security.py`:
```python
import unittest
from tools import execute_tool, validate_tool_arguments

class SecurityTests(unittest.TestCase):
    """Security-focused unit tests"""

    def test_path_traversal_kv_store(self):
        """Test KV store rejects path traversal"""
        from kv_store import KVStore

        with self.assertRaises(ValueError):
            KVStore("../../../etc/passwd")

        with self.assertRaises(ValueError):
            KVStore("/absolute/path/file.json")

    def test_sql_injection_resistance(self):
        """Test database methods resist SQL injection"""
        from database import SimulationDatabase

        db = SimulationDatabase(":memory:")

        # Try injection in email logging
        malicious_subject = "Test'; DROP TABLE emails; --"
        db.log_email(
            simulation_id="test",
            timestamp=datetime.now(),
            direction="inbound",
            email_id="test",
            sender="test@test.com",
            recipient="test@test.com",
            subject=malicious_subject,
            body="test"
        )

        # Verify emails table still exists
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM emails")
        self.assertIsNotNone(cursor.fetchone())

    def test_tool_validation_rejects_invalid(self):
        """Test tool validation rejects malicious inputs"""

        # Invalid slot_id
        valid, error = validate_tool_arguments("stock_machine", {
            "item_name": "Coke",
            "slot_id": "9-9",  # Invalid
            "quantity": 5
        })
        self.assertFalse(valid)

        # Quantity too high
        valid, error = validate_tool_arguments("stock_machine", {
            "item_name": "Coke",
            "slot_id": "0-0",
            "quantity": 9999  # Too high
        })
        self.assertFalse(valid)

        # Invalid email
        valid, error = validate_tool_arguments("send_email", {
            "recipient": "not-an-email",
            "subject": "Test",
            "body": "Test"
        })
        self.assertFalse(valid)

    def test_excessive_length_rejection(self):
        """Test rejection of excessively long inputs"""

        # Excessively long subject
        valid, error = validate_tool_arguments("send_email", {
            "recipient": "test@test.com",
            "subject": "A" * 10000,  # Too long
            "body": "Test"
        })
        self.assertFalse(valid)

if __name__ == '__main__':
    unittest.main()
```

Run tests:
```bash
python -m pytest tests/test_security.py -v
```

---

## Implementation Priority

### Phase 1: Immediate (Before Any Further Use)
1. ✅ Create this SECURITY_HARDENING.md document
2. Implement CRIT-001: Input validation for all tools
3. Implement CRIT-002: Path validation for KV store
4. Implement CRIT-003: Pin dependency versions
5. Implement HIGH-001: Spending limits

**Estimated Time:** 4-6 hours

### Phase 2: Before Team Collaboration
1. Implement HIGH-002: Content sanitization
2. Implement HIGH-003: Search query sanitization
3. Implement HIGH-004: Database security
4. Implement HIGH-005: Rate limiting
5. Create MED-001: SECURITY.md documentation

**Estimated Time:** 6-8 hours

### Phase 3: Before Public Release
1. Implement HIGH-006: Proper error handling
2. Implement HIGH-007: Production error messages
3. Implement HIGH-008: Cost tracking
4. Implement MED-004: Environment configuration
5. Implement MED-006: Audit logging
6. Implement MED-007: Security testing
7. Create MED-003: LICENSE file
8. Security audit and penetration testing

**Estimated Time:** 8-12 hours

---

## Testing Checklist

Before considering the codebase secure:

- [ ] All input validation tests pass
- [ ] Path traversal attempts are blocked
- [ ] SQL injection attempts fail safely
- [ ] Rate limiting works correctly
- [ ] Spending limits are enforced
- [ ] API authentication failures are handled properly
- [ ] Sensitive data not logged in errors
- [ ] Database file permissions are restrictive (600)
- [ ] All dependencies scanned for vulnerabilities
- [ ] Security.md and LICENSE created
- [ ] Audit logging captures security events
- [ ] Cost tracking prevents budget overruns

---

## Security Review Schedule

After implementing hardening measures:
- **Weekly:** Review audit logs for anomalies
- **Monthly:** Update dependencies and check for CVEs
- **Quarterly:** Re-run security scan
- **Annually:** External security audit for production systems

---

## Contact

For security concerns or questions about this document:
- Create a private security advisory on GitHub
- Email: [security contact email]

**Last Updated:** 2026-02-28
