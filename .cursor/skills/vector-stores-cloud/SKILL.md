---
name: vector-stores-cloud
description: Code patterns for 7 managed/cloud vector stores — Pinecone, Weaviate Cloud, Qdrant Cloud, Milvus/Zilliz Cloud, MongoDB Atlas Vector Search, Azure AI Search, and Google Vertex AI Vector Search. Covers upsert, query, metadata filters, hybrid search, and Python/Java patterns for each. Use when your stack requires a fully managed vector store. See pgvector-rag-patterns for selection matrix and pgvector deep-dive.
metadata:
  origin: sergiomc12-fork
---

# Cloud / Managed Vector Store Patterns

Code patterns for 7 managed vector stores.  
See [[pgvector-rag-patterns]] for selection matrix and pgvector patterns.  
See [[vector-stores-self-hosted]] for Chroma, FAISS, LanceDB, Elasticsearch, OpenSearch, Redis patterns.

## When to Activate

- Choosing or implementing one of these managed stores
- Comparing filtering syntax or hybrid search strategies across cloud stores
- Integrating a cloud vector store with LangChain4j or Spring AI
- Migrating from one cloud store to another

---

## 1. Pinecone

**Model**: Indexes → Namespaces → Records (id + dense vector + metadata)  
**Pricing**: Serverless (pay-per-use) / Pod-based (dedicated)  
**Strengths**: Zero-ops, integrated embeddings, sparse-dense hybrid, reranking API

### Setup

```python
from pinecone import Pinecone

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])

# Create index with integrated embedding model
pc.create_index_for_model(
    name="my-index",
    cloud="aws",
    region="us-east-1",
    embed={
        "model": "llama-text-embed-v2",
        "field_map": {"text": "chunk_text"}
    }
)
index = pc.Index("my-index")
```

```java
// Java
Pinecone pc = new Pinecone.Builder(System.getenv("PINECONE_API_KEY")).build();
Index index = new Index(config, connection, "my-index");
```

### Upsert

```python
records = [
    {"_id": "doc-1", "chunk_text": "El plazo de apelación es de 5 días hábiles.",
     "tipo": "resolucion", "anio": 2026},
    {"_id": "doc-2", "chunk_text": "Los candidatos deben presentar documentos.",
     "tipo": "requisito", "anio": 2025},
]
index.upsert_records("namespace-1", records)
```

### Query

```python
results = index.search(
    namespace="namespace-1",
    query={"inputs": {"text": "¿Cuál es el plazo de apelación?"}, "top_k": 5},
    filter={"tipo": {"$eq": "resolucion"}, "anio": {"$gte": 2025}}
)
for match in results["result"]["hits"]:
    print(match["_id"], match["_score"], match["fields"])
```

### Metadata Filter Operators

| Operator | Types | Example |
|---------|------|---------|
| `$eq` | string, number, boolean | `{"tipo": {"$eq": "resolucion"}}` |
| `$ne` | string, number, boolean | `{"tipo": {"$ne": "borrador"}}` |
| `$gt`, `$gte`, `$lt`, `$lte` | number | `{"anio": {"$gte": 2025}}` |
| `$in` | string, number | `{"tipo": {"$in": ["resolucion","requisito"]}}` |
| `$nin` | string, number | `{"tipo": {"$nin": ["borrador"]}}` |
| `$exists` | any | `{"fecha": {"$exists": true}}` |
| `$and`, `$or` | logical | `{"$and": [{"tipo":{"$eq":"res"}}, {"anio":{"$gte":2025}}]}` |

**Metadata types**: string, integer (→ float64), float, boolean, list of strings.  
**Null not supported. Nested JSON not supported.**

### Hybrid Search (Sparse + Dense)

```python
# Requires separate dense + sparse vectors
results = index.search(
    namespace="namespace-1",
    query={
        "inputs": {"text": "plazo apelación"},
        "top_k": 10
    },
    rerank={
        "model": "bge-reranker-v2-m3",
        "top_n": 5,
        "rank_fields": ["chunk_text"]
    }
)
```

---

## 2. Weaviate

**Model**: Collections → Objects (properties + vector)  
**Strengths**: Multi-modal, named vectors, BM25+vector hybrid, generative search  
**Deployment**: Weaviate Cloud (managed) or self-hosted Docker/K8s

### Setup

```python
import weaviate
from weaviate.classes.config import Configure

client = weaviate.connect_to_weaviate_cloud(
    cluster_url=os.environ["WEAVIATE_URL"],
    auth_credentials=weaviate.auth.AuthApiKey(os.environ["WEAVIATE_API_KEY"])
)

# Create collection with managed embeddings
collection = client.collections.create(
    name="Expediente",
    vectorizer_config=Configure.Vectorizer.text2vec_openai(),
    properties=[
        weaviate.classes.config.Property(name="contenido", data_type=DataType.TEXT),
        weaviate.classes.config.Property(name="tipo", data_type=DataType.TEXT),
        weaviate.classes.config.Property(name="anio", data_type=DataType.INT),
    ]
)
```

```java
// Java client
WeaviateClient client = new WeaviateClient(
    new Config("https", os.getenv("WEAVIATE_HOST"), 443,
        new ApiKeyAuthConfiguration(os.getenv("WEAVIATE_API_KEY")))
);
```

### Insert

```python
collection = client.collections.get("Expediente")
with collection.batch.fixed_size(100) as batch:
    for doc in documents:
        batch.add_object({"contenido": doc.text, "tipo": doc.tipo, "anio": doc.anio})
```

### Semantic Search (nearText)

```python
response = collection.query.near_text(
    query="plazo de apelación electoral",
    limit=5,
    filters=weaviate.classes.query.Filter.by_property("tipo").equal("resolucion")
)
for obj in response.objects:
    print(obj.properties, obj.metadata.distance)
```

### Hybrid Search (BM25F + Vector)

```python
# alpha: 0.0 = pure BM25, 1.0 = pure vector, 0.5 = balanced
response = collection.query.hybrid(
    query="plazo apelación",
    alpha=0.5,                         # balance keyword vs semantic
    fusion_type=HybridFusion.RELATIVE_SCORE,  # or RANKED
    limit=10,
    filters=weaviate.classes.query.Filter.by_property("anio").greater_than(2024)
)
```

### where Filter DSL

```python
from weaviate.classes.query import Filter

# Single condition
Filter.by_property("tipo").equal("resolucion")

# Numeric range
Filter.by_property("anio").greater_than_equal(2025)

# AND combination
Filter.by_property("tipo").equal("resolucion") & Filter.by_property("anio").greater_than(2024)

# OR combination
Filter.by_property("tipo").equal("resolucion") | Filter.by_property("tipo").equal("requisito")
```

### Named Vectors (Multi-modal)

```python
collection = client.collections.create(
    name="MultimodalDoc",
    vector_config=[
        Configure.NamedVectors.text2vec_openai(name="content_vector"),
        Configure.NamedVectors.img2vec_neural(name="image_vector"),
    ]
)

# Search specific vector space
response = collection.query.near_text(
    query="plazo apelación",
    target_vector="content_vector",
    limit=5
)
```

---

## 3. Qdrant

**Model**: Collections → Points (id + vector + payload)  
**Strengths**: Rich payload filters (geo, datetime, nested, phrase), named vectors, sparse vectors  
**Deployment**: Qdrant Cloud or self-hosted Docker

### Setup

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(
    url=os.environ["QDRANT_URL"],
    api_key=os.environ["QDRANT_API_KEY"]
)

client.create_collection(
    collection_name="expedientes",
    vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
)
```

```java
// Java
QdrantClient client = new QdrantClient(
    QdrantGrpcClient.newBuilder(os.getenv("QDRANT_HOST"), 6334, true)
        .withApiKey(os.getenv("QDRANT_API_KEY"))
        .build()
);
```

### Upsert Points

```python
from qdrant_client.models import PointStruct

client.upsert(
    collection_name="expedientes",
    points=[
        PointStruct(
            id="a1b2c3d4-...",
            vector=embedding,
            payload={
                "contenido": "El plazo de apelación...",
                "tipo": "resolucion",
                "anio": 2026,
                "fecha": "2026-03-15T00:00:00Z",
                "ubicacion": {"lon": -77.0428, "lat": -12.0464}
            }
        )
    ]
)
```

### Search with Filter

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

results = client.query_points(
    collection_name="expedientes",
    query=query_vector,
    query_filter=Filter(
        must=[
            FieldCondition(key="tipo", match=MatchValue(value="resolucion")),
            FieldCondition(key="anio", range=Range(gte=2025))
        ]
    ),
    limit=5,
    with_payload=True
)
```

### Complete Filter Reference

```python
from qdrant_client.models import (
    Filter, FieldCondition, MatchValue, MatchAny, MatchExcept,
    MatchText, Range, DatetimeRange, GeoBoundingBox, GeoRadius,
    GeoPoint, ValuesCount, IsEmptyCondition, IsNullCondition, HasIdCondition
)

# OR logic
Filter(should=[
    FieldCondition(key="tipo", match=MatchValue(value="resolucion")),
    FieldCondition(key="tipo", match=MatchValue(value="requisito")),
])

# IN operator
FieldCondition(key="tipo", match=MatchAny(any=["resolucion","requisito"]))

# NOT IN
FieldCondition(key="tipo", match=MatchExcept(except=["borrador"]))

# Text search (with FTS index)
FieldCondition(key="contenido", match=MatchText(text="plazo apelación"))

# Datetime range
FieldCondition(key="fecha", range=DatetimeRange(gte="2025-01-01T00:00:00Z"))

# Geo radius
FieldCondition(key="ubicacion",
    geo_radius=GeoRadius(center=GeoPoint(lon=-77.04, lat=-12.04), radius=5000.0))

# Is empty
Filter(must=[IsEmptyCondition(is_empty=PayloadField(key="apelacion"))])

# Has specific IDs
Filter(must=[HasIdCondition(has_id=[1, 3, 5])])

# Nested array element matching
Filter(must=[{"nested": {"key": "documentos", "filter": {
    "must": [FieldCondition(key="tipo", match=MatchValue(value="dni"))]
}}}])
```

### Java Filter Pattern

```java
client.scrollAsync(ScrollPoints.newBuilder()
    .setCollectionName("expedientes")
    .setFilter(Filter.newBuilder()
        .addMust(matchKeyword("tipo", "resolucion"))
        .addMust(range("anio", Range.newBuilder().setGte(2025).build()))
        .build())
    .build()).get();
```

**IMPORTANT**: Create payload indexes before large-scale filtering:
```python
client.create_payload_index("expedientes", "tipo",
    field_schema=PayloadSchemaType.KEYWORD)
client.create_payload_index("expedientes", "fecha",
    field_schema=PayloadSchemaType.DATETIME)
```

---

## 4. Milvus / Zilliz Cloud

**Model**: Collections → Schemas (typed fields) → Partitions  
**Strengths**: Billion-scale, multi-vector hybrid, BM25 built-in, DISKANN for disk-based  
**Deployment**: Milvus Lite (dev), Docker, K8s, Zilliz Cloud (managed)

### Setup

```python
from pymilvus import MilvusClient, DataType, Function, FunctionType

# Zilliz Cloud
client = MilvusClient(
    uri=os.environ["ZILLIZ_URI"],
    token=os.environ["ZILLIZ_TOKEN"]
)
# Self-hosted
# client = MilvusClient(uri="http://localhost:19530", token="root:Milvus")
# Embedded (dev)
# client = MilvusClient("milvus_local.db")
```

### Schema Design (typed fields)

```python
schema = client.create_schema(auto_id=False)
schema.add_field("id",        DataType.INT64,  is_primary=True)
schema.add_field("contenido", DataType.VARCHAR, max_length=2000)
schema.add_field("tipo",      DataType.VARCHAR, max_length=50)
schema.add_field("anio",      DataType.INT32)
schema.add_field("dense_vec", DataType.FLOAT_VECTOR, dim=1536)
schema.add_field("sparse_vec",DataType.SPARSE_FLOAT_VECTOR)  # BM25

# Built-in BM25 function (auto-generates sparse vectors)
bm25_fn = Function(
    name="bm25",
    input_field_names=["contenido"],
    output_field_names=["sparse_vec"],
    function_type=FunctionType.BM25
)
schema.add_function(bm25_fn)
```

### Index Types Reference

| Type | Best For | Key Params |
|------|---------|-----------|
| `FLAT` | Exact search, small datasets | — |
| `IVF_FLAT` | Balanced speed/accuracy | `nlist=100`, `nprobe=10` |
| `IVF_SQ8` | Reduced memory | `nlist=100` |
| `IVF_PQ` | Large datasets, compressed | `nlist=100`, `m=8`, `nbits=8` |
| `HNSW` | High recall, in-memory | `m=16`, `efConstruction=64`, `ef=10` |
| `SCANN` | Fastest approximate | `nlist=1024`, `with_raw_data=true` |
| `DISKANN` | Billion-scale, disk-based | `max_degree=56`, `search_list_size=100` |
| `SPARSE_INVERTED_INDEX` | Sparse / BM25 | `inverted_index_algo=DAAT_MAXSCORE` |
| `AUTOINDEX` | Auto-choose (Zilliz Cloud) | — |

```python
index_params = client.prepare_index_params()
index_params.add_index("dense_vec", index_type="HNSW", metric_type="COSINE",
                       params={"m": 16, "efConstruction": 64})
index_params.add_index("sparse_vec", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25",
                       params={"inverted_index_algo": "DAAT_MAXSCORE"})

client.create_collection("expedientes", schema=schema, index_params=index_params)
```

### Insert

```python
client.insert("expedientes", [
    {"id": 1, "contenido": "El plazo de apelación es 5 días.",
     "tipo": "resolucion", "anio": 2026, "dense_vec": embedding}
])
```

### Search

```python
# Dense vector search with filter
results = client.search(
    collection_name="expedientes",
    data=[query_vector],
    anns_field="dense_vec",
    search_params={"metric_type": "COSINE", "params": {"ef": 64}},
    filter='tipo == "resolucion" and anio >= 2025',
    output_fields=["contenido", "tipo", "anio"],
    limit=5
)
```

### Hybrid Search (Dense + BM25)

```python
from pymilvus import AnnSearchRequest

req_dense = AnnSearchRequest(
    data=[query_vector], anns_field="dense_vec",
    param={"metric_type": "COSINE"}, limit=10
)
req_sparse = AnnSearchRequest(
    data=[query_text], anns_field="sparse_vec", limit=10
)

results = client.hybrid_search(
    collection_name="expedientes",
    reqs=[req_dense, req_sparse],
    ranker=Function(name="rrf", function_type=FunctionType.RERANK,
                    input_field_names=[], params={"reranker": "rrf", "k": 100}),
    limit=5
)
```

---

## 5. MongoDB Atlas Vector Search

**Model**: Documents in Atlas collections with vector array fields  
**Strengths**: JSON documents, existing Mongo users, $vectorSearch pipeline  
**Deployment**: Atlas only (not self-hosted)

### Index Configuration (Atlas UI or API)

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine"
    },
    {"type": "filter", "path": "tipo"},
    {"type": "filter", "path": "anio"}
  ]
}
```

### Python Patterns

```python
from pymongo import MongoClient

client = MongoClient(os.environ["MONGODB_URI"])
db = client["expedientes_db"]
collection = db["documentos"]

# Insert
collection.insert_one({
    "contenido": "El plazo de apelación es 5 días.",
    "tipo": "resolucion",
    "anio": 2026,
    "embedding": embedding   # list[float]
})

# Vector search (ANN — approximate)
pipeline = [
    {
        "$vectorSearch": {
            "index": "vector_index",
            "path": "embedding",
            "queryVector": query_embedding,
            "numCandidates": 100,   # ANN: candidates to examine
            "limit": 5,
            "filter": {"tipo": "resolucion", "anio": {"$gte": 2025}}
        }
    },
    {
        "$project": {
            "contenido": 1,
            "tipo": 1,
            "anio": 1,
            "score": {"$meta": "vectorSearchScore"}
        }
    }
]
results = list(collection.aggregate(pipeline))

# Exact nearest neighbor (ENN — requires MongoDB 6.0.16+)
pipeline_enn = [
    {
        "$vectorSearch": {
            "index": "vector_index",
            "path": "embedding",
            "queryVector": query_embedding,
            "ef": 40,    # ENN: dynamic candidate list (instead of numCandidates)
            "limit": 5
        }
    }
]
```

**Max dimensions**: 8,192  
**Similarity options**: `cosine`, `euclidean`, `dotProduct`  
**Filter fields** must be declared in the index with `"type": "filter"`.

---

## 6. Azure AI Search

**Model**: Index (schema) → Documents (with vector fields)  
**Strengths**: Full Azure ecosystem, hybrid vector+BM25, semantic ranker, RRF fusion  
**Deployment**: Azure managed service

### Search Request (REST)

```http
POST https://{service}.search.windows.net/indexes/{index}/docs/search?api-version=2026-04-01
Content-Type: application/json
api-key: {admin-api-key}

{
  "select": "id, contenido, tipo",
  "vectorQueries": [
    {
      "kind": "vector",
      "vector": [/* 1536 floats */],
      "fields": "embedding",
      "k": 10,
      "weight": 0.7,
      "exhaustive": false
    }
  ],
  "filter": "tipo eq 'resolucion' and anio ge 2025",
  "vectorFilterMode": "postFilter"
}
```

### Hybrid Search (Vector + BM25 + Semantic Ranker)

```http
{
  "search": "plazo apelación",
  "searchFields": "contenido",
  "queryType": "semantic",
  "semanticConfiguration": "my-semantic-config",
  "vectorQueries": [
    {
      "kind": "text",
      "text": "plazo apelación",
      "fields": "embedding",
      "k": 50
    }
  ],
  "filter": "tipo eq 'resolucion'",
  "select": "contenido, tipo, anio",
  "top": 5
}
```

**Note**: Set `k=50` when using semantic ranker (needs 50 inputs).

### Python SDK Pattern

```python
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential

client = SearchClient(
    endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
    index_name="expedientes",
    credential=AzureKeyCredential(os.environ["AZURE_SEARCH_API_KEY"])
)

results = client.search(
    search_text="plazo apelación",
    vector_queries=[
        VectorizedQuery(
            vector=query_embedding,
            k_nearest_neighbors=10,
            fields="embedding",
            weight=0.7
        )
    ],
    filter="tipo eq 'resolucion'",
    select=["contenido", "tipo", "anio"],
    top=5
)

for r in results:
    print(r["contenido"], r["@search.score"])
```

### Threshold (Exclude Low Scores)

```json
"vectorQueries": [{
  "kind": "vector",
  "vector": [...],
  "fields": "embedding",
  "k": 10,
  "threshold": {"kind": "vectorSimilarity", "value": 0.8}
}]
```

**Filter syntax** uses OData 4.0: `tipo eq 'X'`, `anio ge 2025`, `tipo in ('X','Y')`.  
**Filter modes**: `preFilter` (applied before KNN — fewer candidates), `postFilter` (applied after KNN — may return fewer than k).

---

## 7. Google Vertex AI Vector Search

**Model**: Index → Index Endpoint → Deployed Index → Datapoints  
**Algorithm**: ScaNN (tree-AH) — Google's custom ANN  
**Deployment**: GCP managed, autoscaling  
**Strengths**: Petabyte-scale, streaming updates, token/numeric restricts

### Setup

```python
from google.cloud import aiplatform

aiplatform.init(project=os.environ["GCP_PROJECT"], location="us-central1")

# Create index
my_index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
    display_name="expedientes-index",
    contents_delta_uri=f"gs://{bucket}/initial_data/",
    dimensions=1536,
    approximate_neighbors_count=100,
    distance_measure_type="COSINE_DISTANCE"
)

# Create endpoint
endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
    display_name="expedientes-endpoint",
    public_endpoint_enabled=True
)

# Deploy
endpoint.deploy_index(
    index=my_index,
    deployed_index_id="expedientes_deployed"
)
```

### Query

```python
response = endpoint.find_neighbors(
    deployed_index_id="expedientes_deployed",
    queries=[query_embedding],
    num_neighbors=10,
    # Numeric restricts: pre-filter before ANN
    numeric_filter_restrictions=[
        {
            "namespace": "anio",
            "value_int": 2025,
            "op": "GREATER_EQUAL"
        }
    ],
    # Token (string) restricts
    restricts=[
        {"namespace": "tipo", "allow": ["resolucion"]}
    ]
)

for neighbor in response[0]:
    print(neighbor.id, neighbor.distance)
```

**Distance metrics**: `DOT_PRODUCT_DISTANCE`, `COSINE_DISTANCE`, `L1_DISTANCE`, `SQUARED_L2_DISTANCE`

### JSONL Data Format (for index creation)

```jsonl
{"id": "doc-1", "embedding": [0.1, 0.2, ...], "restricts": [{"namespace": "tipo", "allow": ["resolucion"]}], "numeric_restricts": [{"namespace": "anio", "value_int": 2026}]}
```

---

## Production Defaults — Cloud Stores

| Concern | Recommendation |
|---------|--------------|
| API keys | Always `os.environ["KEY"]`, never hardcoded |
| Metadata fields | Index ALL fields you filter on (Qdrant: payload index, Atlas: filter field, Azure: filterable:true) |
| Similarity threshold | Start `0.70–0.75`; measure precision@5 on golden test set |
| Namespace/partition | Use one per tenant for multi-tenant workloads |
| Upsert vs insert | Prefer upsert — safe for re-ingestion |
| Hybrid search | Always test hybrid vs vector-only; hybrid wins for most RAG workloads |
| Reranking | Add Cohere `rerank-multilingual-v3.0` or Pinecone `bge-reranker-v2-m3` for top-k > 10 |
| Batch ingestion | Batch upserts (Pinecone: 100 records/batch, Qdrant: 100 points/batch) |
| Error handling | Retry transient 429/503 with exponential backoff (2s, 4s, 8s) |
