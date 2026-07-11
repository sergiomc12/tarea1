---
name: pgvector-rag-patterns
description: Selection matrix for all 14 major vector stores (pgvector, Pinecone, Weaviate, Milvus/Zilliz, Qdrant, Chroma, FAISS, LanceDB, Elasticsearch, OpenSearch, MongoDB Atlas, Redis/RediSearch, Azure AI Search, Google Vertex AI), deep-dive on pgvector, and universal RAG pipeline patterns. Use when choosing a vector store, designing a RAG architecture, or implementing pgvector with Spring Boot / LangChain4j / Spring AI.
metadata:
  origin: sergiomc12-fork
---

# Vector Store Selection + pgvector RAG Patterns

Complete guide for choosing a vector store and building RAG pipelines.  
Deep dive on **pgvector** (the default for Spring Boot + PostgreSQL stacks).  
See [[vector-stores-cloud]] for Pinecone / Weaviate / Qdrant / MongoDB Atlas / Azure AI Search / Google Vertex AI patterns.  
See [[vector-stores-self-hosted]] for Chroma / LanceDB / FAISS / Elasticsearch / OpenSearch / Redis patterns.  
See [[spring-ai-patterns]] and [[langchain4j-rag]] for framework-specific RAG wiring.

## When to Activate

- Choosing or migrating between vector stores
- Designing a new RAG pipeline from scratch
- Using pgvector with Spring Boot / LangChain4j / Spring AI
- Needing a comparison of filtering syntax, index types, or hybrid search across stores
- Tuning recall/precision trade-offs (HNSW params, IVF lists, similarity thresholds)

---

## Vector Store Selection Matrix

| Store | Deployment | Best For | Weakness | Max Dims | Index Types |
|-------|-----------|---------|---------|---------|-------------|
| **pgvector** | Self-hosted / RDS / Neon | Already on Postgres; ACID; SQL filters | Single-node throughput ceiling | 16,000 | HNSW, IVFFlat |
| **Pinecone** | Fully managed SaaS | Zero-ops, serverless, hybrid sparse+dense | Vendor lock-in; cost at scale | N/A | Serverless (proprietary) |
| **Weaviate** | Cloud + self-hosted | Multi-modal, named vectors, BM25+vector | Schema migration complexity | N/A | HNSW, Flat |
| **Milvus / Zilliz** | Self-hosted + Zilliz Cloud | Billion-scale, multi-vector hybrid | Operational complexity | N/A | HNSW, IVF_FLAT, DISKANN, SCANN |
| **Qdrant** | Cloud + self-hosted | Rich payload filtering, named vectors | Younger ecosystem | N/A | HNSW |
| **Chroma** | Embedded + server | Dev/test, Python-native | Not production-scale | N/A | HNSW (via hnswlib) |
| **FAISS** | In-process library | Maximum throughput research / ML pipelines | No persistence, no filtering | N/A | 10+ index types |
| **LanceDB** | Embedded + managed | Columnar (Lance), multimodal, no server | Smaller community | N/A | IVF_PQ, HNSW |
| **Elasticsearch** | Self-hosted + Elastic Cloud | Hybrid text+vector, existing ES clusters | License, operational cost | 4,096 | HNSW, int8_hnsw, bbq_hnsw |
| **OpenSearch** | Self-hosted + AWS Service | AWS-native, open-source ES alternative | HNSW in-memory only | 10,000 | HNSW (faiss/nmslib/lucene) |
| **MongoDB Atlas** | Managed Atlas | Already on Mongo; JSON documents | Atlas-only (no self-host) | 8,192 | HNSW (ANN) / Exact (ENN) |
| **Redis / RediSearch** | Self-hosted + Redis Cloud | Sub-millisecond, cache+vector together | Memory-only, expensive at scale | N/A | FLAT (brute), HNSW |
| **Azure AI Search** | Managed Azure | Azure ecosystem, hybrid + semantic ranker | Azure-only, cost | 4,096 | HNSW, Exhaustive KNN |
| **Google Vertex AI** | Managed GCP | GCP ecosystem, ScaNN algorithm, autoscaling | GCP-only | N/A | ScaNN (tree-AH) |

### Decision Tree

```
┌─ Already on Postgres? ──→ pgvector
├─ Need zero-ops managed + best-in-class hybrid sparse+dense? ──→ Pinecone
├─ Need billion-scale + multi-vector + BM25? ──→ Milvus / Zilliz Cloud
├─ Need rich geo/datetime payload filters + open-source? ──→ Qdrant
├─ Need BM25 + vector + existing ES cluster? ──→ Elasticsearch / OpenSearch
├─ Already on AWS? ──→ AWS OpenSearch Service
├─ Already on Azure? ──→ Azure AI Search
├─ Already on GCP? ──→ Google Vertex AI Vector Search
├─ Already on MongoDB Atlas? ──→ Atlas Vector Search
├─ Need cache-speed + vector together? ──→ Redis / RediSearch
├─ Python dev/testing only? ──→ Chroma
├─ Columnar data / multimodal / embedded? ──→ LanceDB
└─ Maximum throughput research / no persistence needed? ──→ FAISS
```

---

## Distance Metrics — Cross-Store Reference

| Metric | pgvector | Pinecone | Weaviate | Milvus | Qdrant | Elasticsearch |
|--------|---------|---------|---------|-------|-------|--------------|
| Cosine similarity | `<=>` | cosine | cosine | COSINE | Cosine | cosine |
| L2 / Euclidean | `<->` | euclidean | l2-squared | L2 | Euclid | l2_norm |
| Inner product | `<#>` | dotproduct | dot | IP | Dot | dot_product |
| L1 / Manhattan | `<+>` | — | manhattan | — | — | — |
| Hamming (binary) | `<~>` | — | hamming | HAMMING | — | — |

**Rule of thumb:**
- Use **cosine** for text embeddings from OpenAI, Cohere, Voyage — vectors not guaranteed normalized
- Use **inner product** when vectors ARE normalized (faster, same result as cosine)
- Use **L2** for image embeddings and custom models
- Use **Hamming** only for binary vectors

---

## Embedding Model Selection

| Model | Dims | Context | Best For | Provider |
|-------|------|---------|---------|---------|
| `text-embedding-3-small` | 1536 | 8K tokens | English text, cost-effective | OpenAI |
| `text-embedding-3-large` | 3072 | 8K tokens | Higher accuracy, multilingual | OpenAI |
| `text-embedding-ada-002` | 1536 | 8K tokens | Legacy OpenAI | OpenAI |
| `embed-multilingual-v3.0` | 1024 | — | Multilingual RAG | Cohere |
| `voyage-large-2` | 1536 | 16K tokens | Long documents, high accuracy | Voyage AI |
| `bge-large-en-v1.5` | 1024 | 512 tokens | Open-source, self-hosted | BAAI |
| `paraphrase-albert-small-v2` | 768 | 512 tokens | Offline/embedded (Milvus default) | HuggingFace |

---

## Universal RAG Pipeline

```
Documents → Chunk → Embed → Store
                                ↓
User query → Embed → Search → Retrieve → [Rerank] → LLM augmented prompt → Response
```

### Chunking Strategy

| Content | Strategy | Chunk Size | Overlap |
|---------|---------|-----------|---------|
| General text | TokenTextSplitter | 800 tokens | 50–100 tokens |
| Legal / technical docs | Paragraph-based | 400–600 tokens | 80 tokens |
| Code | Function/class boundaries | — | — |
| Q&A pairs | Question as chunk + answer as metadata | — | — |

**Always** prepend document title or section header to each chunk — improves retrieval quality significantly.

### Query Transformation (before retrieval)

| Technique | When to use | Tool |
|-----------|------------|------|
| Standalone query compression | Chat mode with memory — follow-ups lose context | LangChain4j `CompressingQueryTransformer`, Spring AI `CompressionQueryTransformer` |
| Query rewriting | Short/ambiguous queries | `RewriteQueryTransformer` |
| Multi-query expansion | Broad topics needing coverage | `ExpandingQueryTransformer` / `MultiQueryExpander` |
| HyDE (hypothetical doc) | When user query is very different from document style | Generate synthetic answer, embed that |

### Retrieval Parameters

```
topK         = 5–10      Start here; tune based on context window and precision
minScore     = 0.70–0.80  Filter noise; too high misses valid content
chunkSize    = 800 tokens Reduce if LLM has small context
overlap      = 50 tokens  Minimum to preserve sentence context
```

---

## pgvector — Deep Dive

### Setup

```sql
-- Install extension (once per database)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS hstore;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Basic table
CREATE TABLE document_embeddings (
  id        UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  content   TEXT NOT NULL,
  metadata  JSONB,
  embedding vector(1536)
);
```

### All Vector Types

| Type | Dims | Storage/dim | Use |
|------|------|-------------|-----|
| `vector(n)` | ≤16,000 | 4 bytes | Default: float32 |
| `halfvec(n)` | ≤16,000 | 2 bytes | 50% storage saving |
| `bit(n)` | ≤64,000 | 1 bit | Binary vectors |
| `sparsevec(n)` | ≤16,000 | sparse | Sparse (BM25, SPLADE) |

### All Distance Operators

```sql
-- L2 (Euclidean) — default, general purpose
SELECT * FROM items ORDER BY embedding <-> '[1,2,3]' LIMIT 5;

-- Cosine similarity (1 - distance = similarity)
SELECT *, 1 - (embedding <=> '[1,2,3]') AS similarity FROM items
ORDER BY embedding <=> '[1,2,3]' LIMIT 5;

-- Inner product (for normalized vectors)
SELECT *, (embedding <#> '[1,2,3]') * -1 AS score FROM items
ORDER BY embedding <#> '[1,2,3]' LIMIT 5;

-- L1 Manhattan
SELECT * FROM items ORDER BY embedding <+> '[1,2,3]' LIMIT 5;

-- Hamming (bit type only)
SELECT * FROM bits ORDER BY embedding <~> '[0,1,0]'::bit(3) LIMIT 5;

-- Jaccard (bit type only)
SELECT * FROM bits ORDER BY embedding <%> '[0,1,0]'::bit(3) LIMIT 5;
```

### Index Types

#### HNSW (recommended for most cases)

```sql
-- Default parameters
CREATE INDEX ON document_embeddings USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Higher recall (production)
CREATE INDEX ON document_embeddings USING hnsw (embedding vector_cosine_ops)
  WITH (m = 32, ef_construction = 128);

-- Tuning at query time (larger = higher recall, slower)
SET hnsw.ef_search = 100;
SELECT * FROM document_embeddings ORDER BY embedding <=> $1 LIMIT 10;

-- Iterative scan — needed when combined with WHERE filters (v0.8+)
SET hnsw.iterative_scan = relaxed_order;
SELECT * FROM document_embeddings
WHERE metadata->>'userId' = '12345'
ORDER BY embedding <=> $1 LIMIT 10;
```

**HNSW operator classes:**
- `vector_l2_ops` — L2 distance
- `vector_cosine_ops` — cosine distance
- `vector_ip_ops` — inner product
- `halfvec_cosine_ops`, `bit_hamming_ops`, etc.

#### IVFFlat (faster builds, more memory efficient)

```sql
-- For up to 1M rows: lists = rows/1000
CREATE INDEX ON document_embeddings USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- Query tuning (start with sqrt(lists))
SET ivfflat.probes = 10;
SELECT * FROM document_embeddings ORDER BY embedding <=> $1 LIMIT 10;
```

**IVFFlat requires pre-loading data** — create index AFTER initial load.

### CRUD Patterns

```sql
-- Insert
INSERT INTO document_embeddings (content, metadata, embedding)
VALUES ('Texto del fragmento', '{"source":"doc1","page":1}'::jsonb, $1);

-- Bulk insert (fastest)
COPY document_embeddings (content, metadata, embedding) FROM STDIN WITH (FORMAT BINARY);

-- Upsert
INSERT INTO document_embeddings (id, content, embedding)
VALUES ($1, $2, $3)
ON CONFLICT (id) DO UPDATE SET embedding = EXCLUDED.embedding;

-- Nearest neighbor with metadata filter
SELECT content, metadata, 1 - (embedding <=> $1) AS score
FROM document_embeddings
WHERE metadata->>'tipo' = 'resolucion'
ORDER BY embedding <=> $1 LIMIT 5;

-- Delete by filter
DELETE FROM document_embeddings WHERE metadata->>'userId' = '12345';

-- Aggregation: average embedding
SELECT AVG(embedding) FROM document_embeddings WHERE metadata->>'tipo' = 'resolucion';
```

### Performance Tuning

```sql
-- Before creating index (speed up HNSW build)
SET maintenance_work_mem = '8GB';
SET max_parallel_maintenance_workers = 7;

-- Parallel queries
SET max_parallel_workers_per_gather = 4;

-- Partial index (per category)
CREATE INDEX ON document_embeddings USING hnsw (embedding vector_cosine_ops)
  WHERE metadata->>'tipo' = 'resolucion';

-- Concurrent reindex (no write lock)
CREATE INDEX CONCURRENTLY ON document_embeddings USING hnsw (embedding vector_cosine_ops);

-- Binary quantization (much faster builds, 32x smaller index)
CREATE INDEX ON document_embeddings
  USING hnsw ((binary_quantize(embedding)::bit(1536)) bit_hamming_ops);

-- Re-rank with original vectors for precision
SELECT * FROM (
  SELECT id FROM document_embeddings
  ORDER BY binary_quantize(embedding)::bit(1536) <~> binary_quantize($1) LIMIT 50
) candidates
JOIN document_embeddings USING (id)
ORDER BY embedding <=> $1 LIMIT 10;
```

### Spring Boot / LangChain4j Integration

```xml
<!-- LangChain4j -->
<dependency>
  <groupId>dev.langchain4j</groupId>
  <artifactId>langchain4j-pgvector</artifactId>
  <version>${langchain4j.version}</version>
</dependency>

<!-- Spring AI -->
<dependency>
  <groupId>org.springframework.ai</groupId>
  <artifactId>spring-ai-starter-vector-store-pgvector</artifactId>
</dependency>
```

```yaml
# Spring AI auto-config
spring:
  ai:
    vectorstore:
      pgvector:
        index-type: HNSW
        distance-type: COSINE_DISTANCE
        dimensions: 1536
        initialize-schema: true       # false after first deploy
        table-name: document_embeddings
```

```java
// LangChain4j manual bean
@Bean
EmbeddingStore<TextSegment> embeddingStore(DataSource ds) {
  return PgVectorEmbeddingStore.builder()
      .datasource(ds)
      .table("document_embeddings")
      .dimension(1536)
      .createTable(true)
      .build();
}

// Spring AI manual bean
@Bean
VectorStore vectorStore(JdbcTemplate jdbc, EmbeddingModel embedding) {
  return PgVectorStore.builder(jdbc, embedding)
      .dimensions(1536)
      .distanceType(PgVectorStore.PgDistanceType.COSINE_DISTANCE)
      .indexType(PgVectorStore.PgIndexType.HNSW)
      .initializeSchema(true)
      .build();
}
```

---

## Metadata Filtering — Cross-Store Comparison

| Store | Filter Style | Example |
|-------|------------|---------|
| pgvector | SQL WHERE | `WHERE metadata->>'tipo' = 'resolucion'` |
| Pinecone | MongoDB-style operators | `{"tipo": {"$eq": "resolucion"}}` |
| Weaviate | GraphQL where | `where: {path:["tipo"], operator:Equal, valueText:"resolucion"}` |
| Milvus | SQL-like expr | `filter="tipo == 'resolucion'"` |
| Qdrant | DSL must/should/must_not | `Filter(must=[FieldCondition(key="tipo", match=MatchValue(value="resolucion"))])` |
| Chroma | where dict | `where={"tipo": {"$eq": "resolucion"}}` |
| MongoDB Atlas | pre-filter field | `filter: {"tipo": "resolucion"}` |
| Elasticsearch | query filter | `"filter": {"term": {"tipo": "resolucion"}}` |
| Redis | FT.SEARCH prefix | `(@tipo:{resolucion})` |
| Azure AI Search | OData filter | `$filter=tipo eq 'resolucion'` |
| LanceDB | SQL WHERE | `.where("tipo = 'resolucion'")` |

---

## Hybrid Search — Cross-Store Summary

| Store | Method | How to Configure |
|-------|--------|----------------|
| Pinecone | Sparse-dense | Send both sparse + dense vectors |
| Weaviate | BM25F + vector | `hybrid(query, alpha=0.5)` — 0=keyword, 1=vector |
| Milvus | AnnSearchRequest per field + RRFRanker | `hybrid_search([req1,req2], ranker)` |
| Elasticsearch | `knn` + `query` clauses | Both in same request, RRF fusion |
| Azure AI Search | `vectorQueries` + `search` | Both in same request, RRF fusion, semantic ranker |
| MongoDB Atlas | `$vectorSearch` + `$search` unionWith | Two pipelines merged |
| Redis | KNN filter + FT.SEARCH | Combine metadata filter with KNN |

---

## Production Defaults — pgvector

- Use `HNSW` for most workloads; `IVFFlat` only when index build time is a constraint
- Set `maintenance_work_mem = 8GB` before building index on large tables
- Use `hnsw.iterative_scan = relaxed_order` when combining vector search with WHERE filters
- Disable `initialize-schema: true` / `createTable(true)` after first production deploy
- Add explicit `metadata` indexes (`CREATE INDEX ON tbl (((metadata->>'userId')))`) for frequently filtered fields
- Use `halfvec` to halve storage for `text-embedding-3-small` at 1536 dims
- Run `VACUUM ANALYZE` after bulk ingestion to update planner statistics
- Monitor index size with `pg_indexes_size('document_embeddings')`
- Test recall: insert known docs, query them back, verify rank-1 is correct
