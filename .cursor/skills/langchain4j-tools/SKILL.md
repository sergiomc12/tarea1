---
name: langchain4j-tools
description: LangChain4j tool calling (function calling) — @Tool, @P, @CompensateFor, dynamic ToolProvider, concurrent execution, AI-as-tool routing, error handling, return behaviors, and MCP integration. Use when the LLM needs to invoke your Spring beans. For core AI Services see langchain4j-patterns.
metadata:
  origin: sergiomc12-fork
---

# LangChain4j Tool Calling

Complete guide for exposing Spring beans as callable tools to an LLM.
See [[langchain4j-patterns]] for AI Services core and [[langchain4j-rag]] for RAG pipelines.

## When to Activate

- The LLM needs to search a database, call an API, or trigger business logic
- Implementing a multi-step agentic workflow (e.g., look up → validate → submit)
- Building compensating transactions (saga pattern) for multi-tool operations
- Routing queries between specialized AI Services (multi-agent system)
- Integrating external MCP (Model Context Protocol) servers as tools

## Core Tool Pattern

Mark a Spring bean method with `@Tool`. LangChain4j auto-generates the JSON schema and exposes it to the LLM:

```java
@Component
public class ExpedienteTools {

  private final ExpedienteRepository expedienteRepo;

  ExpedienteTools(ExpedienteRepository expedienteRepo) {
    this.expedienteRepo = expedienteRepo;
  }

  @Tool("Busca expedientes por estado. Retorna resúmenes de expedientes.")
  public List<ExpedienteSummary> buscarPorEstado(
      @P("Estado del expediente: PENDIENTE, EN_REVISION, o CERRADO") String estado) {
    return expedienteRepo.findSummariesByStatus(ExpedienteStatus.valueOf(estado));
  }

  @Tool("Obtiene el detalle completo de un expediente por su ID numérico.")
  public ExpedienteDetail obtenerExpediente(@P("ID numérico del expediente") Long id) {
    return expedienteRepo.findDetailById(id)
        .orElseThrow(() -> new EntityNotFoundException("Expediente no encontrado: " + id));
  }
}
```

Register on the AI Service:

```java
@AiService(tools = ExpedienteTools.class)
public interface ExpedienteAssistant {
  @SystemMessage("Eres un asistente de gestión de expedientes electorales. " +
                 "Usa las herramientas disponibles para responder preguntas.")
  String assist(@MemoryId String userId, @UserMessage String query);
}
```

**Security**: validate all tool inputs — arguments are supplied by the LLM and are untrusted data. Apply the same validation as a REST endpoint (`@NotBlank`, `@Size`, enum parsing with try/catch).

## @Tool — Annotation Options

```java
@Tool(
    name = "searchExpedientes",                        // override method name
    value = "Search expedientes by multiple criteria", // description seen by LLM
    returnBehavior = ReturnBehavior.TO_LLM             // default: LLM processes result
)
public List<ExpedienteSummary> search(String estado, String numero) { ... }
```

## @P — Parameter Annotation

```java
@Tool("Registers a calendar event")
public String createEvent(
    @P("Event title, e.g. 'Audiencia expediente 123-2026'") String title,
    @P("ISO 8601 datetime, e.g. '2026-07-15T14:00:00'") String datetime,
    @P(name = "durationMinutes", description = "Duration in minutes", required = false)
        Optional<Integer> duration,
    @P(defaultValue = "AUDIENCIA") EventType tipo) {
  // ...
}
```

`@P` options: `name` (override when `-parameters` javac flag missing), `description`/`value`, `required` (default `true`), `defaultValue`.

## Parameter Types Supported

- Primitives: `int`, `double`, `boolean`, `long`
- Boxed: `Integer`, `Double`, `Boolean`, `Long`, `String`
- `enum` — LLM provides the constant name
- `Optional<T>` — marks parameter as optional; prefer over `@P(required=false)` for clarity
- `List<T>`, `Set<T>`, `Map<K,V>`
- Custom POJOs / records with nested structures
- Sealed interfaces (polymorphic — no annotations needed)

```java
// Optional parameter
@Tool("Exports data optionally filtered by date range")
public byte[] exportData(String format, Optional<LocalDate> desde, Optional<LocalDate> hasta) { ... }

// Enum parameter
public enum FormatoReporte { PDF, EXCEL, CSV }

@Tool("Generates a report")
public String generateReport(@P("Report format") FormatoReporte formato) { ... }

// Sealed interface (polymorphic)
sealed interface Filtro permits FiltroFecha, FiltroEstado, FiltroUbigeo {}
record FiltroFecha(LocalDate desde, LocalDate hasta) implements Filtro {}
record FiltroEstado(String estado) implements Filtro {}

@Tool("Busca expedientes con filtro genérico")
public List<ExpedienteSummary> buscar(Filtro filtro) { ... }
```

## Default Parameter Values

```java
@Tool("Paginated search of expedientes")
public Page<ExpedienteSummary> search(
    String query,
    @P(defaultValue = "10") int pageSize,
    @P(defaultValue = "FECHA_DESC") String sortBy,
    @P(defaultValue = "[\"PENDIENTE\",\"EN_REVISION\"]") List<String> estados) {
  // When LLM omits an argument, the default is used
}
```

## Tool Return Types

```java
// String → sent as-is to LLM
@Tool String getStatus() { return "All systems operational"; }

// void → LangChain4j sends "Success" to LLM
@Tool void markAsRead(Long id) { ... }

// Any serializable type → converted to JSON
@Tool Map<String, Integer> getMetrics() { return Map.of("cpu", 45, "memory", 78); }

// Image → multimodal result
@Tool("Captures a screenshot of the current state")
Image captureScreen() {
  byte[] png = screenshot();
  return Image.builder()
      .base64Data(Base64.getEncoder().encodeToString(png))
      .mimeType("image/png")
      .build();
}

// List<Content> → text + image together
@Tool("Returns chart data with visualization")
List<Content> getChartWithImage(String metric) {
  return List.of(
      TextContent.from("Metric: " + metric + ", Value: " + getValue(metric)),
      ImageContent.from(renderChart(metric))
  );
}
```

## Return Behavior

Controls whether the LLM sees and processes the tool result, or it's returned directly to the caller:

```java
// TO_LLM (default) — LLM receives result and continues reasoning
@Tool(value = "Busca expediente", returnBehavior = ReturnBehavior.TO_LLM)
ExpedienteDetail buscar(Long id) { ... }

// IMMEDIATE — skip LLM processing; result goes straight to caller
// Use for deterministic calculations or data fetches where LLM commentary is unwanted
@Tool(value = "Calculates exact amount", returnBehavior = ReturnBehavior.IMMEDIATE)
double calculate(double base, double tasa) { return base * tasa; }

// IMMEDIATE_IF_LAST — immediate only when this is the last tool called
// Common pattern for "done" signals in agentic loops
@Tool(value = "Ends task and returns summary", returnBehavior = ReturnBehavior.IMMEDIATE_IF_LAST)
String endTask(String summary) { return summary; }
```

When `IMMEDIATE` is used, `Result<String>.content()` is `null`; the actual result is in `result.toolExecutions()`.

## Accessing Executed Tools

```java
@AiService(tools = ExpedienteTools.class)
public interface TrackedAssistant {
  Result<String> chat(String message);
}

Result<String> result = assistant.chat("Busca el expediente 123-2026");
String answer = result.content();
result.toolExecutions().forEach(exec -> {
  log.info("tool={} args={} result={}",
      exec.request().name(),
      exec.request().arguments(),
      exec.result());
});
```

## Passing Context to Tools — @ToolMemoryId and InvocationParameters

```java
// Pass the memory ID (user ID) from the AI Service down to the tool
@AiService
public interface ContextualAssistant {
  String chat(@UserMessage String message, @MemoryId String userId);
}

@Component
class CalendarTools {
  @Tool("Adds an event to the user's calendar")
  void addEvent(CalendarEvent event, @ToolMemoryId String userId) {
    calendarService.add(userId, event); // now we know WHICH user's calendar
  }
}

// Pass arbitrary extra data via InvocationParameters
@AiService
public interface AssistantWithExtra {
  String chat(@UserMessage String message, InvocationParameters parameters);
}

@Component
class TenantAwareTools {
  @Tool("Gets account balance")
  BigDecimal getBalance(String accountId, InvocationParameters params) {
    String tenantId = params.get("tenantId");
    return accountService.getBalance(tenantId, accountId);
  }
}

// Call:
InvocationParameters params = InvocationParameters.from(Map.of("tenantId", "acme-corp"));
String answer = assistant.chat("What is the balance of account 12345?", params);
```

## Compensating Transactions — @CompensateFor

Automatic rollback when a later tool fails. Useful for multi-step operations:

```java
@Component
public class BudgetTransferTools {

  @Tool("Credits amount to a budget line")
  String creditLine(String lineId, BigDecimal amount) {
    budgetService.credit(lineId, amount);
    return "credited:" + lineId + ":" + amount;
  }

  @CompensateFor("creditLine")
  void rollbackCredit(ToolExecution toolExecution) {
    // toolExecution.result() = "credited:lineA:500.00"
    String result = toolExecution.result();
    // parse and reverse
    budgetService.reverseCredit(parseLineId(result), parseAmount(result));
  }

  @Tool("Debits amount from a budget line")
  void debitLine(String lineId, BigDecimal amount) {
    if (budgetService.balance(lineId).compareTo(amount) < 0) {
      throw new InsufficientBudgetException(lineId);
    }
    budgetService.debit(lineId, amount);
  }

  @CompensateFor("debitLine")
  void rollbackDebit(String lineId, BigDecimal amount) {
    budgetService.reverseDebit(lineId, amount);
  }
}

// Enable compensation in the AI Service builder:
BudgetAssistant assistant = AiServices.builder(BudgetAssistant.class)
    .chatModel(model)
    .tools(new BudgetTransferTools())
    .compensateOnToolErrors(true)
    .build();
```

## Error Handling

```java
// Default: send exception.getMessage() to LLM (LLM can retry with different args)

// Custom: return generic message (hide internal errors)
Assistant assistant = AiServices.builder(Assistant.class)
    .chatModel(model)
    .tools(tools)
    .toolExecutionErrorHandler((error, ctx) ->
        ToolErrorHandlerResult.text("Tool execution failed. Please try again."))
    .build();

// Custom argument error (LLM supplied invalid args):
    .toolArgumentsErrorHandler((error, ctx) ->
        ToolErrorHandlerResult.text("Invalid argument: " + error.getMessage()))

// Strict: throw to caller for critical errors
    .toolExecutionErrorHandler((error, ctx) -> {
      if (ctx.rawError() instanceof CriticalSystemException) {
        throw (CriticalSystemException) ctx.rawError();
      }
      return ToolErrorHandlerResult.text("Tool failed.");
    })

// Handle hallucinated tool names (LLM calls a tool that doesn't exist):
    .hallucinatedToolNameStrategy(req ->
        ToolExecutionResultMessage.from(req, "No tool named '" + req.name() + "' exists."))
```

## Concurrent Tool Execution

When the LLM requests multiple tools in parallel:

```java
Assistant assistant = AiServices.builder(Assistant.class)
    .chatModel(model)
    .tools(tools)
    .executeToolsConcurrently()                    // uses default thread pool
    // or with custom executor:
    // .executeToolsConcurrently(myExecutor)
    .build();
```

Tools must be thread-safe. Avoid shared mutable state across tool instances.

## Dynamic Tool Provider

Expose tools conditionally based on the query or user context:

```java
ToolProvider dynamicProvider = (toolProviderRequest) -> {
  String query = toolProviderRequest.userMessage().singleText();
  ToolProviderResult.Builder builder = ToolProviderResult.builder();

  if (query.contains("expediente")) {
    builder.add(expedienteToolSpec, expedienteExecutor);
  }
  if (isAdmin(toolProviderRequest)) {
    builder.add(adminToolSpec, adminExecutor, ReturnBehavior.IMMEDIATE);
  }
  return builder.build();
};

Assistant assistant = AiServices.builder(Assistant.class)
    .chatModel(model)
    .toolProvider(dynamicProvider)
    .build();
```

Useful when you have many tools — avoids sending the full tool list on every request.

## Tool Search Strategy (Large Tool Sets)

When you have many tools, use semantic search to show only relevant ones to the LLM each turn:

```java
// Vector-based semantic search (best quality)
Assistant assistant = AiServices.builder(Assistant.class)
    .chatModel(model)
    .tools(allMyTools)
    .toolSearchStrategy(new VectorToolSearchStrategy())  // uses embedding similarity
    .build();

// Mark critical tools as always visible regardless of search
@Tool(value = "Escalates to a human agent", searchBehavior = SearchBehavior.ALWAYS_VISIBLE)
void escalate(String reason) { ... }
```

## AI Services as Tools — Multi-Agent Routing

An `@AiService` interface method annotated with `@Tool` can be called by another AI Service:

```java
@AiService
interface LegalExpert {
  @Tool("Analyzes the legal aspects of a user request")
  @UserMessage("You are a legal expert. Analyze: {{it}}")
  String analyze(String request);
}

@AiService
interface TechnicalExpert {
  @Tool("Analyzes the technical aspects of a user request")
  @UserMessage("You are a technical expert. Analyze: {{it}}")
  String analyze(String request);
}

@AiService
interface RouterAgent {
  @UserMessage("Route this request to the appropriate expert tool and return their answer verbatim: {{it}}")
  String route(String request);
}

// Wire up:
LegalExpert legal = AiServices.create(LegalExpert.class, cheapModel);
TechnicalExpert technical = AiServices.create(TechnicalExpert.class, cheapModel);

RouterAgent router = AiServices.builder(RouterAgent.class)
    .chatModel(model)
    .tools(legal, technical)
    .build();

router.route("Is it legal to store biometric data without consent?"); // → legal expert
router.route("Why is my API returning 502 errors?");                 // → technical expert
```

## MCP Integration (Model Context Protocol)

Connect to external MCP servers (npm packages, local processes, remote HTTP):

```java
// Stdio transport (local npm process)
McpTransport transport = StdioMcpTransport.builder()
    .command(List.of("npx", "-y", "@modelcontextprotocol/server-filesystem", "/data"))
    .logEvents(true)
    .build();

// Streamable HTTP transport (remote server)
McpTransport httpTransport = StreamableHttpMcpTransport.builder()
    .sseUrl("https://mcp.example.com/sse")
    .build();

McpClient mcpClient = DefaultMcpClient.builder()
    .key("filesystem-mcp")
    .transport(transport)
    .build();

McpToolProvider mcpProvider = McpToolProvider.builder()
    .mcpClients(mcpClient)
    .filterToolNames("read_file", "list_directory", "write_file")
    .build();

Assistant assistant = AiServices.builder(Assistant.class)
    .chatModel(model)
    .toolProvider(mcpProvider)
    .build();
```

## Low-Level API — Manual ToolSpecification

When you need programmatic control over the schema:

```java
ToolSpecification spec = ToolSpecification.builder()
    .name("searchExpediente")
    .description("Searches for expedientes by their number")
    .parameters(JsonObjectSchema.builder()
        .addStringProperty("numero", "Expediente number in format 'NNN-YYYY'")
        .addEnumProperty("estado", List.of("PENDIENTE", "EN_REVISION", "CERRADO"))
        .required("numero")
        .build())
    .build();

ToolExecutor executor = (request, memoryId) -> {
  Map<String, Object> args = fromJson(request.arguments());
  ExpedienteDetail detail = expedienteRepo.findByNumero(args.get("numero").toString());
  return detail.toJson();
};

AiServiceTool tool = AiServiceTool.builder()
    .toolSpecification(spec)
    .toolExecutor(executor)
    .returnBehavior(ReturnBehavior.TO_LLM)
    .build();

Assistant assistant = AiServices.builder(Assistant.class)
    .chatModel(model)
    .tools(List.of(tool))
    .build();
```

## Production Defaults

- Keep tool descriptions precise — the LLM reads them to decide whether/how to invoke the tool; vague descriptions cause wrong calls
- Document all `@P` parameters — LLM uses descriptions to construct arguments
- Validate ALL tool inputs as untrusted (the LLM may hallucinate argument values)
- Use `compensateOnToolErrors(true)` for multi-step write operations
- Enable `executeToolsConcurrently()` when multiple tools are expected per turn and they're thread-safe
- Use `toolExecutionErrorHandler` to hide internal error details from the LLM — `exception.getMessage()` may expose stack traces or sensitive info
- Log tool executions via `Result<T>.toolExecutions()` for audit trails
- For large tool sets (>15 tools), use `VectorToolSearchStrategy` to avoid token bloat
- Close `McpClient` on Spring context destruction (`@PreDestroy mcpClient.close()`)

**Remember**: Tools give the LLM agency over your systems. Scope them narrowly, apply authorization checks inside tool methods, and never expose destructive operations without a confirm-before-execute pattern.
