---
name: python-ai-agents
description: Python AI agent frameworks — LlamaIndex (RAG + Workflows), CrewAI (multi-agent crews), AutoGen (conversational multi-agent), Haystack (RAG pipelines), DSPy (prompt optimization), Pydantic AI (typed agents), smolagents (HuggingFace code agents), OpenAI Agents SDK, Semantic Kernel. Covers agent construction, tool calling, multi-agent orchestration, memory, structured output, and RAG integration for each framework. Use when building Python AI agents, pipelines, or choosing between orchestration frameworks.
metadata:
  origin: sergiomc12-fork
---

# Python AI Agent Frameworks

## Framework Selection Matrix

| Framework | Best For | Paradigm | LLM Agnostic | Key Strength |
|-----------|----------|----------|--------------|--------------|
| **LlamaIndex** | RAG over documents, data-backed agents | Index → Query | Yes | Richest data connectors + retrieval |
| **CrewAI** | Multi-role agent teams, business workflows | Crew → Roles → Tasks | Yes | Crew + role-playing + memory |
| **AutoGen** | Multi-agent conversations, code execution | Message-passing | Yes | Flexible conversational topology |
| **Haystack** | Production RAG pipelines, enterprise | Declarative Pipeline | Yes | Component DAG, battle-tested at scale |
| **DSPy** | Auto-optimizing prompts/chains | Signatures + Compile | Yes | Eliminates manual prompt engineering |
| **Pydantic AI** | Type-safe, production-grade agents | Agent + RunContext | Yes | Mypy/Pyright safe, Pydantic-native |
| **smolagents** | Minimal code agents, HF ecosystem | Code execution | Yes | Agents write Python to call tools |
| **OpenAI Agents SDK** | OpenAI-first, handoffs, guardrails | Agent + Runner | Partial | First-party SDK with tracing |
| **Semantic Kernel** | Enterprise .NET/Python SDK, plugins | Kernel + Plugins | Yes | Microsoft Azure integration |

---

## LlamaIndex

### Core Abstractions

- **Document** / **Node** — chunked text with metadata
- **VectorStoreIndex** — in-memory or persistent vector index
- **QueryEngine** — single-turn Q&A over an index
- **ChatEngine** — multi-turn conversation over an index
- **FunctionAgent** — agent with tools; async-first
- **Context** — persistent state across agent turns

### RAG Pipeline

```python
import os
os.environ["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]

from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    StorageContext,
    Settings,
    load_index_from_storage,
)
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding

# Global settings (replaces ServiceContext)
Settings.llm = OpenAI(model="gpt-4o-mini")
Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")

# Load documents
documents = SimpleDirectoryReader("data/").load_data()

# Build index
index = VectorStoreIndex.from_documents(documents)

# Query engine — response_mode: compact | refine | tree_summarize | accumulate
query_engine = index.as_query_engine(
    similarity_top_k=4,
    response_mode="tree_summarize",
)
response = query_engine.query("What are the main findings?")
print(response)

# Persist / reload
index.storage_context.persist("./storage")
storage_context = StorageContext.from_defaults(persist_dir="./storage")
index = load_index_from_storage(storage_context)
```

### Metadata Filtering

```python
from llama_index.core.vector_stores import (
    MetadataFilters,
    MetadataFilter,
    FilterOperator,
    FilterCondition,
)

filters = MetadataFilters(
    filters=[
        MetadataFilter(key="category", value="finance", operator=FilterOperator.EQ),
        MetadataFilter(key="year", value=2024, operator=FilterOperator.GTE),
    ],
    condition=FilterCondition.AND,
)
query_engine = index.as_query_engine(filters=filters)
```

### Agent with Tools

```python
import asyncio
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI

async def search_documents(query: str) -> str:
    """Search internal document database."""
    response = await query_engine.aquery(query)
    return str(response)

def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b

agent = FunctionAgent(
    tools=[multiply, search_documents],
    llm=OpenAI(model="gpt-4o-mini"),
    system_prompt="You are a helpful financial analyst.",
)

async def main():
    from llama_index.core.workflow import Context
    ctx = Context(agent)
    response = await agent.run("What are last year's total revenues?", ctx=ctx)
    print(str(response))

asyncio.run(main())
```

### Vector Store Backends

```python
# Chroma
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("docs")
vector_store = ChromaVectorStore(chroma_collection=collection)
index = VectorStoreIndex.from_documents(docs, vector_store=vector_store)

# Qdrant
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
q_client = QdrantClient(url=os.environ["QDRANT_URL"])
vector_store = QdrantVectorStore(client=q_client, collection_name="docs")

# pgvector
from llama_index.vector_stores.postgres import PGVectorStore
vector_store = PGVectorStore.from_params(
    database="mydb", host="localhost", password=os.environ["PG_PASSWORD"],
    port=5432, user="postgres", table_name="doc_embeddings", embed_dim=1536,
)
```

---

## CrewAI

### Core Components

```python
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from langchain_openai import ChatOpenAI

# Agent
researcher = Agent(
    role="Senior Research Analyst",
    goal="Uncover cutting-edge developments in AI",
    backstory="You are a renowned AI researcher...",
    llm=ChatOpenAI(model="gpt-4o"),      # or "gpt-4o" string shorthand
    tools=[search_tool, web_tool],
    memory=True,           # enable short-term + long-term memory
    verbose=True,
    allow_delegation=False,
    max_iter=10,           # max reasoning iterations
    max_rpm=20,            # rate limit
    cache=True,            # cache tool results
    reasoning=True,        # enable planning before execution
)

writer = Agent(
    role="Content Writer",
    goal="Write compelling AI articles",
    backstory="Expert technical writer...",
    llm="gpt-4o-mini",
)

# Task
research_task = Task(
    description="Research the top AI frameworks for 2024.",
    expected_output="A structured report with pros/cons per framework.",
    agent=researcher,
    async_execution=False,
)

write_task = Task(
    description="Write a 1000-word article based on {research}.",
    expected_output="A polished article in markdown.",
    agent=writer,
    context=[research_task],             # depends on research_task output
    output_file="article.md",
    # output_json=ArticleSchema,         # use Pydantic schema for JSON output
    # output_pydantic=ArticleSchema,
)

# Crew
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    process=Process.sequential,          # or Process.hierarchical
    verbose=True,
    memory=True,
    cache=True,
    max_rpm=40,
    output_log_file="crew_log.json",
    step_callback=lambda step: print(step),
    task_callback=lambda task: print(task.output),
)

result = crew.kickoff(inputs={"research": "initial context"})
print(result.raw)
print(result.token_usage)
```

### Hierarchical Process (Manager Agent)

```python
from crewai import Crew, Process

crew = Crew(
    agents=[researcher, writer, analyst],
    tasks=[...],
    process=Process.hierarchical,
    manager_llm=ChatOpenAI(model="gpt-4o"),  # required for hierarchical
    verbose=True,
)
```

### Custom Tool via BaseTool

```python
from crewai.tools import BaseTool
from pydantic import Field

class MySearchTool(BaseTool):
    name: str = "company_search"
    description: str = "Search company database by keyword."
    db_url: str = Field(default="postgresql://...")

    def _run(self, query: str) -> str:
        # call DB or API
        return f"Results for '{query}': ..."

tool = MySearchTool()
```

### Async & Parallel Execution

```python
import asyncio

# True native async
result = asyncio.run(crew.akickoff(inputs={"topic": "AI"}))

# Fan-out: run crew for each input item
results = crew.kickoff_for_each(inputs=[
    {"company": "OpenAI"},
    {"company": "Anthropic"},
])

# Async fan-out
results = asyncio.run(crew.akickoff_for_each(inputs=[...]))
```

### Memory Configuration

```python
from crewai import Crew
from crewai.memory import (
    ShortTermMemory,     # RAG-backed, in-run retrieval
    LongTermMemory,      # SQLite3, persists across runs
    EntityMemory,        # Structured entity knowledge
)

crew = Crew(
    agents=[...], tasks=[...],
    memory=True,   # enables all three memory types
    embedder={
        "provider": "openai",
        "config": {"model": "text-embedding-3-small"},
    },
)
```

---

## AutoGen (Microsoft)

### Single Agent

```python
import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient

model_client = OpenAIChatCompletionClient(
    model="gpt-4o",
    api_key=os.environ["OPENAI_API_KEY"],
)

async def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"Weather in {city}: 22°C, sunny"

agent = AssistantAgent(
    name="weather_agent",
    model_client=model_client,
    tools=[get_weather],
    system_message="You are a helpful weather assistant.",
    reflect_on_tool_use=True,
)

async def main():
    await Console(agent.run_stream(task="What's the weather in Paris?"))

asyncio.run(main())
```

### Multi-Agent Teams

```python
from autogen_agentchat.teams import (
    RoundRobinGroupChat,
    SelectorGroupChat,
    Swarm,
)
from autogen_agentchat.conditions import (
    MaxMessageTermination,
    TextMentionTermination,
    StopMessageTermination,
)
from autogen_agentchat.messages import HandoffMessage

# RoundRobin: agents take turns sequentially
team = RoundRobinGroupChat(
    participants=[writer_agent, critic_agent],
    termination_condition=TextMentionTermination("APPROVE") | MaxMessageTermination(10),
)
result = await team.run(task="Write a blog post about Python.")
print(result.stop_reason)

# SelectorGroupChat: LLM selects next speaker
team = SelectorGroupChat(
    participants=[planner, coder, tester],
    model_client=model_client,
    termination_condition=MaxMessageTermination(20),
)

# Swarm: explicit handoffs between agents
from autogen_agentchat.agents import AssistantAgent

triage = AssistantAgent(
    "triage",
    model_client=model_client,
    handoffs=["billing_agent", "support_agent"],
    system_message="Classify customer requests and hand off.",
)
billing = AssistantAgent("billing_agent", model_client=model_client)
support = AssistantAgent("support_agent", model_client=model_client)

swarm = Swarm(participants=[triage, billing, support])

# Stream results
async for msg in team.run_stream(task="Help me with my bill"):
    print(msg)
```

### Termination Conditions

```python
from autogen_agentchat.conditions import (
    MaxMessageTermination,         # stop after N messages
    TextMentionTermination,        # stop when text appears
    StopMessageTermination,        # stop on StopMessage type
    ExternalTermination,           # stop via external .set()
)
from autogen_agentchat.base import CancellationToken

# External control
ext = ExternalTermination()
# In another thread/task: ext.set()

# Cancel mid-run
cancel = CancellationToken()
# cancel.cancel() to abort
result = await team.run(task="...", cancellation_token=cancel)
```

---

## Haystack

### RAG Pipeline

```python
from haystack import Pipeline, Document
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.components.retrievers.in_memory import (
    InMemoryEmbeddingRetriever,
    InMemoryBM25Retriever,
)
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.components.builders import ChatPromptBuilder
from haystack.components.embedders import (
    OpenAITextEmbedder,
    OpenAIDocumentEmbedder,
)
from haystack.dataclasses import ChatMessage

# 1 — Indexing pipeline
doc_store = InMemoryDocumentStore(embedding_similarity_function="cosine")

indexing = Pipeline()
indexing.add_component("embedder", OpenAIDocumentEmbedder(model="text-embedding-3-small"))
indexing.add_component("writer", DocumentWriter(document_store=doc_store))
indexing.connect("embedder.documents", "writer.documents")
indexing.run({"embedder": {"documents": [Document(content="..."), ...]}})

# 2 — RAG query pipeline
template = [ChatMessage.from_user("""
Answer using only the following context:
{% for doc in documents %}{{ doc.content }}{% endfor %}
Question: {{question}}
""")]

rag = Pipeline()
rag.add_component("embedder", OpenAITextEmbedder(model="text-embedding-3-small"))
rag.add_component("retriever", InMemoryEmbeddingRetriever(document_store=doc_store, top_k=5))
rag.add_component("prompt", ChatPromptBuilder(template=template))
rag.add_component("llm", OpenAIChatGenerator(model="gpt-4o-mini"))

rag.connect("embedder.embedding", "retriever.query_embedding")
rag.connect("retriever.documents", "prompt.documents")
rag.connect("prompt.prompt", "llm.messages")

result = rag.run({
    "embedder": {"text": "What is RAG?"},
    "prompt": {"question": "What is RAG?"},
})
print(result["llm"]["replies"][0].text)
```

### Custom Component

```python
from haystack import component
from haystack.dataclasses import Document
from typing import List

@component
class KeywordFilter:
    @component.output_types(documents=List[Document])
    def run(self, documents: List[Document], keyword: str) -> dict:
        filtered = [d for d in documents if keyword.lower() in d.content.lower()]
        return {"documents": filtered}
```

### External Document Stores

```python
# Chroma
from haystack_integrations.document_stores.chroma import ChromaDocumentStore
doc_store = ChromaDocumentStore(collection_name="docs", persist_path="./chroma")

# Qdrant
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
doc_store = QdrantDocumentStore(url=os.environ["QDRANT_URL"], collection_name="docs", embedding_dim=1536)

# Elasticsearch
from haystack_integrations.document_stores.elasticsearch import ElasticsearchDocumentStore
doc_store = ElasticsearchDocumentStore(hosts="http://localhost:9200", index="docs")
```

---

## DSPy

### Core Concepts

```python
import dspy

# 1 — Configure LLM
lm = dspy.LM("openai/gpt-4o-mini", api_key=os.environ["OPENAI_API_KEY"])
dspy.configure(lm=lm)

# Optional retriever
colbertv2 = dspy.ColBERTv2(url="http://20.102.90.50:2017/wiki17_abstracts")
dspy.configure(rm=colbertv2)
```

### Signatures

```python
# Inline signature (string shorthand)
classify = dspy.Predict("sentence -> sentiment: Literal['positive','negative','neutral']")

# Class-based signature (richer)
class ExtractEvent(dspy.Signature):
    """Extract structured event details from an email."""
    email: str = dspy.InputField(desc="The email text")
    event_name: str = dspy.OutputField()
    date: str = dspy.OutputField(desc="ISO 8601 date")
    location: str = dspy.OutputField()

extractor = dspy.Predict(ExtractEvent)
result = extractor(email="Join us for the AI Summit on 2025-03-15 in San Francisco!")
print(result.event_name, result.date)
```

### Modules

```python
# ChainOfThought — adds step-by-step reasoning
cot = dspy.ChainOfThought("question -> answer")
result = cot(question="What is 2^10?")
print(result.reasoning, result.answer)

# ReAct — tool-augmented reasoning
def search(query: str) -> str:
    """Search Wikipedia for factual information."""
    return colbertv2(query, k=3)[0].long_text

react_agent = dspy.ReAct("question -> answer", tools=[search], max_iters=5)
result = react_agent(question="Who invented the telephone?")

# Custom Module
class RAGPipeline(dspy.Module):
    def __init__(self, num_passages=3):
        self.retrieve = dspy.Retrieve(k=num_passages)
        self.generate = dspy.ChainOfThought("context, question -> answer")

    def forward(self, question):
        context = self.retrieve(question).passages
        return self.generate(context=context, question=question)

rag = RAGPipeline()
result = rag(question="What year was Python created?")
```

### Optimizers (Auto-Prompt Tuning)

```python
from dspy.teleprompt import BootstrapFewShot, MIPROv2

# Training data
trainset = [
    dspy.Example(question="...", answer="...").with_inputs("question")
    for ... in data
]

# Metric function
def validate_answer(example, pred, trace=None):
    return example.answer.lower() in pred.answer.lower()

# BootstrapFewShot — fast, few-shot examples
optimizer = BootstrapFewShot(metric=validate_answer, max_bootstrapped_demos=4)
optimized_rag = optimizer.compile(RAGPipeline(), trainset=trainset)

# MIPROv2 — optimizes instructions + demonstrations
optimizer = MIPROv2(metric=validate_answer, auto="medium")
optimized_rag = optimizer.compile(
    RAGPipeline(),
    trainset=trainset,
    num_trials=20,
)

# Evaluate
from dspy.evaluate import Evaluate
evaluator = Evaluate(devset=devset, metric=validate_answer, num_threads=4)
score = evaluator(optimized_rag)

# Save / load
optimized_rag.save("rag_optimized.json")
loaded = RAGPipeline()
loaded.load("rag_optimized.json")
```

---

## Pydantic AI

### Agent Setup

```python
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel
from dataclasses import dataclass

# Simple agent
agent = Agent(
    "openai:gpt-4o-mini",
    system_prompt="You are a helpful assistant.",
)

result = agent.run_sync("What is the capital of France?")
print(result.output)  # "Paris"
```

### Typed Output + Dependency Injection

```python
@dataclass
class Deps:
    user_id: int
    db: "DatabaseConn"

class InvoiceResult(BaseModel):
    invoice_id: str
    total: float
    currency: str

agent = Agent(
    "openai:gpt-4o",
    deps_type=Deps,
    output_type=InvoiceResult,
    system_prompt="Extract invoice information.",
)

@agent.system_prompt
def add_user_context(ctx: RunContext[Deps]) -> str:
    return f"Processing request for user {ctx.deps.user_id}."

@agent.tool
async def lookup_invoice(ctx: RunContext[Deps], invoice_number: str) -> str:
    """Look up invoice by number in the database."""
    row = await ctx.deps.db.fetch_invoice(invoice_number)
    if row is None:
        from pydantic_ai import ModelRetry
        raise ModelRetry(f"Invoice {invoice_number!r} not found, try another.")
    return str(row)

async def process_invoice(user_id: int):
    deps = Deps(user_id=user_id, db=get_db())
    result = await agent.run("Get invoice INV-2024-001", deps=deps)
    invoice: InvoiceResult = result.output  # type-safe
    return invoice
```

### Run Methods

```python
# Async (preferred)
result = await agent.run("prompt", deps=deps)

# Sync (convenience)
result = agent.run_sync("prompt", deps=deps)

# Streaming
async with agent.run_stream("prompt") as response:
    async for chunk in response.stream_text():
        print(chunk, end="", flush=True)

# Stream all events (tool calls + text)
async with agent.run_stream_events("prompt") as events:
    async for event in events:
        print(type(event).__name__, event)
```

### Usage Limits

```python
from pydantic_ai import UsageLimits, UsageLimitExceeded

try:
    result = agent.run_sync(
        "Analyze this document",
        usage_limits=UsageLimits(
            request_limit=5,
            output_tokens_limit=2000,
            tool_calls_limit=10,
        ),
    )
except UsageLimitExceeded as e:
    print(f"Limit exceeded: {e}")
```

### Model Settings & Multi-Turn Conversations

```python
from pydantic_ai import ModelSettings

result1 = agent.run_sync("Who was Einstein?", model_settings=ModelSettings(temperature=0.0))
result2 = agent.run_sync(
    "What was his famous equation?",
    message_history=result1.new_messages(),  # continue conversation
)
```

---

## smolagents (HuggingFace)

### CodeAgent vs ToolCallingAgent

| | CodeAgent | ToolCallingAgent |
|---|---|---|
| Tool calls | Writes Python code snippets | Structured JSON |
| Expressivity | High (loops, transforms, logic) | Low (atomic actions only) |
| Safety | Requires secure sandbox | Safer by default |
| Best for | Complex reasoning, multi-step | Simple dispatching |

### Creating an Agent

```python
from smolagents import CodeAgent, ToolCallingAgent, LiteLLMModel, InferenceClientModel

# Via LiteLLM (100+ providers)
model = LiteLLMModel(
    model_id="anthropic/claude-3-5-sonnet-latest",
    api_key=os.environ["ANTHROPIC_API_KEY"],
)

# Via HuggingFace Inference
model = InferenceClientModel(
    model_id="Qwen/Qwen2.5-Coder-32B-Instruct",
    token=os.environ["HF_TOKEN"],
)

agent = CodeAgent(
    tools=[],
    model=model,
    add_base_tools=True,          # adds DuckDuckGo search + Python interpreter
    additional_authorized_imports=["pandas", "numpy"],
)
result = agent.run("What is the 100th Fibonacci number?")
```

### Custom Tools

```python
from smolagents import tool, Tool

# Decorator pattern (simple)
@tool
def get_stock_price(ticker: str) -> str:
    """
    Get the current stock price for a given ticker symbol.

    Args:
        ticker: Stock ticker symbol (e.g., AAPL, MSFT).
    """
    return f"${ticker}: $150.00"  # replace with real API call

# Class pattern (complex initialization)
class DatabaseTool(Tool):
    name = "database_search"
    description = "Search the internal product database."
    inputs = {
        "query": {"type": "string", "description": "Search query"},
        "limit": {"type": "integer", "description": "Max results"},
    }
    output_type = "string"

    def __init__(self, connection_string: str):
        super().__init__()
        self.db = connect(connection_string)

    def forward(self, query: str, limit: int = 10) -> str:
        results = self.db.search(query, limit=limit)
        return str(results)

agent = CodeAgent(
    tools=[get_stock_price, DatabaseTool("postgresql://...")],
    model=model,
)
```

### Multi-Agent Architecture

```python
from smolagents import CodeAgent, InferenceClientModel, WebSearchTool

model = InferenceClientModel()

# Sub-agent specialized in web search
web_agent = CodeAgent(
    tools=[WebSearchTool()],
    model=model,
    name="web_search_agent",
    description="Runs web searches. Pass your query as the task.",
)

# Manager orchestrates sub-agents as tools
manager = CodeAgent(
    tools=[],
    model=model,
    managed_agents=[web_agent],
)

manager.run("What are the latest AI breakthroughs this week?")
```

### Secure Code Execution

```python
# E2B sandbox (cloud)
agent = CodeAgent(tools=[], model=model, executor_type="e2b")
# Requires E2B_API_KEY env var

# Docker sandbox
agent = CodeAgent(tools=[], model=model, executor_type="docker")
```

---

## OpenAI Agents SDK

### Basic Agent

```python
from agents import Agent, Runner, function_tool
import os

@function_tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"Weather in {city}: 22°C, partly cloudy"

agent = Agent(
    name="weather_assistant",
    instructions="You are a helpful weather assistant. Use the get_weather tool.",
    model="gpt-4o-mini",
    tools=[get_weather],
)

# Sync run
result = Runner.run_sync(agent, "What's the weather in Tokyo?")
print(result.final_output)

# Async run
import asyncio
result = asyncio.run(Runner.run(agent, "What's the weather in London?"))
```

### Structured Output

```python
from pydantic import BaseModel

class WeatherReport(BaseModel):
    city: str
    temperature: float
    condition: str
    recommendation: str

agent = Agent(
    name="structured_weather",
    instructions="Extract weather information and provide a recommendation.",
    model="gpt-4o",
    output_type=WeatherReport,
)

result = Runner.run_sync(agent, "What's the weather in Paris?")
report: WeatherReport = result.final_output
print(report.city, report.temperature)
```

### Handoffs Between Agents

```python
from agents import Agent, Runner, handoff

triage_agent = Agent(
    name="triage",
    instructions="Route customer requests to the appropriate specialist.",
    model="gpt-4o-mini",
)

billing_agent = Agent(
    name="billing_specialist",
    instructions="Handle billing questions and refund requests.",
    model="gpt-4o",
)

support_agent = Agent(
    name="technical_support",
    instructions="Resolve technical issues.",
    model="gpt-4o",
)

# Register handoffs
triage_agent = triage_agent.clone(
    handoffs=[billing_agent, support_agent]
)

result = Runner.run_sync(triage_agent, "I was charged twice for my subscription.")
print(result.final_output)
```

### Guardrails

```python
from agents import (
    Agent, Runner,
    InputGuardrail, OutputGuardrail,
    GuardrailFunctionOutput,
    RunContextWrapper,
)
from pydantic import BaseModel

class SafetyCheck(BaseModel):
    is_safe: bool
    reason: str

async def input_safety_check(
    ctx: RunContextWrapper,
    agent: Agent,
    input_text: str,
) -> GuardrailFunctionOutput:
    """Reject requests that violate content policy."""
    dangerous_keywords = ["hack", "exploit", "malware"]
    is_safe = not any(kw in input_text.lower() for kw in dangerous_keywords)
    return GuardrailFunctionOutput(
        output_info=SafetyCheck(is_safe=is_safe, reason="content policy check"),
        tripwire_triggered=not is_safe,
    )

agent = Agent(
    name="safe_assistant",
    instructions="Be helpful and safe.",
    model="gpt-4o-mini",
    input_guardrails=[InputGuardrail(guardrail_function=input_safety_check)],
)
```

### Streaming

```python
import asyncio

async def stream_response():
    async with Runner.run_streamed(agent, "Explain quantum computing.") as stream:
        async for event in stream.stream_events():
            if hasattr(event, "delta"):
                print(event.delta, end="", flush=True)

asyncio.run(stream_response())
```

---

## Semantic Kernel (Python)

### Kernel Setup + Plugin

```python
import asyncio
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion, AzureChatCompletion
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.functions import kernel_function
from semantic_kernel.functions.kernel_arguments import KernelArguments

kernel = Kernel()

# Add OpenAI service
kernel.add_service(
    OpenAIChatCompletion(
        ai_model_id="gpt-4o",
        api_key=os.environ["OPENAI_API_KEY"],
    )
)

# Define plugin
class WeatherPlugin:
    @kernel_function(name="get_weather", description="Get weather for a city")
    def get_weather(self, city: str) -> str:
        return f"Weather in {city}: 22°C, sunny"

    @kernel_function(name="get_forecast", description="Get 5-day forecast")
    def get_forecast(self, city: str, days: int = 5) -> str:
        return f"{days}-day forecast for {city}: mixed conditions"

kernel.add_plugin(WeatherPlugin(), plugin_name="Weather")
```

### Auto Function Calling (Planning)

```python
from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings

execution_settings = OpenAIChatPromptExecutionSettings()
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

history = ChatHistory()

async def chat(user_message: str):
    history.add_user_message(user_message)

    chat_service = kernel.get_service(type=OpenAIChatCompletion)
    result = await chat_service.get_chat_message_contents(
        chat_history=history,
        settings=execution_settings,
        kernel=kernel,
        arguments=KernelArguments(),
    )
    reply = result[0]
    history.add_message(reply)
    return str(reply)

asyncio.run(chat("What's the weather in Madrid?"))
```

### Kernel Function Invocation

```python
# Invoke a specific plugin function directly
result = await kernel.invoke(
    plugin_name="Weather",
    function_name="get_weather",
    arguments=KernelArguments(city="Tokyo"),
)
print(str(result))

# Invoke via prompt template
from semantic_kernel.prompt_template import PromptTemplateConfig

prompt = "Summarize the following: {{$input}}"
summarize = kernel.add_function(
    prompt=prompt,
    function_name="summarize",
    plugin_name="TextUtils",
    prompt_template_config=PromptTemplateConfig(template=prompt),
)
result = await kernel.invoke(summarize, arguments=KernelArguments(input="Long text..."))
```

### Memory & Vector Stores (Semantic Kernel)

```python
from semantic_kernel.memory import SemanticTextMemory
from semantic_kernel.connectors.memory.chroma import ChromaMemoryStore

memory_store = ChromaMemoryStore(persist_directory="./sk_memory")
memory = SemanticTextMemory(
    storage=memory_store,
    embeddings_generator=kernel.get_service(type=OpenAIChatCompletion),
)

# Save
await memory.save_information(collection="facts", id="1", text="Python was created in 1991.")

# Search
results = await memory.search(collection="facts", query="When was Python created?", limit=3)
for r in results:
    print(r.text, r.relevance)
```

---

## Framework Comparison

| Feature | LlamaIndex | CrewAI | AutoGen | Haystack | DSPy | Pydantic AI | smolagents | OAI SDK | Semantic Kernel |
|---------|-----------|--------|---------|---------|------|-------------|-----------|---------|----------------|
| **RAG** | ★★★ | ★★ | ★★ | ★★★ | ★★ | ★★ | ★★ | ★★ | ★★ |
| **Multi-agent** | ★★ | ★★★ | ★★★ | ★ | ★ | ★★ | ★★★ | ★★★ | ★★ |
| **Type safety** | ★★ | ★★ | ★★ | ★★ | ★★ | ★★★ | ★★ | ★★★ | ★★ |
| **Prompt opt.** | ★ | ★ | ★ | ★ | ★★★ | ★ | ★ | ★ | ★ |
| **Code agents** | ★★ | ★ | ★★ | ★ | ★★ | ★★ | ★★★ | ★★ | ★ |
| **Enterprise** | ★★ | ★★ | ★★ | ★★★ | ★★ | ★★★ | ★★ | ★★★ | ★★★ |
| **Learning curve** | Medium | Low | Medium | Medium | High | Low | Low | Low | Medium |

## Related Skills
- [[pgvector-rag-patterns]] — Vector store integration for RAG pipelines
- [[vector-stores-cloud]] — Cloud vector store patterns (Pinecone, Weaviate, Qdrant, etc.)
- [[vector-stores-self-hosted]] — Self-hosted vector stores (Chroma, FAISS, LanceDB)
- [[llm-observability]] — Ragas, LangSmith, Langfuse for evaluation and tracing
- [[ai-visual-tools]] — Flowise and Langflow for visual prototyping
