import requests
import json
import os
from typing import Optional
import litellm


def call_claude_model(prompt: str, system_prompt: str = "") -> str:
    """
    Call Claude Sonnet model with a prompt and return the response

    Args:
        prompt: The text prompt to send to Claude

    Returns:
        The model's response as a string
    """

    # Get API key from parameter or environment
    api_key = os.environ["ANTHROPIC_API_KEY"]
    if not api_key:
        raise ValueError(
            "API key must be provided or set in ANTHROPIC_API_KEY environment variable"
        )

    # API endpoint
    url = "https://api.anthropic.com/v1/messages"

    # Headers
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    # Request payload
    payload = {
        "model": "claude-sonnet-4-20250514",  # Latest Sonnet model
        "max_tokens": 1000,
        "system": system_prompt,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        # Make the API request
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise exception for bad status codes

        # Parse response
        response_data = response.json()

        # Extract the text content from the response
        if "content" in response_data and len(response_data["content"]) > 0:
            return response_data["content"][0]["text"]
        else:
            return "No response content received"

    except requests.exceptions.RequestException as e:
        return f"API request failed: {str(e)}"
    except json.JSONDecodeError as e:
        return f"Failed to parse response JSON: {str(e)}"
    except KeyError as e:
        return f"Unexpected response format: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


def call_claude_with_fallback(prompt: str) -> str:
    """
    Call Claude with fallback to mock response if API fails
    Useful for development/testing when API key isn't available
    """
    try:
        return call_claude_model(prompt)
    except (ValueError, Exception) as e:
        # Fallback to mock response for development
        print(f"API call failed ({e}), using mock response")
        return "Mock response: -1.0,2.00,10"  # Example format for economic analysis


def call_model_litellm(
    prompt: str,
    model: str = "claude-3-5-sonnet-20241022",
    system_prompt: str = "",
    tools: Optional[list] = None,
) -> dict:
    """Unified Litellm call that forwards Cerebras models to the Cerebras wrapper."""
    # If the requested model is a Cerebras model, route it directly.
    if model.lower().startswith("cerebras"):
        # Expected format: "cerebras/<model_name>" or just "cerebras"
        parts = model.split("/", 1)
        cerebras_model_name = parts[1] if len(parts) > 1 else "llama3.1-8b"
        return call_cerebras_model(
            prompt,
            system_prompt=system_prompt,
            model_name=cerebras_model_name,
            tools=tools,
        )

    """
    Call model using LiteLLM unified interface with optional tools support.
    """
    # Build the messages payload
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    completion_params = {
        "model": model,
        "messages": messages,
        "max_tokens": 1000,
    }
    if tools:
        completion_params["tools"] = tools

    try:
        response = litellm.completion(**completion_params)
        # litellm returns a dict‑like object; use bracket notation to avoid type‑checking issues
        first_choice = response["choices"][0]
        message = first_choice["message"]
        tool_calls = message.get("tool_calls")
        if tool_calls and len(tool_calls) > 1:
            print(
                f"🔧 Multiple tool calls detected ({len(tool_calls)}), using first only"
            )
            tool_calls = [tool_calls[0]]

        # Convert Pydantic tool_calls to dicts for JSON serialization
        if tool_calls:
            serializable_tool_calls = []
            for tc in tool_calls:
                if hasattr(tc, 'model_dump'):
                    # Pydantic v2
                    serializable_tool_calls.append(tc.model_dump())
                elif hasattr(tc, 'dict'):
                    # Pydantic v1
                    serializable_tool_calls.append(tc.dict())
                elif isinstance(tc, dict):
                    # Already a dict
                    serializable_tool_calls.append(tc)
                else:
                    # Fallback: convert object to dict
                    serializable_tool_calls.append(vars(tc))
            tool_calls = serializable_tool_calls

        return {"content": message.get("content", ""), "tool_calls": tool_calls}
    except Exception as e:
        # Provide a mock response for authentication errors to keep the simulation running
        if "AuthenticationError" in str(e) or "invalid x-api-key" in str(e):
            print("⚠️ LiteLLM auth failed – using mock response")
            return {
                "content": "Mock response from LiteLLM (auth error)",
                "tool_calls": None,
            }
        # Otherwise return the original error message
        return {
            "content": "Error: LiteLLM request failed: " + str(e),
            "tool_calls": None,
        }


from typing import Union


def call_cerebras_model(
    prompt: str,
    system_prompt: str = "",
    model_name: str = "gpt-oss-120b",
    max_tokens: int = 1000,
    temperature: float = 0.7,
    tools: Optional[list] = None,
) -> Union[str, dict]:
    """Call a Cerebras model via the official SDK (or fallback to raw HTTP).

    Args:
        prompt: The user prompt.
        system_prompt: Optional system message.
        model_name: Cerebras model identifier (e.g., "llama3.1-8b").
        max_tokens: Max tokens to generate.
        temperature: Sampling temperature.
        tools: Optional list of tool schemas for function calling.
    Returns:
        Dict with "content" and "tool_calls" keys.
    """
    import os

    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        raise ValueError("CEREBRAS_API_KEY must be set in the environment")

    # Build messages list
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # Try the official SDK first
    try:
        try:
            from cerebras.cloud.sdk import Cerebras
        except ModuleNotFoundError:
            # Simple stub Cerebras class when SDK is not installed.
            import types, sys

            dummy_sdk = types.ModuleType("cerebras.cloud.sdk")

            class DummyCerebras:
                def __init__(self, api_key: str):
                    self.api_key = api_key
                    self.chat = types.SimpleNamespace(
                        completions=types.SimpleNamespace(create=lambda *a, **k: None)
                    )

            dummy_sdk.Cerebras = DummyCerebras
            # Register stub packages in sys.modules
            sys.modules.setdefault("cerebras", types.ModuleType("cerebras"))
            sys.modules.setdefault("cerebras.cloud", types.ModuleType("cerebras.cloud"))
            sys.modules["cerebras.cloud.sdk"] = dummy_sdk
            Cerebras = DummyCerebras

        client = Cerebras(api_key=api_key)
        completion_kwargs = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            completion_kwargs["tools"] = tools
        response = client.chat.completions.create(**completion_kwargs)

        # Process the SDK response (or lack thereof)
        if response is None:
            # No SDK response – treat as mock content.
            content = "[Mock Cerebras response – SDK not available]"
        else:
            message = response.choices[0].message
            content = getattr(message, "content", "") or ""
            tool_calls = getattr(message, "tool_calls", None)

            if tool_calls and len(tool_calls) > 1:
                tool_calls = [tool_calls[0]]

            # Convert Pydantic tool_calls to dicts for JSON serialization
            if tool_calls:
                serializable_tool_calls = []
                for tc in tool_calls:
                    if hasattr(tc, 'model_dump'):
                        # Pydantic v2
                        serializable_tool_calls.append(tc.model_dump())
                    elif hasattr(tc, 'dict'):
                        # Pydantic v1
                        serializable_tool_calls.append(tc.dict())
                    elif isinstance(tc, dict):
                        # Already a dict
                        serializable_tool_calls.append(tc)
                    else:
                        # Fallback: convert object to dict
                        serializable_tool_calls.append(vars(tc))
                tool_calls = serializable_tool_calls

            # When the caller does not request tool support, return just the content string.
            if tools is None:
                return content
            return {"content": content, "tool_calls": tool_calls}

        # If we reach here we are returning a mock response because the SDK gave None.
        if tools is None:
            return content
        return {"content": content, "tool_calls": None}
    except Exception as e:
        # Fallback to raw HTTP
        import json, requests

        url = "https://api.cerebras.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            message_data = data["choices"][0]["message"]

            content = message_data.get("content", "") or message_data.get(
                "reasoning", ""
            )
            tool_calls = message_data.get("tool_calls")

            if tool_calls and len(tool_calls) > 1:
                tool_calls = [tool_calls[0]]

            return {"content": content, "tool_calls": tool_calls}
        except Exception as e2:
            return {
                "content": "[Mock Cerebras response – network unreachable]",
                "tool_calls": None,
            }


def call_model(
    prompt: str,
    model_type: str = "cerebras/gpt-oss-120b",
    system_prompt: str = "",
    tools: list = None,
):
    """Universal model client using LiteLLM for a unified interface.

    Args:
        prompt: The text prompt to send to the model.
        model_type: Identifier for the model (e.g., "claude", "gpt-4", "cerebras").
        system_prompt: Optional system message.
        tools: Optional list of tool schemas for function calling.

    Returns:
        A dict ``{"content": <str>, "tool_calls": <list|None>}`` – even when no tools are
        requested – to keep the return type consistent across all back‑ends.
    """

    # Map common model shortcuts to their Litellm identifiers.
    model_mapping = {
        "claude-4-opus": "anthropic/claude-opus-4-20250514",
        "claude-4-sonnet": "anthropic/claude-sonnet-4-20250514",
        "grok-3-beta": "xai/grok-3-beta",
        "grok-3-mini": "xai/grok-3-mini-beta",
        "o3-mini": "openai/o3-mini",
        "o3-pro": "openai/o3-pro",
        "gpt-4o": "openai/gpt-4o",
        "gemini-2.5-pro": "vertex_ai/gemini-2.5-pro",
        "gemini-2.5-flash": "vertex_ai/gemini-2.5-flash",
        "cerebras": "cerebras/gpt-oss-120b",
        "cerebras-gpt-oss-120b": "cerebras/gpt-oss-120b",
    }

    litellm_model = model_mapping.get(model_type.lower(), model_type)

    try:
        # Route Cerebras models through the dedicated wrapper.
        if "cerebras" in litellm_model.lower():
            model_name = (
                litellm_model.split("/", 1)[1]
                if "/" in litellm_model
                else "gpt-oss-120b"
            )
            result = call_cerebras_model(
                prompt, system_prompt=system_prompt, model_name=model_name, tools=tools
            )
            # ``call_cerebras_model`` may return a plain string when no tools are provided.
            # Normalize to the dict format expected by the rest of the code and tests.
            if isinstance(result, str):
                return {"content": result, "tool_calls": None}
            return result
        # All other models go via Litellm.
        result = call_model_litellm(prompt, litellm_model, system_prompt, tools)
        return result
    except Exception as e:
        raise ValueError(f"Model type '{model_type}' failed with LiteLLM: {e}")
