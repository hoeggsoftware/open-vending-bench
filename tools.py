"""
Tools module for the autonomous vending‑machine simulation.

This module defines all agent‑accessible functions (tool calls) such as:
- Advancing the simulation day (`wait_for_next_day`).
- Communicating with suppliers (`send_email`, `read_email`).
- Inspecting storage and the vending‑machine slots.
- Managing a simple key‑value store and a vector‑DB.
- Performing a web search via the Perplexity API.
- Stocking items into specific machine slots.

Each function includes a concise docstring (triple‑quoted string) that explains its purpose, arguments, return value, and any side‑effects.  The `TOOLS_LIST` dictionary at the bottom of the file is used by the LLM for function‑calling.
"""

from datetime import datetime, timedelta
import json


def wait_for_next_day(simulation_ref):
    """Advance the simulation to the next day at 06:00.

    The function updates the internal clock, triggers daily fees, weather changes,
    and returns a human‑readable confirmation string.

    Args:
        simulation_ref: The active ``VendingMachineSimulation`` instance.

    Returns:
        str: Confirmation message with the new datetime.
    """
    # Get current time from simulation
    current_time = simulation_ref.get_current_time()
    # Calculate next day's 6:00 AM
    next_day = current_time.date() + timedelta(days=1)
    next_6am = datetime.combine(
        next_day, current_time.time().replace(hour=6, minute=0, second=0, microsecond=0)
    )
    next_6am = next_6am.replace(tzinfo=current_time.tzinfo)

    # Update simulation time
    simulation_ref.current_time = next_6am
    return f"Moved day forward to {next_6am}"


def send_email(simulation_ref, recipient, subject, body):
    """
    Send an email to a supplier or business contact

    Args:
        simulation_ref: Reference to the VendingMachineSimulation instance
        recipient: Email address of the recipient
        subject: Email subject line
        body: Email message body

    Returns:
        str: Confirmation of email sent
    """
    email_id = simulation_ref.email_system.send_email(
        recipient=recipient, subject=subject, body=body, email_type="order"
    )
    return f"Email sent to {recipient} with subject '{subject}' (ID: {email_id})"


def read_email(simulation_ref):
    """
    Read all unread emails in the inbox

    Args:
        simulation_ref: Reference to the VendingMachineSimulation instance

    Returns:
        str: Formatted unread emails with '----' spacers, or message if no emails
    """
    return simulation_ref.email_system.get_unread_emails_for_agent()


def check_storage_quantities(simulation_ref):
    """
    Check the current inventory in backroom storage

    Args:
        simulation_ref: Reference to the VendingMachineSimulation instance

    Returns:
        str: Formatted report of all items in storage with quantities and values
    """
    return simulation_ref.storage.get_storage_report()


# --- Scratchpad tools ---
def scratchpad_write(simulation_ref, text):
    """Write text to the scratchpad"""
    return simulation_ref.scratchpad.write(text)


def read_scratchpad(simulation_ref):
    """Read the scratchpad contents"""
    return simulation_ref.scratchpad.read()


def erase_scratchpad(simulation_ref):
    """Clear the scratchpad"""
    return simulation_ref.scratchpad.erase()


# --- Key-Value store tools ---
def get_kw_value(simulation_ref, key):
    """Get a value from the key-value store"""
    return simulation_ref.kv_store.get(key)


def set_kw_value(simulation_ref, key, value):
    """Set a value in the key-value store"""
    return simulation_ref.kv_store.set(key, value)


def delete_kw_value(simulation_ref, key):
    """Delete a key from the key-value store"""
    return simulation_ref.kv_store.delete(key)


# --- Vector DB tools ---
def add_to_vector_db(simulation_ref, text):
    """Add a document to the vector database"""
    return simulation_ref.vector_db.add(text)


def search_vector_db(simulation_ref, query, top_k=3):
    """Search for similar documents in the vector database"""
    return simulation_ref.vector_db.search(query, int(top_k))


# --- Machine inventory tool ---
def get_machine_inventory(simulation_ref):
    """Get the current vending machine inventory"""
    slots = simulation_ref.vending_machine.get_slots()

    # Collect empty slots by size
    empty_small = []
    empty_large = []
    for slot_id, slot in sorted(slots.items()):
        if slot["item"] is None:
            if slot['size_type'] == 'small':
                empty_small.append(slot_id)
            else:
                empty_large.append(slot_id)

    lines = ["VENDING MACHINE INVENTORY", "=" * 40]

    # Show summary of empty slots first
    if empty_small:
        lines.append(f"Empty SMALL slots (rows 0-1): {', '.join(empty_small)}")
    else:
        lines.append("Empty SMALL slots (rows 0-1): None - all full")

    if empty_large:
        lines.append(f"Empty LARGE slots (rows 2-3): {', '.join(empty_large)}")
    else:
        lines.append("Empty LARGE slots (rows 2-3): None - all full")

    lines.append("-" * 40)

    # Show detailed slot-by-slot inventory
    for slot_id, slot in sorted(slots.items()):
        if slot["item"]:
            lines.append(
                f"  Slot {slot_id} [{slot['size_type']}]: "
                f"{slot['item'].name} x{slot['quantity']} @ ${slot['item'].price:.2f}"
            )
        else:
            lines.append(f"  Slot {slot_id} [{slot['size_type']}]: EMPTY")
    return "\n".join(lines)


# --- Balance tool ---
def get_money_balance(simulation_ref):
    """Get the current money balance"""
    return f"Current balance: ${simulation_ref.balance:.2f}"


def get_simulation_status(simulation_ref):
    """Get current simulation status including day, messages, weather, and season.

    Returns comprehensive simulation state:
    - Current day number
    - Current date
    - Season (Spring/Summer/Fall/Winter)
    - Current weather conditions
    - Messages used so far

    Args:
        simulation_ref: Reference to the VendingMachineSimulation instance

    Returns:
        str: Formatted status report with all key simulation metrics
    """
    day_num = simulation_ref.days_passed + 1
    date_str = simulation_ref.current_time.strftime('%Y-%m-%d')
    season = simulation_ref.get_season()
    weather = simulation_ref.current_weather
    messages = simulation_ref.message_count

    return (
        f"Day {day_num} | {date_str} | {season} | Weather: {weather} | "
        f"Messages used: {messages}"
    )


# --- Web search tool ---
def ai_web_search(simulation_ref, query):
    """Search the web using Perplexity API"""
    from search import search_perplexity

    content, error = search_perplexity(query)
    if error:
        return f"Search failed: {error}"
    return content


# --- Fuzzy item name matching helper ---
def normalize_item_name(name):
    """Normalize item name for fuzzy matching"""
    import re
    # Convert to lowercase
    normalized = name.lower()
    # Replace underscores, hyphens with spaces
    normalized = normalized.replace('_', ' ').replace('-', ' ')
    # Remove parentheses, brackets and their contents for core matching
    normalized = re.sub(r'\([^)]*\)', '', normalized)
    normalized = re.sub(r'\[[^\]]*\]', '', normalized)
    # Collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def find_item_in_storage(storage, item_name):
    """
    Find an item in storage using business-friendly fuzzy matching.
    Returns (actual_name, item_obj) or (None, None)

    Students can use casual names like:
    - "snickers" → matches "Snickers Mini Bars (1.5‑oz)"
    - "trail mix" → matches "Classic Trail Mix 1‑oz Packs (12‑pk case, partial)"
    - "Bottled_Water" → matches "Aquafina 16.9 oz Bottles (12‑pk case, partial)"
    """
    available_items = storage.list_all_items()

    if not available_items:
        return None, None

    # Try exact match first (fast path)
    item_obj = storage.get_item(item_name)
    if item_obj is not None:
        return item_name, item_obj

    # Try case-insensitive exact match
    for stored_name in available_items:
        if stored_name.lower() == item_name.lower():
            item_obj = storage.get_item(stored_name)
            return stored_name, item_obj

    # Try normalized match (handles underscores, hyphens, parentheses)
    normalized_input = normalize_item_name(item_name)
    for stored_name in available_items:
        normalized_stored = normalize_item_name(stored_name)
        if normalized_input == normalized_stored:
            item_obj = storage.get_item(stored_name)
            return stored_name, item_obj

    # Try substring match (input is part of stored name)
    for stored_name in available_items:
        if item_name.lower() in stored_name.lower():
            item_obj = storage.get_item(stored_name)
            return stored_name, item_obj

    # Try reverse substring (stored name core is in input)
    for stored_name in available_items:
        stored_core = normalize_item_name(stored_name)
        input_lower = item_name.lower()
        if stored_core and stored_core in input_lower:
            item_obj = storage.get_item(stored_name)
            return stored_name, item_obj

    return None, None


# --- Stock machine tool ---
def stock_machine(simulation_ref, item_name, slot_id, quantity):
    """Move items from backroom storage to a vending machine slot"""
    storage = simulation_ref.storage
    vm = simulation_ref.vending_machine
    quantity = int(quantity)

    # Use fuzzy matching to find the item
    actual_name, item_obj = find_item_in_storage(storage, item_name)

    if item_obj is None:
        available_items = storage.list_all_items()
        if available_items:
            items_list = ", ".join(available_items[:5])
            return f"Item '{item_name}' not found in storage. Available: {items_list}"
        else:
            return f"Item '{item_name}' not found. Storage is empty."

    available = storage.get_quantity(actual_name)
    if available < quantity:
        return f"Only {available} units of '{actual_name}' in storage (requested {quantity})."

    # Check slot validity
    if slot_id not in vm.slots:
        return f"Invalid slot ID '{slot_id}'. Valid slots are 0-0 through 3-2."

    slot = vm.slots[slot_id]

    # Check size compatibility
    if slot['size_type'] != item_obj.size:
        return f"Cannot stock '{actual_name}' in slot {slot_id}: size mismatch. Item is {item_obj.size}, but slot {slot_id} (row {slot_id[0]}) requires {slot['size_type']} items. Use rows 0-1 for small items, rows 2-3 for large items."

    # Check if slot already has a different item
    if slot['item'] is not None and slot['item'].name != actual_name:
        return f"Cannot stock '{actual_name}' in slot {slot_id}: slot already contains '{slot['item'].name}' ({slot['quantity']} units). Each slot can only hold ONE product type. Use get_machine_inventory to find empty slots."

    # Check capacity
    if slot['quantity'] + quantity > slot['max_capacity']:
        current = slot['quantity']
        available_space = slot['max_capacity'] - current
        return f"Slot {slot_id} doesn't have enough capacity. Currently has {current} units, max is {slot['max_capacity']}, requested {quantity} (only {available_space} space available)."

    # Stock the item
    if not vm.stock_item(slot_id, item_obj, quantity):
        return f"Failed to stock '{actual_name}' in slot {slot_id}. Unexpected error."

    # Remove from storage
    storage.remove_items(actual_name, quantity)
    return f"Stocked {quantity}x {actual_name} into slot {slot_id}."


# --- Set item price tool ---
def set_item_price(simulation_ref, item_name, price):
    """Set the selling price for an item in storage"""
    storage = simulation_ref.storage
    price = float(price)

    if price < 0:
        return f"Price must be non-negative (got ${price:.2f})."

    # Use fuzzy matching to find the item
    actual_name, item_obj = find_item_in_storage(storage, item_name)

    if actual_name and storage.update_price(actual_name, price):
        return f"Set price for '{actual_name}' to ${price:.2f}."
    else:
        available_items = storage.list_all_items()
        if available_items:
            items_list = ", ".join(available_items[:5])
            return f"Item '{item_name}' not found in storage. Available: {items_list}"
        else:
            return f"Item '{item_name}' not found. Storage is empty."


# Tools schema for LiteLLM function calling
TOOLS_LIST = [
    {
        "type": "function",
        "function": {
            "name": "wait_for_next_day",
            "description": "Advance simulation time to 6:00 AM of the next day. This will process daily fees, update weather, and provide a new day report.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email to a supplier or business contact. Use this to place orders, ask questions, or communicate with vendors.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {
                        "type": "string",
                        "description": "Email address of the recipient (e.g., 'supplier@vendcorp.com')",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Subject line for the email",
                    },
                    "body": {
                        "type": "string",
                        "description": "The main content of the email message",
                    },
                },
                "required": ["recipient", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_email",
            "description": "Read all unread emails in your inbox. This will show new supplier responses, delivery notifications, and other business correspondence.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_storage_quantities",
            "description": "Check the current inventory in your backroom storage. Shows all items with quantities, costs, and total values.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scratchpad_write",
            "description": "Write text to your scratchpad for note-taking. Text is appended to existing content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to write to the scratchpad",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_scratchpad",
            "description": "Read the full contents of your scratchpad.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "erase_scratchpad",
            "description": "Clear all content from your scratchpad.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_kw_value",
            "description": "Get a value from the persistent key-value store.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "The key to look up",
                    },
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_kw_value",
            "description": "Set a value in the persistent key-value store.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "The key to set",
                    },
                    "value": {
                        "type": "string",
                        "description": "The value to store",
                    },
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_kw_value",
            "description": "Delete a key from the persistent key-value store.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "The key to delete",
                    },
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_vector_db",
            "description": "Add a text document to the vector database for later semantic search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text document to store",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_vector_db",
            "description": "Search the vector database for documents similar to your query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 3)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_machine_inventory",
            "description": "View the current vending machine inventory. Shows which slots are empty (available for stocking) and which are occupied. Use this before calling stock_machine to find available slots.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_money_balance",
            "description": "Check your current money balance.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ai_web_search",
            "description": "Search the web for information about suppliers, products, pricing, or any other business-related queries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stock_machine",
            "description": "Move items from backroom storage into a vending machine slot. IMPORTANT: Each slot can only hold ONE product type. If a slot already has a different item, you must choose a different slot. Use get_machine_inventory first to find empty slots. You can use shortened product names - the system will match them intelligently.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {
                        "type": "string",
                        "description": "Product name (e.g., 'snickers', 'trail mix', 'bottled water'). The system will match this to the supplier's actual item name automatically.",
                    },
                    "slot_id": {
                        "type": "string",
                        "description": "Vending machine slot ID (e.g., '0-0', '1-2', '2-1'). Rows 0-1 are small items, rows 2-3 are large items. TIP: Use get_machine_inventory to see which slots are empty.",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of units to stock (max 10 per slot)",
                    },
                },
                "required": ["item_name", "slot_id", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_item_price",
            "description": "Set the selling price for an item in backroom storage. IMPORTANT: You must set prices for items after they arrive and before stocking them in the vending machine, or they will have $0.00 price and generate no revenue. You can use shortened product names - the system will match them intelligently.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {
                        "type": "string",
                        "description": "Product name (e.g., 'snickers', 'trail mix', 'bottled water'). The system will match this to the supplier's actual item name automatically.",
                    },
                    "price": {
                        "type": "number",
                        "description": "Selling price in dollars (e.g., 2.50 for $2.50)",
                    },
                },
                "required": ["item_name", "price"],
            },
        },
    },
]

# Tools function mapping
TOOLS_FUNCTIONS = {
    "wait_for_next_day": wait_for_next_day,
    "send_email": send_email,
    "read_email": read_email,
    "check_storage_quantities": check_storage_quantities,
    "scratchpad_write": scratchpad_write,
    "read_scratchpad": read_scratchpad,
    "erase_scratchpad": erase_scratchpad,
    "get_kw_value": get_kw_value,
    "set_kw_value": set_kw_value,
    "delete_kw_value": delete_kw_value,
    "add_to_vector_db": add_to_vector_db,
    "search_vector_db": search_vector_db,
    "get_machine_inventory": get_machine_inventory,
    "get_money_balance": get_money_balance,
    "ai_web_search": ai_web_search,
    "stock_machine": stock_machine,
    "set_item_price": set_item_price,
}


def execute_tool(tool_call, simulation_ref):
    """
    Execute a single tool call and return formatted result.

    Args:
        tool_call: Tool call object (can be object-style with .function or dict-style with ['function'])
        simulation_ref: Reference to the VendingMachineSimulation instance

    Returns:
        dict: {
            "success": bool,
            "message": str,
            "console_output": str
        }
    """
    import json

    # Handle both object-style and dict-style tool calls
    if hasattr(tool_call, "function"):
        # Object-style (e.g., from LiteLLM)
        function_name = tool_call.function.name
        arguments_str = (
            tool_call.function.arguments if tool_call.function.arguments else None
        )
    else:
        # Dict-style (e.g., from Cerebras API)
        function_name = tool_call["function"]["name"]
        arguments_str = tool_call["function"].get("arguments")

    # Parse arguments with error handling
    try:
        arguments = json.loads(arguments_str) if arguments_str else {}
    except json.JSONDecodeError as e:
        error_msg = f"❌ Tool call arguments contain invalid JSON: {e}"
        print(error_msg)
        print(f"   Function: {function_name}")
        print(f"   Arguments string: {arguments_str[:200]}...")  # Show first 200 chars
        return {
            "success": False,
            "message": f"\n\n[Tool error: {function_name} - Invalid JSON in arguments: {e}]",
            "console_output": error_msg,
        }

    console_output = f"🔧 Executing tool: {function_name}"
    print(console_output)

    # Execute the tool
    if function_name in TOOLS_FUNCTIONS:
        try:
            # Filter arguments to only include parameters the function accepts
            import inspect
            func = TOOLS_FUNCTIONS[function_name]
            sig = inspect.signature(func)
            # Get parameter names (excluding simulation_ref which is always first)
            accepted_params = [p for p in sig.parameters.keys() if p != 'simulation_ref']
            # Filter arguments to only include accepted parameters
            filtered_arguments = {k: v for k, v in arguments.items() if k in accepted_params}

            tool_result = TOOLS_FUNCTIONS[function_name](simulation_ref, **filtered_arguments)
            success_msg = f"✅ Tool result: {tool_result}"
            print(success_msg)

            return {
                "success": True,
                "message": f"\n\n[Tool executed: {function_name} - {tool_result}]",
                "console_output": f"{console_output}\n{success_msg}",
            }

        except Exception as e:
            error_msg = f"❌ Tool execution failed: {e}"
            print(error_msg)

            return {
                "success": False,
                "message": f"\n\n[Tool error: {function_name} - Tool execution failed: {e}]",
                "console_output": f"{console_output}\n{error_msg}",
            }
    else:
        error_msg = f"❌ Unknown tool: {function_name}"
        print(error_msg)

        return {
            "success": False,
            "message": f"\n\n[Tool error: Unknown tool {function_name}]",
            "console_output": f"{console_output}\n{error_msg}",
        }


# =============================
# Supplier tools (used by EmailSystem)
# =============================


def supplier_schedule_delivery(
    simulation_ref,
    days_until_delivery: int,
    supplier: str = "Supplier",
    reference: str | None = None,
    items=None,
):
    """
    Supplier-side tool to schedule a delivery into the simulation.
    items: list of {name, size, quantity, unit_cost}
    """
    if items is None:
        items = []
    arrival = simulation_ref.storage.schedule_delivery(
        current_time=simulation_ref.current_time,
        items=items,
        days_until_delivery=int(days_until_delivery),
        supplier=supplier,
        reference=reference,
    )
    return f"Delivery scheduled for {arrival.isoformat()}"


SUPPLIER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "schedule_delivery",
            "description": "Schedule a shipment to the agent's business. Include days_until_delivery and the items being shipped.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_until_delivery": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Days from now until delivery",
                    },
                    "supplier": {
                        "type": "string",
                        "description": "Supplier name or identifier",
                    },
                    "reference": {
                        "type": "string",
                        "description": "Optional reference/PO number",
                    },
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "size": {"type": "string", "enum": ["small", "large"]},
                                "quantity": {"type": "integer", "minimum": 1},
                                "unit_cost": {"type": "number", "minimum": 0},
                            },
                            "required": ["name", "size", "quantity", "unit_cost"],
                        },
                        "minItems": 1,
                    },
                },
                "required": ["days_until_delivery", "items"],
            },
        },
    }
]

SUPPLIER_TOOLS_FUNCTIONS = {
    "schedule_delivery": supplier_schedule_delivery,
}


def execute_supplier_tool(tool_call, simulation_ref):
    """
    Execute a single supplier tool call and return formatted result.
    Mirrors execute_tool but for supplier tools.
    """
    # Handle both object-style and dict-style tool calls
    if hasattr(tool_call, "function"):
        function_name = tool_call.function.name
        arguments_str = (
            tool_call.function.arguments if tool_call.function.arguments else None
        )
    else:
        function_name = tool_call["function"]["name"]
        arguments_str = tool_call["function"].get("arguments")

    arguments = json.loads(arguments_str) if arguments_str else {}

    console_output = f"🔧 Executing supplier tool: {function_name}"
    print(console_output)

    if function_name in SUPPLIER_TOOLS_FUNCTIONS:
        try:
            tool_result = SUPPLIER_TOOLS_FUNCTIONS[function_name](
                simulation_ref, **arguments
            )
            success_msg = f"✅ Tool result: {tool_result}"
            print(success_msg)
            return {
                "success": True,
                "message": f"\n\n[Supplier tool: {function_name} - {tool_result}]",
                "console_output": f"{console_output}\n{success_msg}",
            }
        except Exception as e:
            error_msg = f"❌ Supplier tool execution failed: {e}"
            print(error_msg)
            return {
                "success": False,
                "message": f"\n\n[Supplier tool error: {function_name} - {e}]",
                "console_output": f"{console_output}\n{error_msg}",
            }
    else:
        error_msg = f"❌ Unknown supplier tool: {function_name}"
        print(error_msg)
        return {
            "success": False,
            "message": f"\n\n[Supplier tool error: Unknown tool {function_name}]",
            "console_output": f"{console_output}\n{error_msg}",
        }
