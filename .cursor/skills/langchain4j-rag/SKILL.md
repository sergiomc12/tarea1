---
name: langchain4j-rag
description: LangChain4j RAG pipeline — document loading, chunking, embedding, pgvector, query transformation, routing, re-ranking, and content injection. Use when building retrieval-augmented generation with Java Spring Boot. For core AI Services see langchain4j-patterns. For tools see langchain4j-tools.
metadata:
  origin: sergiomc12-fork
---

# LangChain4j RAG Pipeline

Complete RAG (Retrieval-Augmented Generation) patterns for Spring Boot.
See [[langchain4j-patterns]] for AI Services core and [[langchain4j-tools]] for tool calling.

## When to Activate

- Answering questions from your own documents (PDFs, Word, text, web pages)
- Building a knowledge base search over domain-specific content
- Implementing semantic search over a pgvector / PostgreSQL store
- Needing query compression, routing, or re-ranking for better retrieval quality
- Accessing retrieved document sources (`result.sources()`, `onRetrieved(...)`)

## Dependencies (Maven)

```xml
<!-- Core RAG + Spring Boot auto-config -->
<dependency>
  <groupId>dev.langchain4j</groupId>
  <artifactId>langchain4j-spring-boot-starter</artifactId>
  <version>${langchain4j.version}</version>
</dependency>
<dependency>
  <groupId>dev.langchain4j</groupId>
  <artifactId>langchain4j-open-ai-spring-boot-starter</artifactId>
  <version>${langchain4j.version}</version>
</dependency>

<!-- pgvector embedding store -->
<dependency>
  <groupId>dev.langchain4j</groupId>
  <artifactId>langchain4j-pgvector</artifactId>
  <version>${langchain4j.version}</version>
</dependency>

<!-- Apache Tika: auto-detects and parses PDF, Word, HTML, etc. -->
<dependency>
  <groupId>dev.langchain4j</groupId>
  <artifactId>langchain4j-document-parser-apache-tika</artifactId>
  <version>${langchain4j.version}</version>
</dependency>
```

> Check current version at Maven Central: `dev.langchain4j:langchain4j-spring-boot-starter`.

## Three RAG Flavors

### Flavor 1 — Easy RAG (prototype / proof-of-concept)

Minimal setup, uses built-in defaults (bge-small-en-v1.5 offline model, Tika parser, in-memory store):

```java
// Load all documents from a directory
List<Document> documents = FileSystemDocumentLoader.loadDocumentsRecursively("/data/docs");

InMemoryEmbeddingStore<TextSegment> store = new InMemoryEmbeddingStore<>();
EmbeddingStoreIngestor.ingest(documents, store);

@AiService
public interface EasyAssistant {
  String chat(String userMessage);
}

// Auto-wired ContentRetriever from the store above
```

Easy RAG has lower quality than tailored setups — use only for quick POCs.

### Flavor 2 — Naive RAG (OpenAI embeddings + pgvector)

```java
@Bean
ContentRetriever contentRetriever(EmbeddingStore<TextSegment> store,
                                  EmbeddingModel embeddingModel) {
  return EmbeddingStoreContentRetriever.builder()
      .embeddingStore(store)
      .embeddingModel(embeddingModel)
      .maxResults(5)
      .minScore(0.75)
      .build();
}

@AiService(contentRetriever = ContentRetriever.class)
public interface NaiveRagAssistant {
  @SystemMessage("Answer using only the provided context. " +
                 "If the context lacks the answer, say 'No encontré información.'")
  String answer(@MemoryId String userId, @UserMessage String question);
}
```

### Flavor 3 — Advanced RAG (full pipeline control)

Uses `DefaultRetrievalAugmentor` with pluggable components for each stage:

```java
@Bean
RetrievalAugmentor retrievalAugmentor(EmbeddingStore<TextSegment> store,
                                      EmbeddingModel embeddingModel,
                                      ChatModel chatModel) {
  ContentRetriever retriever = EmbeddingStoreContentRetriever.builder()
      .embeddingStore(store)
      .embeddingModel(embeddingModel)
      .maxResults(5)
      .minScore(0.70)
      .build();

  return DefaultRetrievalAugmentor.builder()
      .queryTransformer(new CompressingQueryTransformer(chatModel))
      .contentRetriever(retriever)
      .build();
}

@AiService(retrievalAugmentor = RetrievalAugmentor.class)
public interface AdvancedRagAssistant {
  @SystemMessage("Answer using only the provided context.")
  Result<String> answer(@MemoryId String userId, @UserMessage String question);
}
```

## Document Loading

```java
// Single file
Document doc = FileSystemDocumentLoader.loadDocument("/docs/manual.pdf",
    new ApacheTikaDocumentParser());

// All files in a directory
List<Document> docs = FileSystemDocumentLoader.loadDocuments("/docs",
    new ApacheTikaDocumentParser());

// Recursive
List<Document> all = FileSystemDocumentLoader.loadDocumentsRecursively("/docs",
    new ApacheTikaDocumentParser());

// Filtered by extension
PathMatcher matcher = FileSystems.getDefault().getPathMatcher("glob:*.pdf");
List<Document> pdfs = FileSystemDocumentLoader.loadDocuments("/docs", matcher,
    new ApacheTikaDocumentParser());

// From URL (web scraping)
Document web = UrlDocumentLoader.load("https://docs.example.com/api",
    new TextDocumentParser());

// From classpath (unit tests)
Document resource = ClassPathDocumentLoader.loadDocument("test-docs/sample.pdf",
    new ApacheTikaDocumentParser());
```

Available parsers: `TextDocumentParser`, `ApachePdfBoxDocumentParser`, `ApachePoiDocumentParser` (Word/Excel), `ApacheTikaDocumentParser` (auto-detect), `MarkdownDocumentParser`.

## Document Metadata

Metadata travels with the document through the pipeline and is stored in the vector store, enabling filtered retrieval:

```java
Document doc = Document.from(content, Metadata.from(Map.of(
    "source",    "resoluciones/2026",
    "tipo",      "resolucion",
    "userId",    "12345",
    "fecha",     "2026-01-15"
)));
```

Metadata types supported: `String`, `Integer`, `Long`, `Float`, `Double`, `UUID`.

## Document Ingestion Pipeline

```java
@Service
public class DocumentIngestionService {

  private final EmbeddingModel embeddingModel;
  private final EmbeddingStore<TextSegment> embeddingStore;

  public IngestionResult ingest(Path filePath, String userId) {
    Document document = FileSystemDocumentLoader.loadDocument(filePath,
        new ApacheTikaDocumentParser());

    return EmbeddingStoreIngestor.builder()
        // 1. Enrich document metadata before splitting
        .documentTransformer(doc -> {
          doc.metadata().put("userId", userId);
          doc.metadata().put("fileName", filePath.getFileName().toString());
          return doc;
        })
        // 2. Split into 500-token chunks with 50-token overlap
        .documentSplitter(DocumentSplitters.recursive(500, 50,
            new OpenAiTokenCountEstimator("gpt-4o-mini")))
        // 3. Prepend file name to each segment for better retrieval context
        .textSegmentTransformer(seg -> TextSegment.from(
            seg.metadata().getString("fileName") + "\n" + seg.text(),
            seg.metadata()))
        // 4. Embed and store
        .embeddingModel(embeddingModel)
        .embeddingStore(embeddingStore)
        .build()
        .ingest(document);
  }
}
```

For large batches use `@Async` to avoid blocking the request thread.

## pgvector Setup

```java
@Configuration
class VectorStoreConfig {

  @Bean
  EmbeddingStore<TextSegment> embeddingStore(DataSource dataSource) {
    return PgVectorEmbeddingStore.builder()
        .datasource(dataSource)
        .table("document_embeddings")
        .dimension(1536)           // text-embedding-3-small
        .createTable(true)         // creates table on first startup if absent
        .build();
  }
}
```

`dimension` must match the embedding model:
- `text-embedding-3-small` → 1536
- `text-embedding-3-large` → 3072
- `text-embedding-ada-002` → 1536

The `createTable(true)` option is safe but disable in production after the first deploy to avoid schema races.

## EmbeddingStoreContentRetriever — Filtering

```java
ContentRetriever userScopedRetriever = EmbeddingStoreContentRetriever.builder()
    .embeddingStore(store)
    .embeddingModel(embeddingModel)
    .maxResults(5)
    .minScore(0.75)
    // Static filter (same for all calls)
    .filter(metadataKey("tipo").isEqualTo("resolucion"))
    // Dynamic filter (computed per query)
    .dynamicFilter(query -> {
      String userId = query.metadata().invocationParameters().get("userId");
      return metadataKey("userId").isEqualTo(userId);
    })
    // Dynamic maxResults (computed per query)
    .dynamicMaxResults(query -> query.text().length() > 200 ? 8 : 4)
    .build();
```

Filter operations: `IsEqualTo`, `IsNotEqualTo`, `IsGreaterThan`, `IsLessThan`, `IsIn`, `IsNotIn`, `ContainsString`, `And`, `Or`, `Not`.

## Query Transformation (Advanced RAG)

### CompressingQueryTransformer

Rewrites conversational follow-up questions into standalone queries:

```
User: "Cuéntame sobre Juan Pérez"
AI: "Juan Pérez fue..."
User: "¿Dónde vivía?" → compressed to: "¿Dónde vivía Juan Pérez?"
```

```java
QueryTransformer compressor = new CompressingQueryTransformer(chatModel);

DefaultRetrievalAugmentor.builder()
    .queryTransformer(compressor)
    .contentRetriever(retriever)
    .build();
```

### ExpandingQueryTransformer

Generates multiple reformulations to broaden retrieval coverage:

```java
QueryTransformer expander = new ExpandingQueryTransformer(chatModel);
```

## Query Routing

Route to different retrievers based on query content:

```java
// Manual routing: all retrievers receive every query
DefaultRetrievalAugmentor.builder()
    .contentRetriever(List.of(expedienteRetriever, resolucionRetriever))
    .build();

// Smart routing: LLM decides which retriever to use
Map<ContentRetriever, String> descriptions = Map.of(
    expedienteRetriever, "Información sobre expedientes electorales",
    resolucionRetriever, "Resoluciones y normativa del JNE"
);

QueryRouter router = new LanguageModelQueryRouter(chatModel, descriptions);

DefaultRetrievalAugmentor.builder()
    .queryRouter(router)
    .build();
```

## Re-Ranking Results

Score and re-rank retrieved segments with a dedicated scoring model (Cohere):

```java
ScoringModel scoringModel = CohereScoringModel.builder()
    .apiKey(System.getenv("COHERE_API_KEY"))
    .modelName("rerank-multilingual-v3.0")
    .build();

ContentAggregator reranker = ReRankingContentAggregator.builder()
    .scoringModel(scoringModel)
    .maxResults(3)       // keep top 3 after re-ranking
    .minScore(0.4)
    .build();

DefaultRetrievalAugmentor.builder()
    .queryTransformer(new CompressingQueryTransformer(chatModel))
    .contentRetriever(retriever)
    .contentAggregator(reranker)
    .build();
```

## Custom Content Injection Prompt

Control how retrieved content is inserted into the user message:

```java
ContentInjector injector = DefaultContentInjector.builder()
    .promptTemplate(PromptTemplate.from(
        "{{userMessage}}\n\nUsa el siguiente contexto para responder:\n{{contents}}"))
    .metadataKeysToInclude(List.of("source", "fecha"))
    .build();

DefaultRetrievalAugmentor.builder()
    .contentRetriever(retriever)
    .contentInjector(injector)
    .build();
```

## Web Search Retriever

```java
WebSearchEngine google = GoogleCustomWebSearchEngine.builder()
    .apiKey(System.getenv("GOOGLE_API_KEY"))
    .csi(System.getenv("GOOGLE_SEARCH_ENGINE_ID"))
    .build();

ContentRetriever webRetriever = WebSearchContentRetriever.builder()
    .webSearchEngine(google)
    .maxResults(3)
    .build();
```

## Controlling Chat Memory + RAG Interaction

By default, the augmented message (with injected context) is stored in chat memory, growing it quickly. To store only the original question:

```java
Assistant assistant = AiServices.builder(Assistant.class)
    .chatModel(chatModel)
    .chatMemory(chatMemory)
    .retrievalAugmentor(retrievalAugmentor)
    .storeRetrievedContentInChatMemory(false)   // store original, not augmented
    .build();
```

## Accessing Retrieved Sources

### From `Result<T>`

```java
@AiService
public interface SourcedAssistant {
  Result<String> answer(String question);
}

Result<String> result = assistant.answer("¿Cuál es el plazo de apelación?");
String answer = result.content();
result.sources().forEach(content -> {
  TextSegment segment = content.textSegment();
  log.info("source={} text={}", segment.metadata().getString("source"), segment.text());
});
```

### From `TokenStream` (streaming)

```java
assistant.stream("¿Cuál es el plazo?")
    .onRetrieved(sources -> sendSourcesHeader(sources))
    .onPartialResponse(token -> sendToken(token))
    .onCompleteResponse(resp -> sendDone())
    .start();
```

## Embedding Store Operations

```java
// Add single embedding with segment
String id = embeddingStore.add(embedding, textSegment);

// Batch add (preferred for ingestion)
embeddingStore.addAll(embeddings, textSegments);

// Search
EmbeddingSearchRequest request = EmbeddingSearchRequest.builder()
    .queryEmbedding(queryEmbedding)
    .maxResults(5)
    .minScore(0.75)
    .filter(metadataKey("userId").isEqualTo("12345"))
    .build();
List<EmbeddingMatch<TextSegment>> matches = embeddingStore.search(request).matches();

// Delete
embeddingStore.remove(id);
embeddingStore.removeAll(metadataKey("userId").isEqualTo("12345"));
embeddingStore.removeAll(); // clear entire store
```

## Production Defaults

- Tune `maxResults` and `minScore` for your domain — too low a score lets noise in, too high misses valid content
- Keep chunk size 300–700 tokens; overlap 50–100 tokens — test with your actual documents
- Prepend document title or section name to each chunk via `textSegmentTransformer` — significantly improves retrieval quality
- Use `CompressingQueryTransformer` whenever chat memory is active — follow-up questions without context compression retrieve poorly
- Add metadata (`source`, `fecha`, `tipo`) to all documents — enables filtering and lets the LLM cite sources
- Disable `createTable(true)` in pgvector after the first production deploy
- Run ingestion with `@Async` for batches; track `IngestionResult` to log token usage
- For multilingual content use `text-embedding-3-large` or a multilingual model (e.g., Cohere `embed-multilingual-v3.0`)
- Add an `EmbeddingStoreListener` to track retrieval latency via Micrometer

**Remember**: RAG quality depends on data quality first, then chunking strategy, then retrieval parameters. Measure precision/recall on a golden test set before tuning hyperparameters.
