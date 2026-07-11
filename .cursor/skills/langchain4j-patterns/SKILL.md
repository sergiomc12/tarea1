---
name: langchain4j-patterns
description: LangChain4j core patterns with Spring Boot — AI Services, chat models, chat memory, streaming, structured outputs, classification, guardrails, and observability. Use when building Java AI backends. For RAG pipelines see langchain4j-rag. For tool calling see langchain4j-tools.
metadata:
  origin: sergiomc12-fork
---

# LangChain4j Core Patterns + Spring Boot

Production patterns for building AI-powered backends. This skill covers the core layer.
See [[langchain4j-rag]] for RAG pipelines and [[langchain4j-tools]] for tool/function calling.

## When to Activate

- Integrating an LLM (OpenAI, Azure OpenAI) into a Spring Boot service
- Defining `@AiService` interfaces with system prompts and memory
- Configuring streaming responses (SSE, WebFlux Flux)
- Extracting structured data from LLM responses
- Classifying text (sentiment, category, intent)
- Adding input/output guardrails
- Setting up Micrometer metrics for token usage

## Dependencies (Maven)

```xml
<!-- Spring Boot 3 (Java 17+) -->
<dependency>
  <groupId>dev.langchain4j</groupId>
  <artifactId>langchain4j-spring-boot-starter</artifactId>
  <version>${langchain4j.version}</version>
</dependency>

<!-- OpenAI provider (chat + embeddings) -->
<dependency>
  <groupId>dev.langchain4j</groupId>
  <artifactId>langchain4j-open-ai-spring-boot-starter</artifactId>
  <version>${langchain4j.version}</version>
</dependency>

<!-- Azure OpenAI provider (use instead of the above on Azure) -->
<!-- <dependency>
  <groupId>dev.langchain4j</groupId>
  <artifactId>langchain4j-azure-open-ai-spring-boot-starter</artifactId>
  <version>${langchain4j.version}</version>
</dependency> -->

<!-- Reactor for Flux<String> streaming -->
<dependency>
  <groupId>dev.langchain4j</groupId>
  <artifactId>langchain4j-reactor</artifactId>
  <version>${langchain4j.version}</version>
</dependency>

<!-- Micrometer metrics for token usage -->
<dependency>
  <groupId>dev.langchain4j</groupId>
  <artifactId>langchain4j-micrometer-metrics</artifactId>
  <version>${langchain4j.version}</version>
</dependency>

<!-- Guardrails testing utilities -->
<dependency>
  <groupId>dev.langchain4j</groupId>
  <artifactId>langchain4j-test</artifactId>
  <version>${langchain4j.version}</version>
  <scope>test</scope>
</dependency>
```

> Check current version at Maven Central: `dev.langchain4j:langchain4j-spring-boot-starter`.
> Spring Boot 4 uses `-spring-boot4-starter` suffix instead.

## Spring Boot Auto-Configuration

Properties in `application.yml` — no `@Bean` definitions needed for common cases:

```yaml
langchain4j:
  open-ai:
    chat-model:
      api-key: ${OPENAI_API_KEY}
      model-name: gpt-4o
      temperature: 0.7
      max-tokens: 2048
      log-requests: true
      log-responses: true
    streaming-chat-model:
      api-key: ${OPENAI_API_KEY}
      model-name: gpt-4o
    embedding-model:
      api-key: ${OPENAI_API_KEY}
      model-name: text-embedding-3-small

# Azure OpenAI equivalent:
# langchain4j:
#   azure-open-ai:
#     chat-model:
#       endpoint: ${AZURE_OPENAI_ENDPOINT}
#       api-key: ${AZURE_OPENAI_API_KEY}
#       deployment-name: gpt-4o
#     embedding-model:
#       endpoint: ${AZURE_OPENAI_ENDPOINT}
#       api-key: ${AZURE_OPENAI_API_KEY}
#       deployment-name: text-embedding-3-small
```

NEVER hardcode API keys. Always read from environment variables or a secrets manager.

Auto-wired into `@AiService` beans automatically:
- `ChatModel`, `StreamingChatModel`
- `ChatMemory` / `ChatMemoryProvider`
- `ContentRetriever` / `RetrievalAugmentor`
- `@Tool`-annotated methods from `@Component`/`@Service` beans
- `ToolProvider`

## Chat Models — Message Types

```java
// Low-level API (use AI Services for higher-level work)
ChatModel model = ...; // auto-injected by Spring Boot

// Single string shorthand
String reply = model.chat("Hello");

// Typed messages
UserMessage user = UserMessage.from("What is the capital of France?");
SystemMessage system = SystemMessage.from("You are a geography expert.");
ChatResponse response = model.chat(system, user);

AiMessage ai = response.aiMessage();
TokenUsage usage = response.metadata().tokenUsage();  // for cost tracking
FinishReason reason = response.metadata().finishReason();
```

Message types: `UserMessage`, `AiMessage`, `SystemMessage`, `ToolExecutionResultMessage`.

Multimodal content within `UserMessage`:

```java
// Image from URL
UserMessage msg = UserMessage.from(
    TextContent.from("Describe this image:"),
    ImageContent.from("https://example.com/chart.png")
);

// Image from bytes (base64)
byte[] bytes = Files.readAllBytes(Path.of("/tmp/chart.png"));
String b64 = Base64.getEncoder().encodeToString(bytes);
ImageContent img = ImageContent.from(b64, "image/png");

// Other content types: AudioContent, VideoContent, PdfFileContent
```

## AI Services — Core Abstraction

Declare an interface; Spring Boot generates the proxy bean automatically:

```java
@AiService
public interface DocumentAssistant {

  @SystemMessage("You are a helpful assistant that answers questions based on documents. " +
                 "If you cannot find the answer in the context, say so clearly.")
  String answer(@UserMessage String question);
}
```

Inject and use as any Spring bean:

```java
@RestController
@RequestMapping("/api/assistant")
class AssistantController {
  private final DocumentAssistant assistant;

  AssistantController(DocumentAssistant assistant) {
    this.assistant = assistant;
  }

  @PostMapping("/ask")
  ResponseEntity<AskResponse> ask(@Valid @RequestBody AskRequest req) {
    return ResponseEntity.ok(new AskResponse(assistant.answer(req.question())));
  }
}
```

### @AiService Annotations

| Annotation | Purpose |
|---|---|
| `@SystemMessage` | System prompt — string literal or classpath resource |
| `@UserMessage` | User prompt template with `{{variable}}` placeholders |
| `@V("name")` | Binds method parameter to a named template variable |
| `@MemoryId` | Partitions chat memory per user/session |
| `@Tool` | On a separate `@Component`, marks methods the LLM can call |

```java
@AiService
public interface TranslationService {

  @SystemMessage("You are a professional translator.")
  @UserMessage("Translate the following text to {{language}}: {{text}}")
  String translate(@V("text") String text, @V("language") String language);
}
```

### Result<T> — Access Token Usage and Sources

```java
@AiService
public interface ResearchAssistant {
  Result<String> research(String topic);
}

Result<String> result = assistant.research("quantum computing");
String answer         = result.content();
TokenUsage usage      = result.tokenUsage();        // input/output tokens
List<Content> sources = result.sources();           // RAG sources (if RAG enabled)
List<ToolExecution> tools = result.toolExecutions(); // tool calls made
FinishReason reason   = result.finishReason();
```

### Dynamic System Message

```java
// Per-user system message resolved at call time
Assistant assistant = AiServices.builder(Assistant.class)
    .chatModel(model)
    .systemMessageProvider(memoryId -> "You are serving user " + memoryId + ". Be concise.")
    .build();
```

### Multiple Models — Explicit Wiring

When you have more than one `ChatModel` bean, use explicit wiring:

```java
@AiService(wiringMode = EXPLICIT, chatModel = "azureOpenAiChatModel")
public interface AzureAssistant {
  String chat(String message);
}
```

### AI Service Composition

Break complex logic into specialized services and chain them:

```java
@AiService
interface GreetingDetector {
  @UserMessage("Is this a greeting? Answer only true or false: {{it}}")
  boolean isGreeting(String text);
}

@AiService
interface SupportBot {
  @SystemMessage("You are a customer support agent.")
  String reply(String message);
}

@Service
class Router {
  private final GreetingDetector greetingDetector;
  private final SupportBot supportBot;

  public String handle(String message) {
    return greetingDetector.isGreeting(message)
        ? "Hello! How can I help you today?"
        : supportBot.reply(message);
  }
}
```

Benefits: cheaper model for simple tasks, isolated testing, separate temperature tuning.

### Per-Call Parameters

```java
@AiService
interface AssistantWithParams {
  String chat(@UserMessage String msg, ChatRequestParameters params);
}

ChatRequestParameters creative = ChatRequestParameters.builder()
    .temperature(0.95)
    .maxOutputTokens(4096)
    .build();

String poem = assistant.chat("Write a poem about spring", creative);
```

## Chat Memory

### MessageWindowChatMemory (last N messages)

```java
@Configuration
class AiConfig {

  @Bean
  ChatMemoryProvider chatMemoryProvider() {
    return memoryId -> MessageWindowChatMemory.builder()
        .id(memoryId)
        .maxMessages(20)
        .build();
  }
}

@AiService
public interface ChatAssistant {
  @SystemMessage("You are a friendly support agent.")
  String chat(@MemoryId String userId, @UserMessage String message);
}
```

Use the authenticated user's ID as `@MemoryId` — never accept it from untrusted client input.

### TokenWindowChatMemory (last N tokens — more precise)

```java
@Bean
ChatMemoryProvider chatMemoryProvider(ChatModel chatModel) {
  return memoryId -> TokenWindowChatMemory.builder()
      .id(memoryId)
      .maxTokens(4000, new OpenAiTokenCountEstimator(chatModel))
      .build();
}
```

### Persistent Chat Memory (database-backed)

```java
@Component
public class RedisChatMemoryStore implements ChatMemoryStore {

  private final RedisTemplate<String, String> redis;

  @Override
  public List<ChatMessage> getMessages(Object memoryId) {
    String json = redis.opsForValue().get("chat:" + memoryId);
    return json == null ? List.of() : ChatMessageDeserializer.messagesFromJson(json);
  }

  @Override
  public void updateMessages(Object memoryId, List<ChatMessage> messages) {
    redis.opsForValue().set("chat:" + memoryId, ChatMessageSerializer.messagesToJson(messages));
  }

  @Override
  public void deleteMessages(Object memoryId) {
    redis.delete("chat:" + memoryId);
  }
}

@Bean
ChatMemoryProvider chatMemoryProvider(RedisChatMemoryStore store) {
  return memoryId -> MessageWindowChatMemory.builder()
      .id(memoryId)
      .maxMessages(20)
      .chatMemoryStore(store)
      .build();
}
```

### Evicting Conversation History

```java
@AiService
public interface ChatAssistant extends ChatMemoryAccess {
  String chat(@MemoryId String userId, @UserMessage String message);
}

// In a session cleanup job:
assistant.evictChatMemory(userId);
List<ChatMessage> history = assistant.getChatMemory(userId).messages();
```

## Response Streaming

### Via AI Service (Flux — recommended for Spring WebFlux)

```java
@AiService
public interface StreamingAssistant {
  @SystemMessage("You are a concise assistant.")
  Flux<String> chat(@MemoryId String userId, @UserMessage String message);
}

@GetMapping(value = "/api/assistant/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
Flux<String> stream(@RequestParam String question, Principal principal) {
  return streamingAssistant.chat(principal.getName(), question);
}
```

### Via AI Service (TokenStream — for callbacks)

```java
@AiService
public interface CallbackAssistant {
  TokenStream stream(@UserMessage String message);
}

TokenStream ts = assistant.stream("Tell me a joke");
ts
  .onPartialResponse(token -> sendToWebSocket(token))
  .onCompleteResponse(response -> log.info("Done: {}", response))
  .onError(err -> log.error("Stream error", err))
  .start();
```

### Streaming with Cancellation

```java
ts.onPartialResponseWithContext((token, ctx) -> {
  sendToWebSocket(token);
  if (shouldCancel()) ctx.streamingHandle().cancel();
}).start();
```

### Low-Level Streaming (StreamingChatModel)

```java
// Compact lambda variant
import static dev.langchain4j.model.LambdaStreamingResponseHandler.onPartialResponse;
model.chat("Tell me a joke", onPartialResponse(System.out::print));

// Full handler with tool call visibility
model.chat(request, new StreamingChatResponseHandler() {
  @Override public void onPartialResponse(String token) { /* ... */ }
  @Override public void onPartialToolCall(PartialToolCall call) { /* ... */ }
  @Override public void onCompleteToolCall(CompleteToolCall call) { /* ... */ }
  @Override public void onCompleteResponse(ChatResponse r) { /* ... */ }
  @Override public void onError(Throwable e) { /* ... */ }
});
```

## Structured Output

Extract typed Java records/classes from LLM responses:

```java
@Description("A classified expediente")
public record ExpedienteClassification(
    @Description("Primary category: APELACION, TACHA, RENUNCIA, OTRO")
    String categoria,
    @Description("Confidence score 0.0 to 1.0")
    double confianza,
    @Description("One-sentence summary")
    String resumen
) {}

@AiService
public interface ExpedienteClassifier {
  @UserMessage("Classify the following expediente document: {{it}}")
  ExpedienteClassification classify(String document);
}
```

Enable JSON Schema mode in OpenAI (most reliable):

```yaml
langchain4j:
  open-ai:
    chat-model:
      supported-capabilities: RESPONSE_FORMAT_JSON_SCHEMA
      strict-json-schema: true
```

Return type support with JSON Schema:

| Return Type | JSON Schema | Prompting fallback |
|---|---|---|
| POJO / record | ✅ | ✅ |
| `List<POJO>` | ✅ | ❌ |
| `Enum` | ✅ | ✅ |
| `List<String>` | ✅ | ✅ |
| Sealed interface (polymorphic) | ✅ | ❌ |
| `boolean` / `int` / `double` | ✅ | ✅ |

## Classification

### LLM-Based Classification (for nuanced reasoning)

```java
public enum Sentimiento { POSITIVO, NEUTRO, NEGATIVO }

@AiService
public interface AnalizadorSentimiento {

  @UserMessage("Analiza el sentimiento del siguiente texto: {{it}}")
  Sentimiento analizar(String texto);

  @UserMessage("¿El siguiente texto tiene sentimiento positivo? {{it}}")
  boolean esPositivo(String texto);
}
```

### Embedding-Based Classification (for speed and cost)

```java
EmbeddingModel embeddingModel = new AllMiniLmL6V2QuantizedEmbeddingModel(); // offline, no API key

Map<Sentimiento, List<String>> ejemplos = Map.of(
    Sentimiento.POSITIVO, List.of("Excelente servicio", "Muy conforme", "Recomendado"),
    Sentimiento.NEUTRO,   List.of("Regular", "Cumple con lo esperado"),
    Sentimiento.NEGATIVO, List.of("Pésimo", "Muy mal servicio", "No recomiendo")
);

TextClassifier<Sentimiento> classifier = new EmbeddingModelTextClassifier<>(embeddingModel, ejemplos);
List<Sentimiento> results = classifier.classify("Quedé muy satisfecho con la atención");
```

Use embedding-based when you have labeled examples and need fast, cheap classification at scale.

## Guardrails — Input/Output Validation

### Input Guardrail

```java
@Component
public class AntiInjectionGuardrail implements InputGuardrail {

  @Override
  public InputGuardrailResult validate(UserMessage userMessage) {
    String text = userMessage.singleText();
    if (text.toLowerCase().contains("ignore previous instructions")) {
      return fatal("Prompt injection attempt detected");
    }
    if (text.length() > 2000) {
      return failure("Input too long — max 2000 characters");
    }
    return success();
  }
}

@AiService
@InputGuardrails(AntiInjectionGuardrail.class)
public interface SecureAssistant {
  String chat(String message);
}
```

Outcomes: `success()`, `successWith(rewritten)`, `failure(msg)` (continues chain), `fatal(msg)` (halts immediately).

### Output Guardrail with Retry

```java
@Component
public class JsonFormatGuardrail implements OutputGuardrail {

  @Override
  public OutputGuardrailResult validate(AiMessage response) {
    try {
      new ObjectMapper().readTree(response.text());
      return success();
    } catch (Exception e) {
      return reprompt(
          "Invalid JSON response: " + e.getMessage(),
          "Please respond with valid JSON only, no markdown or explanation."
      );
    }
  }
}

@AiService
@OutputGuardrails(value = JsonFormatGuardrail.class, maxRetries = 3)
public interface JsonAssistant {
  String extractJson(String document);
}
```

Outcomes: `success()`, `successWith(rewritten)`, `failure(msg)`, `fatal(msg)`, `retry(msg)`, `reprompt(reason, newPrompt)`.

### Built-in Moderation Guardrail

```java
@AiService
@InputGuardrails(MessageModeratorInputGuardrail.class)
public interface ModeratedAssistant {
  String chat(String message);
}
```

Requires a `ModerationModel` bean (e.g., `OpenAiModerationModel`).

### Guardrails in Builder Mode

```java
Assistant assistant = AiServices.builder(Assistant.class)
    .chatModel(model)
    .inputGuardrailClasses(AntiInjectionGuardrail.class, LengthGuardrail.class)
    .outputGuardrails(new JsonFormatGuardrail())
    .build();
```

## Observability

### ChatModelListener (requests, responses, errors)

```java
@Bean
ChatModelListener aiAuditListener() {
  return new ChatModelListener() {
    @Override
    public void onRequest(ChatModelRequestContext ctx) {
      ctx.attributes().put("startMs", System.currentTimeMillis());
      log.info("ai_request model={} messages={}", ctx.chatRequest().parameters().modelName(),
          ctx.chatRequest().messages().size());
    }

    @Override
    public void onResponse(ChatModelResponseContext ctx) {
      long ms = System.currentTimeMillis() - (long) ctx.attributes().get("startMs");
      TokenUsage usage = ctx.chatResponse().metadata().tokenUsage();
      log.info("ai_response durationMs={} inputTokens={} outputTokens={}",
          ms, usage.inputTokenCount(), usage.outputTokenCount());
    }

    @Override
    public void onError(ChatModelErrorContext ctx) {
      log.error("ai_error", ctx.error());
    }
  };
}
```

Listeners are synchronous and run in the calling thread. Multiple listeners are composable.

### Micrometer Token Usage Metrics

```java
@Bean
MicrometerMetricsChatModelListener micrometerListener(MeterRegistry meterRegistry) {
  return new MicrometerMetricsChatModelListener(meterRegistry);
}
```

Exposes `gen_ai.client.token.usage` histogram with tags:
- `gen_ai.operation.name` → "chat"
- `gen_ai.provider.name` → "openai" / "azure.ai.inference"
- `gen_ai.request.model` → "gpt-4o"
- `gen_ai.token.type` → "input" / "output"

Enable in `application.yml`:

```yaml
management:
  endpoints:
    web:
      exposure:
        include: metrics
```

Query: `GET /actuator/metrics/gen_ai.client.token.usage`

### AI Service Event Listeners

```java
@Bean
AiServiceCompletedListener completionAudit() {
  return event -> {
    InvocationContext ctx = event.invocationContext();
    log.info("ai_service_completed interface={} method={} invocationId={}",
        ctx.interfaceName(), ctx.methodName(), ctx.invocationId());
  };
}
```

Available events: `AiServiceStartedEvent`, `AiServiceRequestIssuedEvent`, `AiServiceResponseReceivedEvent`, `AiServiceCompletedEvent`, `AiServiceErrorEvent`, `ToolExecutedEvent`, `InputGuardrailExecutedEvent`, `OutputGuardrailExecutedEvent`.

## Production Defaults

- Java 17 minimum; Spring Boot 3.5+ for the `-spring-boot-starter` suffix
- Set `langchain4j.open-ai.chat-model.timeout` (default 60s) — tune per endpoint's SLA
- Add a Resilience4j circuit breaker around AI endpoints — LLM APIs are external and can timeout under load
- Rate-limit AI endpoints independently — LLM calls cost tokens and are slow
- Never expose `@MemoryId` values from client request params — derive them from the authenticated principal
- Use `Result<T>` to log `tokenUsage()` per request for cost tracking
- Enable `log-requests: true` and `log-responses: true` only in non-production environments (contains PII)
- Prefer constructor injection on `@AiService`-consuming controllers; avoids circular dependency issues
- For deterministic tasks (classification, extraction) use `temperature: 0` to reduce variance

**Remember**: AI Services are Spring beans — apply the same architecture as any service layer: thin controllers, AI logic in the service, tools in dedicated components. Guard all public AI endpoints with authentication and rate limiting.
