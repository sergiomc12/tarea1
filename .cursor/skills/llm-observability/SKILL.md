---
name: llm-observability
description: LLM observability, evaluation, and tracing — Ragas (RAG evaluation metrics: Faithfulness, ContextPrecision, ResponseRelevancy, FactualCorrectness, etc.), LangSmith (tracing with @traceable, datasets, LLM-as-judge evaluation), and Langfuse (traces/spans/generations, @observe decorator, OpenAI/LangChain integrations, user feedback, prompt management). Use when evaluating RAG pipelines, debugging LLM chains, or setting up production observability.
metadata:
  origin: sergiomc12-fork
---

# LLM Observability: Ragas · LangSmith · Langfuse

## When to Use Which Tool

| Tool | Primary Use | Key Strength |
|------|-------------|-------------|
| **Ragas** | Automated RAG quality scoring | Metric-driven evaluation without golden labels |
| **LangSmith** | Trace + evaluate LangChain apps | Native LangChain integration, hub-hosted prompts |
| **Langfuse** | Full-stack LLM observability | Framework-agnostic, self-hostable, cost tracking |

---

## Ragas

### What It Measures

Ragas provides metrics that evaluate different failure modes in RAG systems:

| Metric | Measures | Requires |
|--------|----------|----------|
| `Faithfulness` | Answer is grounded in retrieved context (no hallucination) | `response`, `retrieved_contexts` |
| `ResponseRelevancy` | Answer actually addresses the question | `user_input`, `response` |
| `ContextPrecision` | Retrieved context contains relevant information | `user_input`, `retrieved_contexts`, `reference` |
| `ContextRecall` | All required information was retrieved | `retrieved_contexts`, `reference` |
| `FactualCorrectness` | Factual overlap between answer and ground truth | `response`, `reference` |
| `ContextEntityRecall` | Entities from ground truth are in context | `retrieved_contexts`, `reference` |
| `NoiseSensitivity` | Model correctly ignores irrelevant context | `user_input`, `response`, `retrieved_contexts`, `reference` |
| `SemanticSimilarity` | Embedding similarity between response and reference | `response`, `reference` |
| `LLMContextRecall` | LLM-judged recall of required info in context | `user_input`, `retrieved_contexts`, `reference` |

**Agent/Tool metrics:** `ToolCallAccuracy`, `ToolCallF1`, `AgentGoalAccuracy`, `TopicAdherence`

**NLG metrics (no LLM needed):** `BleuScore`, `RougeScore`, `ExactMatch`, `StringPresence`, `NonLLMStringSimilarity`

### Install

```
pip install ragas langchain-openai
```

### Basic Evaluation

```python
import os
os.environ["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]

from ragas import evaluate, EvaluationDataset
from ragas.metrics import (
    Faithfulness,
    ResponseRelevancy,
    ContextPrecision,
    ContextRecall,
    FactualCorrectness,
)

# Build dataset
samples = [
    {
        "user_input": "What is the capital of France?",
        "retrieved_contexts": ["France is a country in Western Europe. Its capital is Paris."],
        "response": "The capital of France is Paris.",
        "reference": "Paris is the capital of France.",
    },
    {
        "user_input": "When was Python created?",
        "retrieved_contexts": ["Python was created by Guido van Rossum and released in 1991."],
        "response": "Python was created in 1992.",   # wrong — will catch with FactualCorrectness
        "reference": "Python was first released in 1991.",
    },
]

dataset = EvaluationDataset.from_list(samples)

result = evaluate(
    dataset=dataset,
    metrics=[
        Faithfulness(),
        ResponseRelevancy(),
        ContextPrecision(),
        ContextRecall(),
        FactualCorrectness(),
    ],
)

print(result)
# Returns scores per metric and per sample
df = result.to_pandas()
print(df[["user_input", "faithfulness", "response_relevancy", "factual_correctness"]])
```

### Custom LLM Configuration

```python
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_openai import OpenAIEmbeddings
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

# Use GPT-4o as the evaluator
evaluator_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o"))
evaluator_embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings())

result = evaluate(
    dataset=dataset,
    metrics=[Faithfulness(), ResponseRelevancy()],
    llm=evaluator_llm,
    embeddings=evaluator_embeddings,
)

# Azure OpenAI
azure_llm = LangchainLLMWrapper(
    AzureChatOpenAI(
        azure_deployment=os.environ["AZURE_DEPLOYMENT"],
        azure_endpoint=os.environ["AZURE_ENDPOINT"],
        api_version="2024-02-15-preview",
    )
)
```

### Async Evaluation

```python
import asyncio
from ragas import evaluate

async def run_evaluation():
    result = await evaluate(
        dataset=dataset,
        metrics=[Faithfulness(), ContextPrecision()],
        is_async=True,
        run_config=RunConfig(max_workers=4, timeout=60),
    )
    return result

result = asyncio.run(run_evaluation())
```

### End-to-End RAG Evaluation

```python
from ragas.testset import TestsetGenerator
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import DirectoryLoader

# Auto-generate test set from documents
loader = DirectoryLoader("./docs/")
docs = loader.load()

generator = TestsetGenerator.from_langchain(
    generator_llm=ChatOpenAI(model="gpt-4o"),
    critic_llm=ChatOpenAI(model="gpt-4o"),
    embeddings=OpenAIEmbeddings(),
)
testset = generator.generate_with_langchain_docs(docs, test_size=20)
test_df = testset.to_pandas()

# Evaluate your RAG pipeline against generated questions
evaluation_samples = []
for _, row in test_df.iterrows():
    question = row["question"]
    contexts, answer = your_rag_pipeline(question)
    evaluation_samples.append({
        "user_input": question,
        "retrieved_contexts": contexts,
        "response": answer,
        "reference": row["ground_truth"],
    })

result = evaluate(
    dataset=EvaluationDataset.from_list(evaluation_samples),
    metrics=[Faithfulness(), ResponseRelevancy(), ContextPrecision(), ContextRecall()],
)
```

### Metric Interpretation

| Score | Meaning |
|-------|---------|
| Faithfulness ≥ 0.9 | Answer well-grounded, low hallucination risk |
| ResponseRelevancy ≥ 0.8 | Answer addresses the question |
| ContextPrecision ≥ 0.7 | Good signal-to-noise in retrieved docs |
| ContextRecall ≥ 0.8 | Retriever finds the needed information |
| FactualCorrectness ≥ 0.8 | Answers match ground truth facts |

---

## LangSmith

### Setup

```python
import os

# Set environment variables before any LangChain/LLM imports
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = os.environ["LANGSMITH_API_KEY"]
os.environ["LANGCHAIN_PROJECT"] = "my-rag-app"   # optional, defaults to "default"
# os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"  # EU: https://eu.api.smith.langchain.com
```

### Auto-Tracing (LangChain)

Any LangChain chain, agent, or LLM automatically traces when the env vars above are set:

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(model="gpt-4o-mini")
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("human", "{question}"),
])
chain = prompt | llm

# This automatically creates a trace in LangSmith
result = chain.invoke({"question": "What is RAG?"})
```

### @traceable Decorator

```python
from langsmith import traceable

@traceable(name="my_retriever", run_type="retriever")
def retrieve_documents(query: str) -> list[str]:
    """Retrieve relevant documents for a query."""
    # Your retrieval logic here
    return ["doc1 content", "doc2 content"]

@traceable(name="my_rag_pipeline", run_type="chain", tags=["production"])
def rag_pipeline(question: str) -> str:
    docs = retrieve_documents(question)  # automatically nested trace
    context = "\n".join(docs)
    response = llm.invoke(f"Context: {context}\n\nQuestion: {question}")
    return response.content

# Metadata attached to all traces
result = rag_pipeline(
    "What is quantum computing?",
    langsmith_extra={
        "metadata": {"user_id": "user-123", "session_id": "sess-456"},
    },
)
```

### Client API

```python
from langsmith import Client

client = Client(api_key=os.environ["LANGSMITH_API_KEY"])

# List recent runs in a project
runs = client.list_runs(
    project_name="my-rag-app",
    filter='eq(status, "success")',
    limit=50,
)

# Add feedback to a run
client.create_feedback(
    run_id=run.id,
    key="quality",
    score=0.95,
    comment="Good answer, sources cited correctly",
)

# Retrieve a specific run
run = client.read_run(run_id="<uuid>")
print(run.inputs, run.outputs, run.error)
```

### Datasets & Evaluation

```python
from langsmith import Client
from langsmith.evaluation import evaluate as ls_evaluate

client = Client()

# Create a dataset
dataset = client.create_dataset(
    dataset_name="RAG QA Benchmark",
    description="Q&A pairs for evaluating RAG pipeline",
)

# Add examples
examples = [
    {"inputs": {"question": "What is LangChain?"}, "outputs": {"answer": "A framework for building LLM apps."}},
    {"inputs": {"question": "What is RAG?"}, "outputs": {"answer": "Retrieval-Augmented Generation."}},
]
client.create_examples(
    inputs=[e["inputs"] for e in examples],
    outputs=[e["outputs"] for e in examples],
    dataset_id=dataset.id,
)

# Define evaluator
def correctness_evaluator(run, example) -> dict:
    """LLM-as-judge: score answer correctness."""
    predicted = run.outputs.get("answer", "")
    expected = example.outputs.get("answer", "")

    judge_prompt = f"Score 0-1 if '{predicted}' correctly answers the same as '{expected}'. Return only the float."
    score = float(llm.invoke(judge_prompt).content.strip())
    return {"key": "correctness", "score": score}

# Run evaluation
results = ls_evaluate(
    lambda inputs: {"answer": rag_pipeline(inputs["question"])},
    data=dataset.name,
    evaluators=[correctness_evaluator],
    experiment_prefix="gpt4o-mini-rag",
    metadata={"model": "gpt-4o-mini", "chunk_size": 512},
)
print(results.to_pandas()[["correctness"]].mean())
```

### Hub Integration (Prompt Management)

```python
from langchain import hub

# Pull a versioned prompt from LangSmith Hub
prompt = hub.pull("rlm/rag-prompt")            # community prompt
my_prompt = hub.pull("my-org/custom-rag:abc123")  # pinned version

# Push your prompt to Hub
from langchain_core.prompts import ChatPromptTemplate

my_prompt = ChatPromptTemplate.from_messages([...])
hub.push("my-org/rag-v2", my_prompt, new_repo_is_public=False)
```

---

## Langfuse

### Setup

```python
import os

os.environ["LANGFUSE_PUBLIC_KEY"] = os.environ["LANGFUSE_PUBLIC_KEY"]
os.environ["LANGFUSE_SECRET_KEY"] = os.environ["LANGFUSE_SECRET_KEY"]
os.environ["LANGFUSE_HOST"] = "https://cloud.langfuse.com"  # EU: https://eu.cloud.langfuse.com
# Self-hosted: "http://localhost:3000"
```

### @observe Decorator (Recommended)

```python
from langfuse.decorators import observe, langfuse_context

@observe()
def retrieve_docs(query: str) -> list[str]:
    # automatically tracked as a "span"
    return search_vector_db(query)

@observe()
def generate_answer(question: str, context: str) -> str:
    # automatically tracked as a "span" containing an LLM generation
    langfuse_context.update_current_observation(
        metadata={"model": "gpt-4o-mini"},
        tags=["production"],
    )
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Answer based on the context."},
            {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"},
        ],
    )
    return response.choices[0].message.content

@observe(name="rag_pipeline")
def rag_pipeline(question: str) -> str:
    langfuse_context.update_current_trace(
        user_id="user-123",
        session_id="session-456",
        tags=["rag", "production"],
        metadata={"env": "prod"},
    )
    docs = retrieve_docs(question)          # nested span
    context = "\n".join(docs)
    answer = generate_answer(question, context)  # nested span
    langfuse_context.score_current_trace(
        name="user_satisfaction",
        value=1.0,
        comment="auto-scored",
    )
    return answer

result = rag_pipeline("What is quantum computing?")
```

### OpenAI Drop-In Replacement

```python
from langfuse.openai import OpenAI  # drop-in replacement

client = OpenAI()  # reads LANGFUSE_* env vars automatically

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "What is RAG?"}],
    metadata={"user_id": "user-123"},     # Langfuse metadata
    tags=["production"],                   # Langfuse tags
)
print(response.choices[0].message.content)
# This call is automatically traced with token usage, cost, latency
```

### LangChain Callback Handler

```python
from langfuse.callback import CallbackHandler

handler = CallbackHandler(
    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    host=os.environ["LANGFUSE_HOST"],
    user_id="user-123",
    session_id="session-456",
    trace_name="my-rag-chain",
)

# Pass handler to any LangChain invocation
result = chain.invoke(
    {"question": "What is LangChain?"},
    config={"callbacks": [handler]},
)
```

### Manual SDK (Fine-Grained Control)

```python
from langfuse import get_client

langfuse = get_client()

with langfuse.start_as_current_observation(
    as_type="span",
    name="document-retrieval",
    input={"query": "quantum computing"},
) as span:
    docs = retrieve_from_db("quantum computing")
    span.update(output={"num_docs": len(docs)})

with langfuse.start_as_current_observation(
    as_type="generation",
    name="answer-generation",
    model="gpt-4o-mini",
    input=[{"role": "user", "content": "What is quantum computing?"}],
) as gen:
    response = call_llm(...)
    gen.update(
        output=response,
        usage={"input_tokens": 150, "output_tokens": 200},
        metadata={"finish_reason": "stop"},
    )

# Always flush in short-lived scripts
langfuse.flush()
```

### Scores and Feedback

```python
from langfuse import get_client

langfuse = get_client()

# Add score to a trace
langfuse.score(
    trace_id="<trace-uuid>",
    name="faithfulness",
    value=0.95,
    comment="Answer well grounded in retrieved docs",
    data_type="NUMERIC",   # or "BOOLEAN" / "CATEGORICAL"
)

# Collect user feedback (1-click thumbs up/down)
langfuse.score(
    trace_id="<trace-uuid>",
    name="user_feedback",
    value=1,               # 1=positive, 0=negative
    data_type="BOOLEAN",
)
```

### Prompt Management

```python
from langfuse import get_client

langfuse = get_client()

# Fetch prompt from Langfuse (supports versioning)
prompt = langfuse.get_prompt("rag-system-prompt", version=3)
compiled = prompt.compile(context="...", question="...")

# Use in LangChain
from langfuse.langchain import LangfusePrompt
lc_prompt = LangfusePrompt(prompt=prompt)
```

### Ragas + Langfuse Integration

```python
from ragas import evaluate, EvaluationDataset
from ragas.metrics import Faithfulness, ResponseRelevancy
from langfuse import get_client

langfuse = get_client()

# Run Ragas evaluation
result = evaluate(dataset=dataset, metrics=[Faithfulness(), ResponseRelevancy()])
df = result.to_pandas()

# Push scores back to Langfuse traces
for _, row in df.iterrows():
    langfuse.score(
        trace_id=row["trace_id"],
        name="ragas_faithfulness",
        value=row["faithfulness"],
    )
    langfuse.score(
        trace_id=row["trace_id"],
        name="ragas_relevancy",
        value=row["response_relevancy"],
    )
```

---

## Observability Decision Guide

```
Need to evaluate RAG quality?
    → Ragas (Faithfulness + ContextPrecision + ResponseRelevancy)

Need to trace LangChain apps?
    → LangSmith (@traceable + LANGCHAIN_TRACING_V2=true)

Need framework-agnostic tracing?
    → Langfuse (@observe decorator or OpenAI drop-in)

Need self-hostable solution?
    → Langfuse (Docker Compose, self-managed)

Need prompt version management?
    → Langfuse (Prompt Management) or LangSmith Hub

Need dataset + LLM-as-judge evaluation?
    → LangSmith (evaluate()) or Ragas (TestsetGenerator + evaluate())

Need cost tracking?
    → Langfuse (automatic with OpenAI drop-in)
```

## Related Skills
- [[python-ai-agents]] — Agent frameworks to instrument with these tools
- [[pgvector-rag-patterns]] — RAG pipelines to evaluate with Ragas
