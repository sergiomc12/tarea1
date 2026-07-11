---
name: vector-stores-self-hosted
description: Code patterns for 6 self-hosted / open-source vector stores — Chroma, LanceDB, FAISS, Elasticsearch, AWS OpenSearch, and Redis/RediSearch. Covers setup, upsert, vector search, metadata filtering, hybrid search, and Python/Java patterns for each. Use when running vector search on your own infrastructure. See pgvector-rag-patterns for selection matrix and pgvector patterns.
metadata:
  origin: sergiomc12-fork
---

# Self-Hosted / Open-Source Vector Store Patterns

Code patterns for 6 open-source / self-hosted vector stores.  
See [[pgvector-rag-patterns]] for selection matrix, pgvector deep-dive, and universal RAG patterns.  
See [[vector-stores-cloud]] for Pinecone / Weaviate / Qdrant / MongoDB Atlas / Azure AI Search / Google Vertex AI.

## When to Activate

- Implementing a self-hosted vector search stack
- Choosing between Chroma / LanceDB / FAISS for a Python ML pipeline
- Adding vector search to an existing Elasticsearch or Redis deployment
- AWS-native RAG using OpenSearch Service
- Comparing filtering syntax or index options across self-hosted stores

---

## 1. Chroma

**Model**: Collections → Documents (content + embeddings + metadata + IDs)  
**Strengths**: Easiest Python setup, automatic embedding functions, dev-friendly  
**Deployment**: In-process (embedded), persistent, or client-server mode  
**NOT production-scale** — use for prototyping, dev, testing

### Setup

```python
# In-memory (lost on restart)
import chromadb
client = chromadb.Client()

# Persistent (saved to disk)
client = chromadb.PersistentClient(path="./chroma_db")

# Client-server (run: chroma run --path /data)
client = chromadb.HttpClient(host="localhost", port=8000)
```

### Create Collection

```python
# With built-in embedding function (OpenAI)
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

collection = client.create_collection(
    name="expedientes",
    embedding_function=OpenAIEmbeddingFunction(
        api_key=os.environ["OPENAI_API_KEY"],
        model_name="text-embedding-3-small"
    )
)

# With custom embedding function (self-hosted model)
class MyEmbeddingFunction(chromadb.EmbeddingFunction):
    def __call__(self, texts):
        return model.encode(texts).tolist()

collection = client.create_collection("expedientes", embedding_function=MyEmbeddingFunction())

# Get or create (safe for re-runs)
collection = client.get_or_create_collection("expedientes",
    embedding_function=OpenAIEmbeddingFunction(...))
```

### Add Documents

```python
collection.add(
    ids=["doc-1", "doc-2", "doc-3"],
    documents=["El plazo de apelación es 5 días.", "Los candidatos deben...", "..."],
    metadatas=[
        {"tipo": "resolucion", "anio": 2026},
        {"tipo": "requisito", "anio": 2025},
        {"tipo": "resolucion", "anio": 2026}
    ]
    # embeddings=[[...], [...]]  # optional: skip if collection has embedding_function
)

# Upsert (safe for re-ingestion)
collection.upsert(ids=["doc-1"], documents=["Updated text"], metadatas=[{"tipo": "resolucion"}])
```

### Query

```python
results = collection.query(
    query_texts=["¿Cuál es el plazo de apelación?"],
    n_results=5,
    where={"tipo": {"$eq": "resolucion"}},
    where_document={"$contains": "plazo"},
    include=["documents", "metadatas", "distances"]
)
print(results["ids"], results["distances"], results["documents"])

# With pre-computed query embedding
results = collection.query(
    query_embeddings=[query_vector],
    n_results=5,
    where={"anio": {"$gte": 2025}}
)
```

### Filter Operators

```python
# Metadata (where) operators
where={"tipo": {"$eq": "resolucion"}}         # equals
where={"tipo": {"$ne": "borrador"}}            # not equals
where={"anio": {"$gt": 2024}}                  # greater than
where={"anio": {"$gte": 2025}}                 # greater or equal
where={"anio": {"$lt": 2027}}                  # less than
where={"anio": {"$lte": 2026}}                 # less or equal
where={"tipo": {"$in": ["resolucion","req"]}}  # in list
where={"tipo": {"$nin": ["borrador"]}}         # not in list

# Logical operators
where={"$and": [{"tipo": {"$eq": "resolucion"}}, {"anio": {"$gte": 2025}}]}
where={"$or":  [{"tipo": {"$eq": "resolucion"}}, {"tipo": {"$eq": "requisito"}}]}

# Document content operators (where_document)
where_document={"$contains": "plazo apelación"}     # substring match
where_document={"$not_contains": "borrador"}         # not contains
where_document={"$matches": "^El plazo.*días\.$"}    # regex
```

### Get by ID / Paginate

```python
# Get specific IDs
collection.get(ids=["doc-1", "doc-2"])

# Paginate
collection.get(limit=100, offset=0)

# Delete
collection.delete(ids=["doc-1"])
collection.delete(where={"tipo": "borrador"})
```

---

## 2. LanceDB

**Model**: Tables (Lance columnar format) → Records  
**Strengths**: Embedded, columnar storage, multimodal, SQL WHERE filters, no server for dev  
**Deployment**: Embedded (local Lance files), or LanceDB Cloud  
**Languages**: Python, TypeScript, Java, Rust

### Setup

```python
import lancedb
import pyarrow as pa
from lancedb.schema import vector

# Local embedded (creates files in ./lance_db/)
db = lancedb.connect("./lance_db")

# LanceDB Cloud
# db = lancedb.connect("db://my-project", api_key=os.environ["LANCEDB_API_KEY"])
```

### Create Table with Schema

```python
schema = pa.schema([
    pa.field("id",        pa.string()),
    pa.field("contenido", pa.string()),
    pa.field("tipo",      pa.string()),
    pa.field("anio",      pa.int32()),
    pa.field("embedding", vector(1536)),  # float32 array
])

table = db.create_table("expedientes", schema=schema)
```

### Add Data

```python
import pandas as pd

data = [
    {"id": "doc-1", "contenido": "El plazo de apelación...",
     "tipo": "resolucion", "anio": 2026, "embedding": embedding_vector},
]

table.add(data)
# or
table = db.create_table("expedientes", data=data)  # create + add in one step
```

### Vector Search

```python
# Basic vector search
results = table.search(query_vector).limit(10).to_pandas()

# With distance metric
results = (table.search(query_vector)
    .distance_type("cosine")   # "cosine" | "l2" | "dot"
    .limit(5)
    .to_pandas())

# With SQL WHERE filter
results = (table.search(query_vector)
    .where("tipo = 'resolucion' AND anio >= 2025")
    .limit(5)
    .to_pandas())
```

### Full-Text Search (BM25)

```python
from lancedb.index import FTS

# Create FTS index first
table.create_fts_index("contenido", config=FTS(
    language="es",
    stem=True,
    remove_stop_words=True
))

# Full-text search
results = table.search("plazo apelación", query_type="fts").limit(10).to_pandas()

# Hybrid: vector + FTS
results = (table.search("plazo apelación", query_type="hybrid")
    .limit(10)
    .to_pandas())
```

### Index Creation

```python
# IVF-PQ (Inverted File + Product Quantization) — recommended for large tables
table.create_index(
    metric="cosine",
    index_type="ivf_pq",
    num_partitions=256,
    num_sub_vectors=96
)

# HNSW
table.create_index(
    metric="cosine",
    index_type="hnsw",
    m=16,
    ef_construction=64
)
```

### Update and Delete

```python
table.update({"tipo": "RESOLUCION"}, where="tipo = 'resolucion'")
table.delete("anio < 2020")
```

### Result Formats

```python
table.search(query_vector).to_pandas()   # pandas DataFrame
table.search(query_vector).to_arrow()    # PyArrow Table
table.search(query_vector).to_list()     # list of dicts
table.search(query_vector).to_polars()   # Polars DataFrame
```

---

## 3. FAISS

**Model**: In-process index (RAM or mmap) — no persistence, no metadata  
**Strengths**: Maximum throughput, 10+ index types, GPU support  
**Deployment**: In-process Python/C++ library  
**Limitation**: No filtering, no IDs by default, no server — pure vector math

### Installation

```bash
conda install -c pytorch faiss-cpu         # CPU
conda install -c pytorch faiss-gpu         # CUDA GPU (superset)
pip install faiss-cpu                      # pip alternative
```

### Index Types Reference

| Index | Factory String | Memory/vec | Training | Best For |
|-------|--------------|-----------|---------|---------|
| `IndexFlatL2` | `Flat` | `4*d` bytes | No | Exact L2, small datasets |
| `IndexFlatIP` | `FlatIP` | `4*d` bytes | No | Exact inner product / cosine |
| `IndexIVFFlat` | `IVF100,Flat` | `4*d + 8` bytes | Yes | Large datasets, moderate recall |
| `IndexIVFSQ` | `IVF100,SQ8` | `d + 8` bytes | Yes | Memory-efficient approximate |
| `IndexIVFPQ` | `IVF100,PQ16x8` | `16 + 8` bytes | Yes | Billion-scale, compressed |
| `IndexHNSW` | `HNSW32,Flat` | `4*d + 4*M*2` | No | High recall, no removal |
| `IndexPQ` | `PQ16x8` | `16` bytes | Yes | Extreme compression |
| `IndexLSH` | `LSH` | `nbits/8` bytes | Yes | Binary, very fast |

### Python Code Patterns

```python
import faiss
import numpy as np

d = 1536  # dimensions

# 1. Exact search (brute force)
index_flat = faiss.IndexFlatL2(d)         # L2 distance
index_flat_ip = faiss.IndexFlatIP(d)      # inner product (cosine with normalized vecs)

index_flat.add(vectors)                    # vectors: np.float32 shape (n, d)
D, I = index_flat.search(query, k=10)     # D=distances, I=indices

# 2. IVF — large scale approximate
quantizer = faiss.IndexFlatL2(d)
index_ivf = faiss.IndexIVFFlat(quantizer, d, nlist=100)
index_ivf.train(training_vectors)          # must train before add
index_ivf.add(vectors)
index_ivf.nprobe = 10                      # trade recall for speed
D, I = index_ivf.search(query, k=10)

# 3. IVFPQ — billion-scale compressed
coarse = faiss.IndexFlatL2(d)
index_ivfpq = faiss.IndexIVFPQ(coarse, d, nlist=1024, m=16, nbits=8)
index_ivfpq.train(training_vectors)
index_ivfpq.add(vectors)
index_ivfpq.nprobe = 20
D, I = index_ivfpq.search(query, k=10)

# 4. HNSW — high recall, no training
index_hnsw = faiss.IndexHNSWFlat(d, 32)   # m=32 neighbors
index_hnsw.hnsw.efConstruction = 64
index_hnsw.hnsw.efSearch = 40
index_hnsw.add(vectors)
D, I = index_hnsw.search(query, k=10)

# 5. Index factory (concise syntax)
index = faiss.index_factory(d, "IVF1024,PQ16")

# Cosine similarity: normalize first
faiss.normalize_L2(vectors)
faiss.normalize_L2(query)
index_ip = faiss.IndexFlatIP(d)
index_ip.add(vectors)
D, I = index_ip.search(query, k=10)  # D = cosine similarity scores

# Save/load index
faiss.write_index(index, "index.faiss")
index = faiss.read_index("index.faiss")

# GPU (faster search + training)
res = faiss.StandardGpuResources()
gpu_index = faiss.index_cpu_to_gpu(res, 0, index_cpu)
```

### When to Choose Which FAISS Index

```
Dataset < 10K vectors     → IndexFlatL2 (exact, fast enough)
Dataset < 1M vectors      → IndexIVFFlat (nlist ≈ sqrt(n))
Dataset 1M–100M           → IndexIVFPQ (m=8 or 16)
Need high recall + speed  → IndexHNSW (no training, no removal)
Extreme memory constraint → IndexIVFPQ (16 bytes/vector)
Binary vectors            → IndexBinaryFlat or IndexBinaryIVF
```

### Pairing FAISS with Metadata Filtering

FAISS has no metadata — pair with a separate store:

```python
# Pattern: FAISS (vector) + dict/DB (metadata)
id_to_metadata = {i: {"tipo": "resolucion", "texto": "..."} for i, _ in enumerate(documents)}

D, I = faiss_index.search(query_vector, k=50)   # over-retrieve
results = []
for dist, idx in zip(D[0], I[0]):
    meta = id_to_metadata[idx]
    if meta["tipo"] == "resolucion":              # filter metadata
        results.append({"score": float(dist), **meta})
    if len(results) >= 5:
        break
```

---

## 4. Elasticsearch

**Model**: Indexes → Documents (JSON with `dense_vector` fields)  
**Strengths**: Hybrid text+vector, existing ES clusters, BM25+kNN  
**Deployment**: Self-hosted or Elastic Cloud (managed)

### Index Mapping

```json
PUT /expedientes
{
  "mappings": {
    "properties": {
      "contenido": {"type": "text", "analyzer": "spanish"},
      "tipo":      {"type": "keyword"},
      "anio":      {"type": "integer"},
      "embedding": {
        "type": "dense_vector",
        "dims": 1536,
        "element_type": "float",
        "similarity": "cosine",
        "index_options": {
          "type": "int8_hnsw",
          "m": 16,
          "ef_construction": 100,
          "rescore_vector": {"oversample": 1.5}
        }
      }
    }
  }
}
```

**Index types by version:**
- ES 9.0+: `int8_hnsw` default for float vectors (8x compression vs full float)
- ES 9.1+: `bbq_hnsw` default for ≥384 dims (32x compression)
- `flat`: exhaustive exact search
- `hnsw`: full float HNSW

### Index Data

```python
from elasticsearch import Elasticsearch, helpers

es = Elasticsearch(
    hosts=os.environ["ES_URL"],
    api_key=os.environ["ES_API_KEY"]
)

# Bulk index
actions = [
    {
        "_index": "expedientes",
        "_id": f"doc-{i}",
        "_source": {
            "contenido": doc.text,
            "tipo": doc.tipo,
            "anio": doc.anio,
            "embedding": doc.embedding
        }
    }
    for i, doc in enumerate(documents)
]
helpers.bulk(es, actions)
```

### kNN Search

```python
response = es.search(
    index="expedientes",
    body={
        "knn": {
            "field": "embedding",
            "query_vector": query_embedding,
            "k": 10,
            "num_candidates": 100,
            "filter": {
                "bool": {
                    "must": [
                        {"term": {"tipo": "resolucion"}},
                        {"range": {"anio": {"gte": 2025}}}
                    ]
                }
            }
        },
        "_source": ["contenido", "tipo", "anio"],
        "size": 5
    }
)
for hit in response["hits"]["hits"]:
    print(hit["_score"], hit["_source"]["contenido"])
```

### Hybrid Search (kNN + BM25)

```python
response = es.search(
    index="expedientes",
    body={
        "knn": {
            "field": "embedding",
            "query_vector": query_embedding,
            "k": 10,
            "num_candidates": 100
        },
        "query": {
            "match": {
                "contenido": {
                    "query": "plazo apelación",
                    "boost": 1.0
                }
            }
        },
        "size": 5
    }
)
```

Elasticsearch fuses kNN + BM25 results automatically using RRF (reciprocal rank fusion) when both are in the same request.

---

## 5. AWS OpenSearch Service (k-NN)

**Model**: Indexes (k-NN enabled) → Documents with `knn_vector` fields  
**Strengths**: AWS-native, managed, supports HNSW via nmslib/faiss/lucene engines  
**Deployment**: AWS OpenSearch Service (managed), OpenSearch self-hosted  
**Note**: AWS OpenSearch diverged from Elasticsearch at version 7.10

### Index Creation

```json
PUT /expedientes
{
  "settings": {
    "index.knn": true
  },
  "mappings": {
    "properties": {
      "contenido": {"type": "text"},
      "tipo":      {"type": "keyword"},
      "anio":      {"type": "integer"},
      "embedding": {
        "type": "knn_vector",
        "dimension": 1536,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "lucene",
          "parameters": {
            "m": 16,
            "ef_construction": 100
          }
        }
      }
    }
  }
}
```

**Engines:**
- `lucene` — pure Java, good recall, recommended for most workloads
- `faiss` — better for large datasets, GPU-capable
- `nmslib` — legacy, fastest approximate search

**space_type options:** `cosinesimil`, `l2`, `innerproduct`

### Insert

```json
POST /expedientes/_bulk
{"index": {"_id": "doc-1"}}
{"contenido": "El plazo de apelación...", "tipo": "resolucion", "anio": 2026, "embedding": [0.1, 0.2, ...]}
```

### k-NN Search

```json
GET /expedientes/_search
{
  "size": 5,
  "query": {
    "knn": {
      "embedding": {
        "vector": [0.1, 0.2, ...],
        "k": 10
      }
    }
  },
  "post_filter": {
    "bool": {
      "must": [
        {"term": {"tipo": "resolucion"}},
        {"range": {"anio": {"gte": 2025}}}
      ]
    }
  }
}
```

**Note:** Use `post_filter` (not `filter` inside `knn`) to apply metadata filtering after the kNN search — `filter` inside `knn` reduces the candidate set before ANN, which can hurt recall.

### Python Pattern

```python
from opensearchpy import OpenSearch, helpers

client = OpenSearch(
    hosts=[{"host": os.environ["OS_HOST"], "port": 443}],
    http_auth=("user", os.environ["OS_PASSWORD"]),
    use_ssl=True,
    verify_certs=True
)

response = client.search(
    index="expedientes",
    body={
        "size": 5,
        "query": {"knn": {"embedding": {"vector": query_vector, "k": 10}}},
        "post_filter": {"term": {"tipo": "resolucion"}}
    }
)
```

### Bulk Search (Multi-Query)

```json
GET /_msearch
{"index": "expedientes"}
{"query": {"knn": {"embedding": {"vector": [1,2,...], "k": 5}}}}
{"index": "expedientes"}
{"query": {"knn": {"embedding": {"vector": [3,4,...], "k": 5}}}}
```

---

## 6. Redis / RediSearch

**Model**: Redis hashes → Indexed with FT.CREATE → Searched with FT.SEARCH  
**Strengths**: Sub-millisecond latency, cache + vector in one store, hybrid metadata filtering  
**Deployment**: Redis Stack (self-hosted with modules), Redis Cloud  
**Limitation**: All vectors in RAM — expensive at scale

### Index Creation

```bash
# FLAT (brute force — exact, dev/small datasets)
FT.CREATE idx ON HASH PREFIX 1 "doc:"
  SCHEMA
    contenido TEXT
    tipo TAG
    anio NUMERIC SORTABLE
    embedding VECTOR FLAT 6
      TYPE FLOAT32 DIM 1536 DISTANCE_METRIC COSINE

# HNSW (approximate — production)
FT.CREATE idx ON HASH PREFIX 1 "doc:"
  SCHEMA
    contenido TEXT
    tipo TAG
    anio NUMERIC SORTABLE
    embedding VECTOR HNSW 10
      TYPE FLOAT32 DIM 1536 DISTANCE_METRIC COSINE
      M 16 EF_CONSTRUCTION 200 EF_RUNTIME 10
```

**Distance metrics:** `COSINE`, `IP` (inner product), `L2`

### Insert Data

```bash
HSET doc:1
  contenido "El plazo de apelación es 5 días."
  tipo "resolucion"
  anio 2026
  embedding <binary_float32_vector>
```

### KNN Search

```bash
# Pure vector KNN
FT.SEARCH idx "*=>[KNN 10 @embedding $vec]"
  PARAMS 2 vec <binary_vector>
  RETURN 3 contenido tipo anio
  LIMIT 0 10

# Hybrid: metadata filter + KNN
FT.SEARCH idx "(@tipo:{resolucion} @anio:[2025 +inf])=>[KNN 10 @embedding $vec]"
  PARAMS 2 vec <binary_vector>
  RETURN 3 contenido tipo anio
  LIMIT 0 5

# Multiple TAG values (OR)
FT.SEARCH idx "(@tipo:{resolucion|requisito})=>[KNN 5 @embedding $vec]"
  PARAMS 2 vec <binary_vector>
```

**Filter syntax reference:**
- `@tag:{value}` — exact tag match
- `@tag:{val1|val2}` — OR
- `@numeric:[min max]` — range
- `@text:keyword` — full-text
- `(@f1:{x})(@f2:[0 100])` — AND

### Python (redis-py)

```python
import redis
import numpy as np
from redis.commands.search.field import VectorField, TagField, TextField, NumericField
from redis.commands.search.query import Query

r = redis.Redis(host=os.environ["REDIS_HOST"], port=6379,
                password=os.environ["REDIS_PASSWORD"], decode_responses=False)

# Create index
r.ft("idx").create_index([
    VectorField("embedding", "HNSW", {
        "DIM": 1536, "TYPE": "FLOAT32", "DISTANCE_METRIC": "COSINE",
        "M": 16, "EF_CONSTRUCTION": 200
    }),
    TagField("tipo"),
    TextField("contenido"),
    NumericField("anio")
])

# Add document
r.hset("doc:1", mapping={
    "contenido": "El plazo de apelación es 5 días.",
    "tipo": "resolucion",
    "anio": 2026,
    "embedding": np.array(embedding, dtype=np.float32).tobytes()
})

# Search
query_bytes = np.array(query_vector, dtype=np.float32).tobytes()
results = r.ft("idx").search(
    Query("(@tipo:{resolucion})=>[KNN 10 @embedding $vec]")
    .return_fields("contenido", "tipo", "anio")
    .paging(0, 5)
    .params({"vec": query_bytes})
)
for doc in results.docs:
    print(doc.tipo, doc.contenido)
```

### Java (Jedis)

```java
import redis.clients.jedis.JedisCluster;
import redis.clients.jedis.search.*;
import redis.clients.jedis.search.schemafields.*;

JedisCluster jedis = new JedisCluster(nodes, jedisClusterConfig);

// Create index
Schema schema = new Schema()
    .addField(new VectorField("embedding", VectorField.VectorAlgorithm.HNSW,
        new VectorField.VectorFieldAttributes()
            .dimension(1536)
            .distanceMetric(VectorField.DistanceMetric.COSINE)))
    .addSortableTagField("tipo")
    .addTextField("contenido", 1.0f);

jedis.ftCreate("idx", FTCreateParams.createParams().on(IndexDataType.HASH), schema);

// Search
byte[] queryVec = toFloat32Bytes(queryEmbedding);
Map<String, Object> params = Map.of("vec", queryVec);
SearchResult result = jedis.ftSearch("idx",
    "(@tipo:{resolucion})=>[KNN 10 @embedding $vec]",
    FTSearchParams.searchParams()
        .params(params)
        .returnFields("contenido", "tipo", "anio")
        .limit(0, 5));
```

---

## Production Defaults — Self-Hosted Stores

| Concern | Recommendation |
|---------|--------------|
| **Chroma** | Use `PersistentClient` for anything beyond single-session testing; use `upsert` not `add` for safe re-ingestion |
| **LanceDB** | Create IVF_PQ index once table exceeds 10K records; use `.where()` SQL filters for metadata |
| **FAISS** | Store metadata separately (dict / SQLite / Postgres); normalize vectors before `IndexFlatIP` for cosine; save index with `write_index()` periodically |
| **Elasticsearch** | Use `int8_hnsw` (default in ES 9) — 8x compression with ~1-2% recall loss; `rescore_vector.oversample=1.5` recovers quality; disable `exclude_source_vectors` only when you need to retrieve raw vectors |
| **OpenSearch** | Enable `knn.memory.circuit_breaker.limit` monitoring; use `lucene` engine unless you need GPU; add `post_filter` (not in-KNN filter) to avoid reducing ANN candidate set |
| **Redis** | Use `HNSW` for production (FLAT only for ≤10K docs); convert vectors to `FLOAT32` bytes with `np.array(..., dtype=np.float32).tobytes()`; monitor `KNNGraphMemoryUsage` metric |
| **All** | Pre-index filterable metadata fields before ingesting large datasets — adding indexes post-hoc is slow |
| **All** | Measure recall on a golden test set (query 10 known docs, expect rank-1 correct) before going to production |
