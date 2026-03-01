
import os
import json
import re
from collections import defaultdict, deque
from urllib.parse import urlparse
from openai import OpenAI
from dotenv import load_dotenv

from .tools import search_products

load_dotenv()

GROQ_API_KEY = os.getenv("Groq_API_KEY_1")  # use your actual variable name

if not GROQ_API_KEY:
    raise ValueError("Groq API key not found in environment variables.")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)
SYSTEM_PROMPT = """
You are an AI shopping assistant for EpicOutlet ecommerce website.

Rules:
- You ONLY answer questions about products available on this website.
- You MUST use the search_products tool to get product information.
- NEVER invent products.
- If a question is unrelated to ecommerce or products, politely refuse.
- Always include the exact product URL provided by the tool.
- Format your response using proper Markdown.
- If you are listing multiple products, you MUST use a proper Markdown table (using `|` for columns).
- Do NOT provide raw or bare URLs. Make the product name a clickable Markdown link using the format `[Product Name](/collection/<category>/<product>/)`.
- Put the markdown link directly inside the table or text. Do NOT list the product links separately at the end.
- If the tool returns one or more products, DO NOT say "not found"; present those products as available options.
- If the requested keyword is unavailable but related category products are returned, clearly say they are alternatives and list them.
"""
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search for products in the ecommerce store.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "category": {"type": "string"},
                    "min_price": {"type": "integer"},
                    "max_price": {"type": "integer"},
                    "vendor": {"type": "string"},
                    "trending": {"type": "boolean"},
                    "limit": {"type": "integer"},
                    "sort": {"type": "string"}
                }
            }
        }
    }
]

# Keep lightweight in-memory chat history for follow-up questions.
_CONVERSATION_HISTORY = defaultdict(lambda: deque(maxlen=12))


def _normalize_links_to_paths(text: str, products: list) -> str:
    def to_path(url: str) -> str:
        if url.startswith("/"):
            return url
        parsed = urlparse(url)
        return parsed.path or url

    cleaned = text or ""
    cleaned = re.sub(
        r"https?://[^\s)\]]+",
        lambda m: to_path(m.group(0)),
        cleaned,
    )

    if products:
        product_urls = [p.get("url", "") for p in products if isinstance(p, dict) and p.get("url")]
        if product_urls and not any(url in cleaned for url in product_urls):
            lines = ["", "Product links:"]
            for product in products:
                if isinstance(product, dict) and product.get("url"):
                    lines.append(f"- {product.get('name', 'Product')}: {to_path(product['url'])}")
            cleaned = cleaned.rstrip() + "\n\n" + "\n".join(lines)

    return cleaned


def chat_with_ai(user_message: str, conversation_id: str = "default", is_admin: bool = False):
    history = list(_CONVERSATION_HISTORY[conversation_id])
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": user_message},
    ]
    latest_products = []

    try:
        # Allow multiple tool rounds so follow-up tool calls do not fail.
        for _ in range(5):
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
            message = response.choices[0].message
            messages.append(message)

            if not message.tool_calls:
                assistant_text = _normalize_links_to_paths(message.content or "", latest_products)
                _CONVERSATION_HISTORY[conversation_id].append({"role": "user", "content": user_message})
                _CONVERSATION_HISTORY[conversation_id].append({"role": "assistant", "content": assistant_text})
                return assistant_text

            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments or "{}")

                if function_name == "search_products":
                    tool_result = search_products(**arguments)
                    if isinstance(tool_result, list):
                        latest_products = tool_result
                else:
                    tool_result = {"error": f"Unknown tool: {function_name}"}

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result),
                    }
                )

        return "I apologize, but I could not complete the request after multiple tool calls. Please try rephrasing your query."
    except Exception as e:
        error_msg = str(e)
        if "rate_limit_exceeded" in error_msg.lower() or "429" in error_msg:
            if is_admin:
                return f"I encountered an unexpected error: {error_msg}"
            return "EpiOutlet server down, Please wait for few minutes"
            
        if "tool_use_failed" in error_msg:
            return "I apologize, but I had trouble processing your search request. Could you please rephrase it slightly? For example: 'Show me mobile phones under 35000'."
        return f"I encountered an unexpected error: {error_msg}"
