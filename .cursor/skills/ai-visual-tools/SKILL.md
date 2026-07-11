---
name: ai-visual-tools
description: Visual/low-code AI prototyping tools — Flowise (drag-and-drop LangChain/LlamaIndex flows, REST API, Docker) and Langflow (Python-based visual editor, component system, MCP server, REST API, Tweaks override). Use when rapidly prototyping LLM pipelines without heavy code, building chatbots, or exposing AI flows via REST API.
metadata:
  origin: sergiomc12-fork
---

# Visual AI Tools: Flowise · Langflow

## Comparison

| Feature | Flowise | Langflow |
|---------|---------|---------|
| **Language** | Node.js (TypeScript) | Python |
| **Focus** | LangChain/LlamaIndex flows | General LLM orchestration |
| **Self-host** | npm / Docker | pip / Docker |
| **Custom components** | JS/TS + npm packages | Python `@component` decorator |
| **MCP support** | Limited | Yes (expose as MCP server) |
| **API** | `/api/v1/prediction/{id}` | `/api/v1/run/{id}` |
| **Auth** | API key header | API key header |
| **Best for** | LangChain-heavy workflows | Flexible Python AI pipelines |

---

## Flowise

### What It Is

Flowise is an open-source, drag-and-drop UI to build **LangChain** and **LlamaIndex** pipelines visually. Flows are called **Chatflows** (single LLM chain) or **Agentflows** (multi-agent with tools).

### Installation

**npm (local):**
```bash
npm install -g flowise
npx flowise start
# Access at http://localhost:3000
```

**Docker:**
```bash
docker run -d \
  --name flowise \
  -p 3000:3000 \
  -v ~/.flowise:/root/.flowise \
  flowiseai/flowise:latest
```

**Docker Compose:**
```yaml
services:
  flowise:
    image: flowiseai/flowise:latest
    ports:
      - "3000:3000"
    environment:
      - DATABASE_PATH=/root/.flowise
      - APIKEY_PATH=/root/.flowise
      - SECRETKEY_PATH=/root/.flowise
      - LOG_PATH=/root/.flowise/logs
      - BLOB_STORAGE_PATH=/root/.flowise/storage
    volumes:
      - ~/.flowise:/root/.flowise
```

### Node Categories

| Category | Examples |
|----------|---------|
| **LLM** | OpenAI, Anthropic Claude, Google Gemini, Ollama, Azure OpenAI |
| **Chain** | LLMChain, ConversationalRetrievalQAChain, APIChain |
| **Agent** | OpenAI Function Agent, ReAct Agent, Conversational Agent |
| **Tool** | Calculator, WebBrowser, SerpAPI, DuckDuckGoSearch, Custom Tool |
| **Memory** | BufferMemory, ConversationSummaryMemory, ZepMemory, MotorheadMemory |
| **Vector Store** | Chroma, Pinecone, Qdrant, Weaviate, pgvector, Faiss, Redis |
| **Document Loader** | PDF, CSV, Notion, Confluence, GitHub, Apify Web Scraper |
| **Text Splitter** | RecursiveCharacterTextSplitter, TokenTextSplitter |
| **Embedding** | OpenAI Embeddings, HuggingFace, Cohere, Ollama |
| **Retriever** | Vector Store Retriever, MultiQuery Retriever, Contextual Compression |

### REST API

Every Chatflow exposes a prediction endpoint. Get the `chatflowId` from the URL in the UI.

**Prediction (non-streaming):**
```bash
curl -X POST \
  "http://localhost:3000/api/v1/prediction/<chatflowId>" \
  -H "Authorization: Bearer <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is quantum computing?",
    "overrideConfig": {
      "sessionId": "user-session-123"
    }
  }'
```

**Python client:**
```python
import os
import requests

FLOWISE_URL = os.environ["FLOWISE_URL"]      # e.g. http://localhost:3000
FLOWISE_API_KEY = os.environ["FLOWISE_API_KEY"]
CHATFLOW_ID = os.environ["FLOWISE_CHATFLOW_ID"]

def query_flowise(question: str, session_id: str = "default") -> str:
    response = requests.post(
        f"{FLOWISE_URL}/api/v1/prediction/{CHATFLOW_ID}",
        headers={
            "Authorization": f"Bearer {FLOWISE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "question": question,
            "overrideConfig": {
                "sessionId": session_id,
                "returnSourceDocuments": True,
            },
        },
    )
    response.raise_for_status()
    data = response.json()
    return data.get("text", "")

answer = query_flowise("Explain RAG in simple terms.", session_id="user-42")
print(answer)
```

**Streaming:**
```python
import httpx

async def stream_flowise(question: str, chatflow_id: str):
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{FLOWISE_URL}/api/v1/prediction/{chatflow_id}",
            headers={"Authorization": f"Bearer {FLOWISE_API_KEY}"},
            json={"question": question, "streaming": True},
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    print(line[6:], end="", flush=True)
```

**File/document upload:**
```python
import requests

with open("document.pdf", "rb") as f:
    response = requests.post(
        f"{FLOWISE_URL}/api/v1/prediction/{CHATFLOW_ID}",
        headers={"Authorization": f"Bearer {FLOWISE_API_KEY}"},
        files={"files": ("document.pdf", f, "application/pdf")},
        data={"question": "Summarize this document"},
    )
```

**Vector store upsert:**
```python
# Push documents to an in-flow vector store
response = requests.post(
    f"{FLOWISE_URL}/api/v1/vector/upsert/{CHATFLOW_ID}",
    headers={"Authorization": f"Bearer {FLOWISE_API_KEY}"},
    json={
        "overrideConfig": {
            "returnSourceDocuments": False,
        },
    },
    files={"files": ("data.pdf", open("data.pdf", "rb"), "application/pdf")},
)
```

### Custom Tool

Flowise custom tools are JavaScript functions exposed to agents:

```javascript
// Custom tool in Flowise UI → Tools → Add Tool
// Name: get_product_info
// Description: Get product details by SKU

const fetch = require('node-fetch');

const response = await fetch(`https://api.myshop.com/products/${$input}`, {
    headers: { 'Authorization': `Bearer ${process.env.SHOP_API_KEY}` }
});
const data = await response.json();
return JSON.stringify({ name: data.name, price: data.price, stock: data.stock });
```

### Embed in Web App

```html
<!-- Embed chatbot widget -->
<script type="module">
    import Chatbot from 'https://cdn.jsdelivr.net/npm/flowise-embed/dist/web.js';
    Chatbot.init({
        chatflowid: '<chatflowId>',
        apiHost: 'http://localhost:3000',
        chatflowConfig: {
            sessionId: 'user-123',
            returnSourceDocuments: true,
        },
        theme: {
            button: { backgroundColor: '#0d47a1' },
            chatWindow: { title: 'AI Assistant' },
        },
    });
</script>
```

---

## Langflow

### What It Is

Langflow is an open-source, Python-based visual editor for building LLM pipelines. Components are Python classes connected in a DAG; the full pipeline runs as a Python process exposed via REST API. Supports **MCP server** exposure.

### Installation

**pip:**
```bash
pip install langflow
langflow run           # starts at http://localhost:7860
# or
python -m langflow run --host 0.0.0.0 --port 7860
```

**Docker:**
```bash
docker run -it \
  --rm \
  -p 7860:7860 \
  langflowai/langflow:latest
```

**Python (embedding in a script):**
```bash
pip install langflow-base
```

### Component Architecture

Langflow components are Python classes. Visual editor generates a JSON flow that Langflow executes:

```
[Input] → [LLM Component] → [Prompt Template] → [Output]
                ↑
         [Vector Store Retriever]
```

**Component types available in UI:**

| Category | Examples |
|----------|---------|
| **LLMs** | OpenAI, Anthropic, Google Gemini, Azure OpenAI, Ollama, Cohere |
| **Prompts** | Prompt Template, System Message |
| **Agents** | Agent, ReAct Agent, Tool Calling Agent |
| **Tools** | Calculator, Search (SerpAPI, Tavily), URL Fetcher, Python REPL |
| **Memory** | In-Memory Store, Astra DB Memory, Upstash Redis Memory |
| **Vector Stores** | Chroma, Pinecone, Qdrant, Weaviate, pgvector, FAISS, Astra DB |
| **Document Loaders** | File, URL, GitHub, Confluence, Notion, S3 |
| **Embeddings** | OpenAI, HuggingFace, Cohere, Ollama |
| **Outputs** | Chat Output, Text Output, Data Output |

### REST API

Get your `flow_id` from the URL when viewing a flow in the UI.

**Run a flow (non-streaming):**
```bash
curl -X POST \
  "http://localhost:7860/api/v1/run/<flow_id>" \
  -H "x-api-key: <langflow-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "input_value": "What is RAG?",
    "input_type": "chat",
    "output_type": "chat",
    "session_id": "user-session-123"
  }'
```

**Python client:**
```python
import os
import requests

LANGFLOW_URL = os.environ.get("LANGFLOW_URL", "http://localhost:7860")
LANGFLOW_API_KEY = os.environ["LANGFLOW_API_KEY"]
FLOW_ID = os.environ["LANGFLOW_FLOW_ID"]

def run_flow(
    message: str,
    flow_id: str = FLOW_ID,
    session_id: str = "default",
    tweaks: dict | None = None,
) -> str:
    payload = {
        "input_value": message,
        "input_type": "chat",
        "output_type": "chat",
        "session_id": session_id,
    }
    if tweaks:
        payload["tweaks"] = tweaks

    response = requests.post(
        f"{LANGFLOW_URL}/api/v1/run/{flow_id}",
        headers={
            "x-api-key": LANGFLOW_API_KEY,
            "Content-Type": "application/json",
        },
        json=payload,
    )
    response.raise_for_status()
    data = response.json()
    # Extract text from nested response
    return data["outputs"][0]["outputs"][0]["outputs"]["message"]["message"]

answer = run_flow("Explain quantum computing in simple terms.")
print(answer)
```

### Tweaks API (Override Components at Runtime)

Override any component parameter without modifying the saved flow:

```python
# Get component IDs from the flow JSON (File → Export)
tweaks = {
    "OpenAI-abc12": {
        "model_name": "gpt-4o",           # upgrade model for this request
        "temperature": 0.0,
    },
    "Chroma-xyz34": {
        "number_of_results": 8,           # retrieve more docs
    },
    "SystemMessage-def56": {
        "message": "You are a Python expert.",  # override system prompt
    },
}

answer = run_flow("How do I use async in Python?", tweaks=tweaks)
```

### Custom Component (Python)

```python
# Save as a .py file, then upload via UI: Components → Custom → Upload
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message

class MyCustomComponent(Component):
    display_name = "Product Lookup"
    description = "Look up product information from our catalog."

    inputs = [
        MessageTextInput(
            name="product_sku",
            display_name="Product SKU",
            info="Enter the product SKU to look up.",
        ),
    ]

    outputs = [
        Output(display_name="Product Info", name="product_info", method="lookup_product"),
    ]

    def lookup_product(self) -> Message:
        sku = self.product_sku
        # Call internal API
        product = self._fetch_product(sku)
        return Message(text=f"{product['name']}: ${product['price']}")

    def _fetch_product(self, sku: str) -> dict:
        import requests
        r = requests.get(f"https://api.myshop.com/products/{sku}")
        return r.json()
```

### Streaming

```python
import httpx
import json

async def stream_langflow(message: str, flow_id: str):
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            f"{LANGFLOW_URL}/api/v1/run/{flow_id}?stream=true",
            headers={"x-api-key": LANGFLOW_API_KEY},
            json={"input_value": message, "input_type": "chat", "output_type": "chat"},
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunk = json.loads(line[6:])
                    if "chunk" in chunk:
                        print(chunk["chunk"], end="", flush=True)
```

### MCP Server Exposure

Langflow can expose flows as an MCP (Model Context Protocol) server, letting Claude or any MCP client call your flows as tools:

```bash
# Start Langflow as MCP server
python -m langflow run --mcp

# Or configure in Claude Code settings.json:
# {
#   "mcpServers": {
#     "langflow": {
#       "command": "python",
#       "args": ["-m", "langflow", "run", "--mcp"],
#       "env": {"LANGFLOW_API_KEY": "..."}
#     }
#   }
# }
```

### Exporting and Running Flows Programmatically

```python
# Export a flow from UI as JSON, then run it in Python without UI
from langflow.load import run_flow_from_json

result = run_flow_from_json(
    flow="my_flow.json",
    input_value="What is quantum computing?",
    session_id="user-session-1",
    fallback_to_env_vars=True,   # use env vars for API keys
    tweaks={
        "OpenAI-abc12": {"model_name": "gpt-4o-mini"},
    },
)
```

---

## Quick Decision Guide

```
I need to prototype a RAG chatbot in 30 minutes?
    → Flowise (drag-drop Chatflow with PDF loader + vector store + LLM)

I want to expose my Python AI pipeline as a REST API?
    → Langflow (build in UI, call via /api/v1/run)

I need an MCP tool that calls my pipeline from Claude Code?
    → Langflow (--mcp flag)

I need to embed a chat widget in my website?
    → Flowise (flowise-embed CDN widget)

My team prefers Node.js and LangChain?
    → Flowise

My team prefers Python and flexible LLM support?
    → Langflow

I need to override flow parameters at runtime (A/B test models)?
    → Langflow (Tweaks API)
```

## Related Skills
- [[python-ai-agents]] — For when visual tools aren't enough and you need code-level control
- [[llm-observability]] — Add Langfuse/LangSmith tracing to your Flowise/Langflow pipelines
- [[pgvector-rag-patterns]] — Vector store configuration for RAG nodes in Flowise/Langflow
