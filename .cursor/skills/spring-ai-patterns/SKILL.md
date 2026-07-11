---
name: spring-ai-patterns
description: Spring AI patterns with Spring Boot 4 — ChatClient fluent API, Advisors chain, Chat Memory (6 DB backends), Tool Calling, Structured Output, RAG (ETL + QuestionAnswerAdvisor + RetrievalAugmentationAdvisor), pgvector, Multimodality, and Observability. Use when building Java AI backends with Spring's native AI framework. Requires Spring Boot 4.0.x. For the LangChain4j alternative see langchain4j-patterns.
metadata:
  origin: sergiomc12-fork
---

# Spring AI Patterns

Spring AI is Spring's native AI framework — a first-class Spring citizen that uses the Advisor pattern, standard Spring beans, and Spring Boot auto-configuration.  
**Requires Spring Boot 4.0.x** (Spring AI 2.0.x is NOT compatible with Spring Boot 3.x).  
See [[langchain4j-patterns]] for the LangChain4j alternative.

## When to Activate

- Building an AI feature on a **Spring Boot 4** project and want idiomatic Spring integration
- Need chat memory backed by **JDBC, Redis, MongoDB, Cassandra, or Neo4j** with zero-glue setup
- Implementing RAG with a fluent builder API (no custom interface proxies needed)
- Calling tools and intercepting the tool loop at the framework level
- Measuring AI operations via Micrometer / OpenTelemetry (built-in, zero-config)

## ⚠️ Critical: Spring Boot Version Requirement

```xml
<!-- Spring AI 2.0.x requires Spring Boot 4.0.x -->
<parent>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-starter-parent</artifactId>
  <version>4.0.0</version>
</parent>

<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>org.springframework.ai</groupId>
      <artifactId>spring-ai-bom</artifactId>
      <version>2.0.0</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>
```

## Core Dependencies

```xml
<!-- ChatModel (OpenAI) -->
<dependency>
  <groupId>org.springframework.ai</groupId>
  <artifactId>spring-ai-starter-model-openai</artifactId>
</dependency>

<!-- pgvector vector store -->
<dependency>
  <groupId>org.springframework.ai</groupId>
  <artifactId>spring-ai-starter-vector-store-pgvector</artifactId>
</dependency>

<!-- PDF document reader -->
<dependency>
  <groupId>org.springframework.ai</groupId>
  <artifactId>spring-ai-pdf-document-reader</artifactId>
</dependency>

<!-- Tika: multi-format reader (PDF, DOCX, HTML, ...) -->
<dependency>
  <groupId>org.springframework.ai</groupId>
  <artifactId>spring-ai-tika-document-reader</artifactId>
</dependency>
```

Minimum `application.yml`:

```yaml
spring:
  ai:
    openai:
      api-key: ${OPENAI_API_KEY}       # never hardcode
      chat:
        options:
          model: gpt-4o
      embedding:
        options:
          model: text-embedding-3-small
```

---

## ChatClient — Fluent API (Core Abstraction)

`ChatClient` is Spring AI's central API. Unlike LangChain4j's `@AiService`, it uses a fluent builder instead of annotated interfaces.

### Basic Setup

```java
@Configuration
class AiConfig {

  @Bean
  ChatClient chatClient(ChatClient.Builder builder) {
    return builder
        .defaultSystem("Eres un asistente de gestión de expedientes electorales.")
        .build();
  }
}
```

### Calling the Model

```java
@Service
public class ExpedienteAssistant {

  private final ChatClient chatClient;

  ExpedienteAssistant(ChatClient chatClient) {
    this.chatClient = chatClient;
  }

  public String consult(String userId, String question) {
    return chatClient.prompt()
        .user(question)
        .advisors(a -> a.param(ChatMemory.CONVERSATION_ID, userId))
        .call()
        .content();
  }
}
```

### Multiple ChatClient Beans (Different Models)

```java
@Configuration
class MultiModelConfig {

  @Bean
  @Primary
  ChatClient primaryClient(ChatClient.Builder builder) {
    return builder.defaultSystem("General assistant").build();
  }

  @Bean("summaryClient")
  ChatClient summaryClient(ChatModel chatModel) {
    return ChatClient.builder(chatModel)
        .defaultSystem("You summarize documents concisely.")
        .defaultOptions(OpenAiChatOptions.builder().model("gpt-4o-mini").build())
        .build();
  }
}
```

### Prompt Templates

```java
// Inline template variables
String answer = chatClient.prompt()
    .user(u -> u.text("Analiza el expediente {numero} del año {anio}")
                .param("numero", "123-2026")
                .param("anio", "2026"))
    .call()
    .content();

// System prompt with variables
String answer2 = chatClient.prompt()
    .system(s -> s.text("Eres un experto en {dominio}")
                  .param("dominio", "derecho electoral"))
    .user("¿Cuál es el plazo de apelación?")
    .call()
    .content();
```

### Streaming Response

```java
Flux<String> stream = chatClient.prompt()
    .user(question)
    .stream()
    .content();

// With full ChatResponse
Flux<ChatResponse> responseStream = chatClient.prompt()
    .user(question)
    .stream()
    .chatResponse();
```

### Full ChatResponse (Token Usage, Metadata)

```java
ChatResponse response = chatClient.prompt()
    .user(question)
    .call()
    .chatResponse();

String content = response.getResult().getOutput().getText();
Usage usage = response.getMetadata().getUsage();
long inputTokens = usage.getPromptTokens();
long outputTokens = usage.getGenerationTokens();
```

---

## Advisors — Cross-Cutting Concern Chain

Advisors intercept `ChatClient` calls in a chain (lowest order = innermost = runs first, closest to model).

### Custom Advisor

```java
@Component
public class AuditAdvisor implements CallAdvisor {

  @Override
  public ChatClientResponse aroundCall(ChatClientRequest request, CallAdvisorChain chain) {
    log.info("[AUDIT] user={} prompt={}",
        request.context().get(ChatMemory.CONVERSATION_ID),
        request.prompt().getUserMessage());

    ChatClientResponse response = chain.nextAroundCall(request);

    log.info("[AUDIT] response={}", response.chatResponse().getResult().getOutput().getText());
    return response;
  }

  @Override
  public int getOrder() { return Ordered.HIGHEST_PRECEDENCE; }
}
```

### Built-in Advisors

| Advisor | Purpose |
|---------|---------|
| `MessageChatMemoryAdvisor` | Inject conversation history as messages |
| `VectorStoreChatMemoryAdvisor` | Store/retrieve conversation in vector store |
| `QuestionAnswerAdvisor` | Naive RAG — augment prompt with vector search results |
| `RetrievalAugmentationAdvisor` | Advanced RAG — full pipeline control |
| `ToolCallingAdvisor` | Manual tool execution loop control |
| `SafeGuardAdvisor` | Block sensitive keywords in input |
| `SimpleLoggerAdvisor` | Log request/response (dev only) |
| `ReReadingAdvisor` | Re-reading technique for complex reasoning (RE² prompting) |

### Wiring Multiple Advisors

```java
// Default advisors (applied on all calls)
ChatClient chatClient = builder
    .defaultAdvisors(
        new MessageChatMemoryAdvisor(chatMemory),
        new SimpleLoggerAdvisor()
    )
    .build();

// Per-call advisors
chatClient.prompt()
    .user(question)
    .advisors(new SafeGuardAdvisor(List.of("política", "religión")))
    .call()
    .content();
```

---

## Chat Memory

### Memory Repositories

Spring AI ships 6 repository implementations out of the box:

```java
// 1. In-memory (dev/testing only — lost on restart)
ChatMemoryRepository repo = new InMemoryChatMemoryRepository();

// 2. JDBC — PostgreSQL, MySQL, MariaDB, SQLServer, HSQLDB, Oracle
// Auto-configured when spring-ai-starter-chat-memory-repository-jdbc is present
@Bean
ChatMemoryRepository jdbcRepository(JdbcTemplate jdbc) {
  return JdbcChatMemoryRepository.builder()
      .jdbcTemplate(jdbc)
      .build();
}

// 3. Redis
@Bean
ChatMemoryRepository redisRepository(RedisTemplate<String, Object> redis) {
  return RedisChatMemoryRepository.builder()
      .redisTemplate(redis)
      .build();
}

// 4. MongoDB
@Bean
ChatMemoryRepository mongoRepository(MongoTemplate mongo) {
  return MongoDbChatMemoryRepository.builder()
      .mongoTemplate(mongo)
      .build();
}

// 5. Cassandra — supports TTL
@Bean
ChatMemoryRepository cassandraRepository(CqlSession session) {
  return CassandraChatMemoryRepository.builder()
      .cqlSession(session)
      .timeToLive(Duration.ofDays(30))
      .build();
}

// 6. Neo4j
@Bean
ChatMemoryRepository neo4jRepository(Driver driver) {
  return Neo4jChatMemoryRepository.builder()
      .driver(driver)
      .build();
}
```

### MessageWindowChatMemory (Default)

```java
@Bean
ChatMemory chatMemory(ChatMemoryRepository repository) {
  return MessageWindowChatMemory.builder()
      .chatMemoryRepository(repository)
      .maxMessages(20)
      .build();
}
```

### CRITICAL: CONVERSATION_ID Is Mandatory

```java
// WRONG — no conversation ID → NullPointerException at runtime
chatClient.prompt().user(q).call().content();

// CORRECT — always pass the conversation ID
chatClient.prompt()
    .user(q)
    .advisors(a -> a.param(ChatMemory.CONVERSATION_ID, userId))
    .call()
    .content();
```

### Full Wiring: ChatMemory + Advisor

```java
@Configuration
class MemoryConfig {

  @Bean
  ChatMemory chatMemory(ChatMemoryRepository repository) {
    return MessageWindowChatMemory.builder()
        .chatMemoryRepository(repository)
        .maxMessages(20)
        .build();
  }

  @Bean
  ChatClient chatClient(ChatClient.Builder builder, ChatMemory chatMemory) {
    return builder
        .defaultSystem("Eres un asistente de expedientes electorales.")
        .defaultAdvisors(new MessageChatMemoryAdvisor(chatMemory))
        .build();
  }
}

@Service
class ConversationalService {

  private final ChatClient chatClient;

  public String chat(String userId, String message) {
    return chatClient.prompt()
        .user(message)
        .advisors(a -> a.param(ChatMemory.CONVERSATION_ID, userId))
        .call()
        .content();
  }
}
```

---

## Tool Calling

### Defining Tools

```java
@Component
public class ExpedienteTools {

  private final ExpedienteRepository repo;

  @Tool(description = "Busca expedientes por estado: PENDIENTE, EN_REVISION, o CERRADO")
  public List<ExpedienteSummary> buscarPorEstado(
      @ToolParam(description = "Estado del expediente") String estado) {
    return repo.findSummariesByStatus(EstadoExpediente.valueOf(estado));
  }

  @Tool(description = "Obtiene el detalle completo de un expediente por ID")
  public ExpedienteDetail obtenerExpediente(
      @ToolParam(description = "ID numérico del expediente") Long id) {
    return repo.findDetailById(id)
        .orElseThrow(() -> new EntityNotFoundException("Expediente no encontrado: " + id));
  }

  @Tool(description = "Cierra un expediente. Irreversible.",
        returnDirect = true)       // skip LLM processing, return result directly to caller
  public String cerrarExpediente(Long id, String motivo) {
    repo.close(id, motivo);
    return "Expediente %d cerrado: %s".formatted(id, motivo);
  }
}
```

`@ToolParam` options: `description`, `required` (default `true`), `name`.

### Registering Tools on ChatClient

```java
// Default tools for all calls
ChatClient chatClient = builder
    .defaultTools(expedienteTools)
    .build();

// Per-call tools
String answer = chatClient.prompt()
    .user(question)
    .tools(expedienteTools, calendarTools)
    .call()
    .content();
```

### ToolContext — Passing Server-Side Data to Tools

Use `ToolContext` to pass data (user ID, tenant, roles) that the LLM should NOT control:

```java
@Tool(description = "Registers a calendar event for the current user")
public String addCalendarEvent(String title, String datetime, ToolContext context) {
  String userId = context.get("userId");  // injected by the framework
  String tenantId = context.get("tenantId");
  calendarService.add(userId, tenantId, title, datetime);
  return "Event registered: " + title;
}

// Pass context values at call time:
chatClient.prompt()
    .user(question)
    .toolContext(Map.of("userId", principal.getName(), "tenantId", tenant.getId()))
    .call()
    .content();
```

### Tool Error Handling

```java
@Bean
ToolExecutionExceptionProcessor toolErrorProcessor() {
  return (toolDefinition, exception) -> {
    if (exception instanceof EntityNotFoundException) {
      return "No se encontró el recurso solicitado.";
    }
    log.error("Tool error in {}: {}", toolDefinition.name(), exception.getMessage());
    return "Error ejecutando la herramienta. Intenta de nuevo.";
  };
}

ChatClient chatClient = builder
    .defaultOptions(OpenAiChatOptions.builder()
        .toolExecutionExceptionProcessor(toolErrorProcessor())
        .build())
    .build();
```

### Tool Search — Semantic Filtering for Large Tool Sets

When you have many tools (>15), use semantic search to show only relevant ones:

```java
@Bean
ChatClient chatClient(ChatClient.Builder builder, EmbeddingModel embeddingModel) {
  VectorToolIndex toolIndex = VectorToolIndex.builder()
      .embeddingModel(embeddingModel)
      .build();

  return builder
      .defaultOptions(OpenAiChatOptions.builder()
          .toolCallbackResolver(ToolSearchToolCallingAdvisor.builder()
              .toolIndex(toolIndex)
              .maxResults(5)
              .build())
          .build())
      .defaultTools(allMyToolBeans)
      .build();
}
```

Alternative index implementations: `LuceneToolIndex`, `RegexToolIndex`.

### User-Controlled Tool Execution Loop

By default, Spring AI executes tools automatically. To control the loop manually:

```java
ChatResponse response = chatClient.prompt()
    .user(question)
    .tools(myTools)
    .advisors(ToolCallingAdvisor.builder().build())  // disables auto-execution
    .call()
    .chatResponse();

// Check for pending tool calls
if (response.hasToolCalls()) {
  List<ToolCall> calls = response.getResult().getOutput().getToolCalls();
  // execute and feed results back manually
}
```

---

## Structured Output

Return type-safe Java objects directly from the model:

```java
// 1. Bean (POJO / record)
record ExpedienteReport(String numero, String estado, List<String> observaciones) {}

ExpedienteReport report = chatClient.prompt()
    .user("Resume el expediente 123-2026 con estado y observaciones")
    .call()
    .entity(ExpedienteReport.class);

// 2. Parameterized type
List<ExpedienteReport> reports = chatClient.prompt()
    .user("Genera 3 reportes de ejemplo")
    .call()
    .entity(new ParameterizedTypeReference<List<ExpedienteReport>>() {});

// 3. Map
Map<String, Object> raw = chatClient.prompt()
    .user("Retorna JSON con campos nombre, edad, cargo")
    .call()
    .entity(new ParameterizedTypeReference<Map<String, Object>>() {});
```

### Native Structured Output (OpenAI JSON Mode)

```java
String answer = chatClient.prompt()
    .user("Clasifica este texto en positivo, negativo o neutro: " + text)
    .advisors(a -> a.param(AdvisorParams.ENABLE_NATIVE_STRUCTURED_OUTPUT, true))
    .call()
    .content();
```

### Known Limitation

OpenAI native structured output does NOT support top-level arrays. Wrap in an object:

```java
// WRONG — fails with OpenAI native output
List<String> tags = ...entity(new ParameterizedTypeReference<List<String>>(){});

// CORRECT — wrap in record
record TagList(List<String> tags) {}
TagList result = ...entity(TagList.class);
```

---

## RAG — Retrieval-Augmented Generation

### ETL Pipeline (Document Ingestion)

```java
@Service
public class DocumentIngestionService {

  private final VectorStore vectorStore;

  public void ingest(Resource resource, String source) {
    // 1. Read
    List<Document> docs = new TikaDocumentReader(resource).read();

    // 2. Enrich metadata
    docs.forEach(d -> d.getMetadata().put("source", source));

    // 3. Split into chunks
    List<Document> chunks = new TokenTextSplitter.Builder()
        .withChunkSize(800)
        .withMinChunkSizeChars(350)
        .build()
        .apply(docs);

    // 4. Embed and store
    vectorStore.add(chunks);
  }
}
```

**Available Readers:**

| Reader | Dependency | Use |
|--------|-----------|-----|
| `TikaDocumentReader` | `spring-ai-tika-document-reader` | Auto-detect: PDF, DOCX, HTML, PPTX... |
| `PagePdfDocumentReader` | `spring-ai-pdf-document-reader` | PDF page-by-page |
| `ParagraphPdfDocumentReader` | `spring-ai-pdf-document-reader` | PDF by TOC paragraph |
| `JsonReader` | core | JSON arrays/objects |
| `TextReader` | core | Plain text |
| `JsoupDocumentReader` | `spring-ai-jsoup-document-reader` | HTML with CSS selector |
| `MarkdownDocumentReader` | `spring-ai-markdown-document-reader` | Markdown files |

**Metadata Enrichers:**

```java
// AI-generated keywords → metadata["excerpt_keywords"]
KeywordMetadataEnricher keywordEnricher =
    KeywordMetadataEnricher.builder(chatModel).keywordCount(5).build();

// AI-generated summaries → prev/current/next section
SummaryMetadataEnricher summaryEnricher =
    new SummaryMetadataEnricher(chatModel,
        List.of(SummaryType.PREVIOUS, SummaryType.CURRENT, SummaryType.NEXT));

List<Document> enriched = summaryEnricher.apply(keywordEnricher.apply(chunks));
vectorStore.add(enriched);
```

### Naive RAG — QuestionAnswerAdvisor

Quick setup, auto-injects retrieved context into the prompt:

```java
@Bean
ChatClient ragClient(ChatClient.Builder builder, VectorStore vectorStore) {
  return builder
      .defaultSystem("Responde SOLO con el contexto provisto. " +
                     "Si no hay información, dilo claramente.")
      .defaultAdvisors(
          new MessageChatMemoryAdvisor(chatMemory),
          QuestionAnswerAdvisor.builder(vectorStore)
              .searchRequest(SearchRequest.builder()
                  .topK(5)
                  .similarityThreshold(0.75)
                  .build())
              .build()
      )
      .build();
}

// Call (always include CONVERSATION_ID):
String answer = ragClient.prompt()
    .user(question)
    .advisors(a -> a.param(ChatMemory.CONVERSATION_ID, userId))
    .call()
    .content();
```

### Dynamic Metadata Filtering per Query

```java
QuestionAnswerAdvisor.builder(vectorStore)
    .searchRequest(SearchRequest.builder()
        .topK(5)
        .similarityThreshold(0.70)
        .build())
    .dynamicFilterExpression(request -> {
      // read user ID from advisor params set at call time
      String userId = (String) request.advisorParams().get("userId");
      return "userId == '" + userId + "'";
    })
    .build();

// Pass userId at call site:
chatClient.prompt()
    .user(question)
    .advisors(a -> a
        .param(ChatMemory.CONVERSATION_ID, userId)
        .param("userId", userId))
    .call()
    .content();
```

### Advanced RAG — RetrievalAugmentationAdvisor

Full pipeline: query transformation → retrieval → augmentation:

```java
@Bean
RetrievalAugmentationAdvisor advancedRagAdvisor(VectorStore vectorStore, ChatModel chatModel) {
  return RetrievalAugmentationAdvisor.builder()
      // Compress conversational follow-ups into standalone queries
      .queryTransformer(CompressionQueryTransformer.builder()
          .chatClientBuilder(ChatClient.builder(chatModel))
          .build())
      // Optionally expand into multiple reformulations
      // .queryExpander(MultiQueryExpander.builder().chatClientBuilder(...).build())
      .documentRetriever(VectorStoreDocumentRetriever.builder()
          .vectorStore(vectorStore)
          .topK(5)
          .similarityThreshold(0.70)
          .build())
      // Contextual re-writing of user query given retrieved docs
      .queryAugmentor(ContextualQueryAugmenter.builder().build())
      .build();
}

@Bean
ChatClient advancedRagClient(ChatClient.Builder builder,
                             ChatMemory chatMemory,
                             RetrievalAugmentationAdvisor ragAdvisor) {
  return builder
      .defaultSystem("Responde usando el contexto recuperado.")
      .defaultAdvisors(
          new MessageChatMemoryAdvisor(chatMemory),
          ragAdvisor
      )
      .build();
}
```

**Query Transformers:**

| Class | Purpose |
|-------|---------|
| `CompressionQueryTransformer` | Condense follow-ups into standalone question |
| `RewriteQueryTransformer` | Rephrase for better retrieval |
| `TranslationQueryTransformer` | Translate query to match document language |
| `MultiQueryExpander` | Generate N reformulations → broader coverage |

---

## pgvector Setup

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/postgres
    username: ${DB_USER}
    password: ${DB_PASSWORD}
  ai:
    vectorstore:
      pgvector:
        index-type: HNSW
        distance-type: COSINE_DISTANCE
        dimensions: 1536
        initialize-schema: true       # runs CREATE TABLE/INDEX on startup
        schema-name: public
        table-name: vector_store
        max-document-batch-size: 10000
```

Required PostgreSQL extensions (run once):

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS hstore;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

Manual bean (when auto-config is insufficient):

```java
@Bean
VectorStore pgVectorStore(JdbcTemplate jdbcTemplate, EmbeddingModel embeddingModel) {
  return PgVectorStore.builder(jdbcTemplate, embeddingModel)
      .dimensions(1536)
      .distanceType(PgVectorStore.PgDistanceType.COSINE_DISTANCE)
      .indexType(PgVectorStore.PgIndexType.HNSW)
      .initializeSchema(true)
      .vectorTableName("document_embeddings")
      .build();
}
```

### Similarity Search with Filter

```java
// Text expression filter
List<Document> results = vectorStore.similaritySearch(
    SearchRequest.builder()
        .query("plazo de apelación")
        .topK(5)
        .similarityThreshold(0.75)
        .filterExpression("tipo == 'resolucion' && anio >= 2024")
        .build()
);

// Programmatic DSL
FilterExpressionBuilder b = new FilterExpressionBuilder();
List<Document> results2 = vectorStore.similaritySearch(
    SearchRequest.builder()
        .query("plazo de apelación")
        .topK(5)
        .filterExpression(b.and(
            b.eq("tipo", "resolucion"),
            b.gte("anio", 2024)
        ).build())
        .build()
);
```

**Dimension reference:**
- `text-embedding-3-small` → 1536
- `text-embedding-3-large` → 3072
- `text-embedding-ada-002` → 1536

---

## Multimodality

```java
// Image analysis (resource)
ClassPathResource image = new ClassPathResource("/report-scan.png");

String analysis = chatClient.prompt()
    .user(u -> u
        .text("Extrae el número de expediente y la fecha de este documento escaneado")
        .media(MimeTypeUtils.IMAGE_PNG, image))
    .call()
    .content();

// Image from URI
String analysis2 = chatClient.prompt()
    .user(u -> u
        .text("¿Qué muestra esta imagen?")
        .media(MimeTypeUtils.IMAGE_JPEG, new URI("https://example.com/doc.jpg")))
    .call()
    .content();
```

Supported MIME types (model-dependent): `IMAGE_PNG`, `IMAGE_JPEG`, `IMAGE_GIF`, `IMAGE_WEBP`, audio formats.  
Media applies only to `UserMessage` — `AssistantMessage` is always text-only.

---

## Prompts and Templates

```java
// PromptTemplate with named variables
PromptTemplate template = new PromptTemplate(
    "Resume el expediente {numero} emitido en {fecha} con estado {estado}");

Prompt prompt = template.create(Map.of(
    "numero", "123-2026",
    "fecha", "2026-03-15",
    "estado", "EN_REVISION"));

ChatResponse response = chatModel.call(prompt);
```

---

## Observability (Micrometer / OpenTelemetry)

Spring AI emits metrics and traces automatically when Micrometer is on the classpath.  
No additional code required.

### Key Metric Names

| Component | Metric | Labels |
|-----------|--------|--------|
| ChatModel | `gen_ai.client.operation` | `gen_ai.system`, `gen_ai.request.model` |
| ChatModel tokens | `gen_ai.client.token.usage` | `gen_ai_token_type=input/output/total` |
| ChatClient | `spring.ai.chat.client` | `spring.ai.chat.client.stream` |
| Advisor | `spring.ai.advisor` | `spring.ai.advisor.name` |
| Tool | `spring.ai.tool` | `spring.ai.tool.definition.name` |
| VectorStore | `db.vector.client.operation` | `db.operation.name=add/delete/query` |
| EmbeddingModel | `gen_ai.client.operation` | `gen_ai.system` |

### Prometheus Queries

```
# Average ChatModel latency
rate(gen_ai_client_operation_seconds_sum[5m]) / rate(gen_ai_client_operation_seconds_count[5m])

# Total token usage (input tokens)
increase(gen_ai_client_token_usage_total{gen_ai_token_type="input"}[1h])

# In-flight ChatClient calls
gen_ai_chat_client_operation_active_count

# Vector store query throughput
rate(db_vector_client_operation_seconds_count{db_operation_name="query"}[5m])
```

### Observation Properties

```yaml
spring:
  ai:
    chat:
      client:
        observations:
          log-prompt: false       # NEVER true in production
          log-completion: false
      observations:
        log-prompt: false
        log-completion: false
        include-error-logging: false
    tools:
      observations:
        include-content: false    # hides tool args/results from traces
    vectorstore:
      observations:
        log-query-response: false
    image:
      observations:
        log-prompt: false
```

---

## Production Defaults

### Spring AI vs LangChain4j: Key Differences

| Concern | Spring AI | LangChain4j |
|---------|-----------|-------------|
| Min Spring Boot | 4.0.x | 3.x |
| Main API | `ChatClient` fluent | `@AiService` interface |
| Interceptors | `Advisor` chain | `ChatModelListener` |
| Memory backends | 6 built-in (JDBC/Redis/Mongo...) | Custom `ChatMemoryStore` |
| Context passing | `ToolContext` | `@MemoryId` / `InvocationParameters` |
| `returnDirect` | `@Tool(returnDirect=true)` | `ReturnBehavior.IMMEDIATE` |
| Observability | Built-in Micrometer auto-config | Manual `ChatModelListener` bean |
| RAG entry | `QuestionAnswerAdvisor` / `RetrievalAugmentationAdvisor` | `@AiService(retrievalAugmentor=...)` |

### Checklist

- `spring.ai.openai.api-key` always read from env (`${OPENAI_API_KEY}`), never hardcoded
- Always pass `ChatMemory.CONVERSATION_ID` to memory advisors — no default, NPE without it
- Set `initialize-schema: false` for pgvector after the first production deploy
- All prompt/completion/tool logging disabled by default — keep it that way
- Validate all `@Tool` parameters as untrusted input (LLM-supplied arguments)
- Use `ToolContext` for server-controlled values (userId, tenantId, roles) — never let LLM pass these
- Run document ingestion with `@Async` for large batches
- `TokenTextSplitter` default: 800 tokens, `CL100K_BASE` encoding — tune `chunkSize` and overlap per domain
- Use `similarityThreshold` (>0.70) on all vector searches to filter noise
- `QuestionAnswerAdvisor` is fastest to wire; use `RetrievalAugmentationAdvisor` when you need query rewriting or multi-step retrieval
- Emit `gen_ai.client.token.usage` to cost dashboards — multiply by model pricing for spend alerts
