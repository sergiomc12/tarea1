---
name: springboot-observability
description: Full-stack observability for Spring Boot + LangChain4j — OpenTelemetry Java (auto-agent + manual spans), Micrometer Tracing (@Observed, ObservationRegistry), LLM span attributes (model, tokens, latency, cost), MDC log correlation (traceId/spanId), Prometheus metrics + Grafana dashboards, Spring Boot Actuator config, OTLP exporter. Python equivalents: OpenTelemetry Python, FastAPI auto-instrumentation, instrument_openai, structlog + trace correlation. Use when setting up distributed tracing, metrics, or LLM call observability for AI backends.
metadata:
  origin: sergiomc12-fork
---

# Observability: Spring Boot + LangChain4j + OpenTelemetry

## Architecture Overview

```
[Spring Boot App + LangChain4j]
    │
    ├─ Micrometer Tracing ──► OTel Bridge ──► OTLP Exporter ──► Jaeger / Tempo / Grafana Cloud
    ├─ Micrometer Metrics ──────────────────────────────────────► Prometheus ──► Grafana
    └─ SLF4J + MDC (traceId/spanId) ────────────────────────────► ELK / Loki
```

---

## Dependencies (pom.xml)

```xml
<!-- Micrometer Tracing: core + OTel bridge -->
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-tracing-bridge-otel</artifactId>
</dependency>
<!-- OTel SDK + OTLP gRPC exporter -->
<dependency>
    <groupId>io.opentelemetry</groupId>
    <artifactId>opentelemetry-exporter-otlp</artifactId>
</dependency>
<!-- Prometheus metrics endpoint -->
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
<!-- Spring Boot Actuator (exposes /actuator/prometheus) -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
<!-- OTel propagator (W3C TraceContext + Baggage) -->
<dependency>
    <groupId>io.opentelemetry</groupId>
    <artifactId>opentelemetry-extension-trace-propagators</artifactId>
</dependency>
```

---

## application.yml — Full Observability Config

```yaml
spring:
  application:
    name: ai-backend                      # sets service.name in OTel resource

management:
  tracing:
    sampling:
      probability: 1.0                    # 1.0 = trace everything (production: 0.1–0.5)
  otlp:
    tracing:
      endpoint: http://localhost:4318/v1/traces   # OTLP/HTTP (or :4317 for gRPC)
    metrics:
      export:
        url: http://localhost:4318/v1/metrics
  endpoints:
    web:
      exposure:
        include: health,info,prometheus,metrics,circuitbreakers
  metrics:
    distribution:
      percentiles-histogram:
        http.server.requests: true        # enable histogram for P95/P99
        llm.call.duration: true
      slo:
        http.server.requests: 50ms, 100ms, 500ms, 1s
    tags:
      application: ${spring.application.name}
      env: ${ENVIRONMENT:local}

logging:
  pattern:
    level: "%5p [${spring.application.name},%X{traceId:-},%X{spanId:-}]"
```

---

## Micrometer Tracing — @Observed (Recommended)

```java
import io.micrometer.observation.annotation.Observed;
import io.micrometer.observation.ObservationRegistry;
import io.micrometer.observation.Observation;

@Service
@Slf4j
public class AiOrchestrationService {

    private final ChatLanguageModel llm;
    private final ObservationRegistry observationRegistry;

    // @Observed creates a span automatically (requires AOP)
    @Observed(
        name = "llm.generate",
        contextualName = "LLM Generate Response",
        lowCardinalityKeyValues = {"model", "gpt-4o-mini", "component", "langchain4j"}
    )
    public String generateResponse(String userMessage) {
        return llm.generate(userMessage);
    }

    // Manual observation with dynamic attributes
    public String generateWithContext(String prompt, String userId, String model) {
        return Observation.createNotStarted("llm.generate", observationRegistry)
            .lowCardinalityKeyValue("model", model)
            .lowCardinalityKeyValue("user.tier", "premium")
            .highCardinalityKeyValue("user.id", userId)  // high cardinality: don't use as metric label
            .observe(() -> {
                long start = System.currentTimeMillis();
                try {
                    String response = llm.generate(prompt);
                    long durationMs = System.currentTimeMillis() - start;
                    log.info("LLM call completed. model={} duration={}ms traceId={}",
                        model, durationMs, MDC.get("traceId"));
                    return response;
                } catch (Exception e) {
                    log.error("LLM call failed. model={} error={}", model, e.getMessage());
                    throw e;
                }
            });
    }
}
```

### Enable @Observed AOP

```java
@Configuration
@EnableAspectJAutoProxy
public class ObservabilityConfig {

    @Bean
    public ObservedAspect observedAspect(ObservationRegistry observationRegistry) {
        return new ObservedAspect(observationRegistry);
    }
}
```

---

## Custom LLM Span Attributes

```java
import io.micrometer.tracing.Tracer;
import io.micrometer.tracing.Span;

@Service
@Slf4j
public class InstrumentedLlmService {

    private final ChatLanguageModel llm;
    private final Tracer tracer;
    private final MeterRegistry meterRegistry;

    // Custom timer for LLM call duration
    private final Timer llmCallTimer;
    private final Counter llmTokensCounter;

    public InstrumentedLlmService(ChatLanguageModel llm, Tracer tracer, MeterRegistry meterRegistry) {
        this.llm = llm;
        this.tracer = tracer;
        this.meterRegistry = meterRegistry;
        this.llmCallTimer = Timer.builder("llm.call.duration")
            .description("Duration of LLM API calls")
            .tag("model", "gpt-4o-mini")
            .publishPercentiles(0.5, 0.95, 0.99)
            .register(meterRegistry);
        this.llmTokensCounter = Counter.builder("llm.tokens.total")
            .description("Total tokens consumed by LLM calls")
            .register(meterRegistry);
    }

    public String generateWithInstrumentation(String prompt, String model, String userId) {
        Span span = tracer.nextSpan()
            .name("langchain4j.chat")
            .tag("llm.model", model)
            .tag("llm.provider", "openai")
            .tag("langchain4j.component", "ChatLanguageModel")
            .start();

        try (Tracer.SpanInScope scope = tracer.withSpan(span)) {
            Timer.Sample sample = Timer.start(meterRegistry);

            String response = llm.generate(prompt);

            // Estimate token counts (real implementation: use tokenizer)
            int inputTokens = prompt.split("\\s+").length * 2;   // rough estimate
            int outputTokens = response.split("\\s+").length * 2;

            span.tag("llm.usage.input_tokens", String.valueOf(inputTokens))
                .tag("llm.usage.output_tokens", String.valueOf(outputTokens))
                .tag("llm.usage.total_tokens", String.valueOf(inputTokens + outputTokens))
                .tag("llm.finish_reason", "stop");

            sample.stop(llmCallTimer);
            llmTokensCounter.increment(inputTokens + outputTokens);

            log.info("LLM call. model={} inputTokens={} outputTokens={} traceId={}",
                model, inputTokens, outputTokens, MDC.get("traceId"));

            return response;

        } catch (Exception e) {
            span.tag("error", "true")
                .error(e);
            log.error("LLM call failed. model={} traceId={}", model, MDC.get("traceId"), e);
            throw e;
        } finally {
            span.end();
        }
    }
}
```

---

## RAG Pipeline Tracing (Full Call Chain)

```java
@Service
@Slf4j
public class RagService {

    private final ObservationRegistry registry;
    private final EmbeddingModel embeddingModel;
    private final EmbeddingStore<TextSegment> vectorStore;
    private final ChatLanguageModel llm;

    @Observed(name = "rag.pipeline", contextualName = "RAG Full Pipeline")
    public String answer(String question, String userId) {
        // Step 1: Embed query
        Embedding queryEmbedding = embedQuery(question);

        // Step 2: Retrieve context
        List<EmbeddingMatch<TextSegment>> matches = retrieveContext(queryEmbedding, 4);

        // Step 3: Generate answer
        String context = matches.stream()
            .map(m -> m.embedded().text())
            .collect(Collectors.joining("\n---\n"));

        return generateAnswer(question, context);
    }

    @Observed(name = "rag.embed_query")
    private Embedding embedQuery(String question) {
        return embeddingModel.embed(question).content();
    }

    @Observed(name = "rag.retrieve", contextualName = "Vector DB Retrieval")
    private List<EmbeddingMatch<TextSegment>> retrieveContext(Embedding embedding, int k) {
        List<EmbeddingMatch<TextSegment>> results = vectorStore.findRelevant(embedding, k);
        log.debug("Retrieved {} matches. traceId={}", results.size(), MDC.get("traceId"));
        return results;
    }

    @Observed(name = "rag.generate", contextualName = "LLM Answer Generation")
    private String generateAnswer(String question, String context) {
        String prompt = String.format("""
            Answer the question based on the following context:
            %s

            Question: %s
            """, context, question);
        return llm.generate(prompt);
    }
}
```

---

## MDC Log Correlation

Spring Boot auto-populates `traceId` and `spanId` into MDC when Micrometer Tracing is on the classpath. Configure logback to include them:

### logback-spring.xml

```xml
<configuration>
    <appender name="JSON" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="net.logstash.logback.encoder.LogstashEncoder">
            <includeMdcKeyName>traceId</includeMdcKeyName>
            <includeMdcKeyName>spanId</includeMdcKeyName>
        </encoder>
    </appender>

    <root level="INFO">
        <appender-ref ref="JSON" />
    </root>
</configuration>
```

Output:
```json
{"level":"INFO","traceId":"4bf92f3577b34da6","spanId":"00f067aa0ba902b7","message":"LLM call completed. model=gpt-4o-mini duration=832ms"}
```

---

## Custom Metrics — Counters, Timers, Gauges

```java
@Service
public class LlmMetricsService {

    private final MeterRegistry registry;
    private final AtomicLong activeConversations = new AtomicLong(0);

    public LlmMetricsService(MeterRegistry registry) {
        this.registry = registry;

        // Gauge: live snapshot of current conversations
        Gauge.builder("llm.conversations.active", activeConversations, AtomicLong::get)
            .description("Number of active LLM conversations")
            .register(registry);
    }

    public void recordLlmCall(String model, long durationMs, int inputTokens, int outputTokens, boolean success) {
        Tags tags = Tags.of(
            "model", model,
            "success", String.valueOf(success)
        );

        // Timer
        Timer.builder("llm.call.duration")
            .tags(tags)
            .description("LLM API call duration")
            .register(registry)
            .record(Duration.ofMillis(durationMs));

        // Token counters
        Counter.builder("llm.tokens.input")
            .tags(tags)
            .register(registry)
            .increment(inputTokens);

        Counter.builder("llm.tokens.output")
            .tags(tags)
            .register(registry)
            .increment(outputTokens);

        // Cost estimation (OpenAI gpt-4o pricing)
        double costUsd = (inputTokens / 1_000_000.0 * 2.50) + (outputTokens / 1_000_000.0 * 10.0);
        DistributionSummary.builder("llm.call.cost.usd")
            .tags(tags)
            .description("Estimated cost per LLM call in USD")
            .register(registry)
            .record(costUsd);
    }
}
```

---

## Prometheus Queries & Grafana Panels

```promql
# P95 LLM call latency (last 5 minutes)
histogram_quantile(0.95, rate(llm_call_duration_bucket[5m]))

# LLM error rate
rate(llm_call_duration_count{success="false"}[5m])
  / rate(llm_call_duration_count[5m])

# Tokens per minute
rate(llm_tokens_input_total[1m]) + rate(llm_tokens_output_total[1m])

# Estimated cost per hour (USD)
increase(llm_call_cost_usd_sum[1h])

# Active span count (circuit breaker)
resilience4j_circuitbreaker_state{application="ai-backend"}

# HTTP P99 request latency
histogram_quantile(0.99, rate(http_server_requests_seconds_bucket[5m]))
```

---

## OpenTelemetry Java Agent (Zero-Code Auto-Instrumentation)

The simplest approach: no code changes needed.

```bash
# Download agent (latest)
wget https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/latest/download/opentelemetry-javaagent.jar

# Run Spring Boot app with agent
java \
  -javaagent:./opentelemetry-javaagent.jar \
  -Dotel.service.name=ai-backend \
  -Dotel.traces.exporter=otlp \
  -Dotel.exporter.otlp.endpoint=http://localhost:4317 \
  -Dotel.metrics.exporter=prometheus \
  -Dotel.propagators=tracecontext,baggage \
  -jar app.jar
```

```yaml
# Docker Compose: Jaeger all-in-one for local dev
services:
  jaeger:
    image: jaegertracing/jaeger:latest
    ports:
      - "16686:16686"     # Jaeger UI
      - "4317:4317"       # OTLP gRPC
      - "4318:4318"       # OTLP HTTP
```

---

## Python Equivalents

### OpenTelemetry Python Setup (FastAPI)

```bash
pip install opentelemetry-distro opentelemetry-exporter-otlp \
    opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-requests \
    opentelemetry-instrumentation-httpx
```

```python
import os
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def setup_telemetry(service_name: str = "ai-backend"):
    resource = Resource.create({"service.name": service_name, "service.version": "1.0.0"})

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"))
        )
    )
    trace.set_tracer_provider(provider)

    # Auto-instrument httpx (used by openai, httpx, etc.)
    HTTPXClientInstrumentor().instrument()

setup_telemetry()

from fastapi import FastAPI

app = FastAPI()
FastAPIInstrumentor.instrument_app(app)  # auto-instruments all routes
```

### Manual Spans with LLM Attributes (Python)

```python
import time
from opentelemetry import trace

tracer = trace.get_tracer("ai_backend.tracer")

def call_llm_with_tracing(prompt: str, model: str = "gpt-4o-mini") -> str:
    import openai
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    with tracer.start_as_current_span("llm.chat") as span:
        span.set_attribute("llm.model", model)
        span.set_attribute("llm.provider", "openai")
        span.set_attribute("llm.prompt.length", len(prompt))

        start = time.monotonic()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            duration_ms = (time.monotonic() - start) * 1000

            usage = response.usage
            span.set_attribute("llm.usage.input_tokens", usage.prompt_tokens)
            span.set_attribute("llm.usage.output_tokens", usage.completion_tokens)
            span.set_attribute("llm.usage.total_tokens", usage.total_tokens)
            span.set_attribute("llm.response.duration_ms", int(duration_ms))
            span.set_attribute("llm.finish_reason", response.choices[0].finish_reason)

            return response.choices[0].message.content

        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise
```

### Instrument OpenAI (drop-in wrapper)

```python
# Option 1: Langfuse (wraps OpenAI, traces automatically)
from langfuse.openai import OpenAI
client = OpenAI()  # all calls traced

# Option 2: OpenInference (Arize Phoenix)
pip install arize-phoenix openinference-instrumentation-openai

from phoenix.otel import register
from openinference.instrumentation.openai import OpenAIInstrumentor

register(endpoint="http://localhost:6006/v1/traces")
OpenAIInstrumentor().instrument()
```

### Structured Logging with Trace Correlation (Python)

```python
import structlog
from opentelemetry import trace

def add_otel_context(logger, method, event_dict):
    """Add traceId/spanId from current OTel context to every log record."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:
        event_dict["traceId"] = format(ctx.trace_id, "032x")
        event_dict["spanId"] = format(ctx.span_id, "016x")
    return event_dict

structlog.configure(
    processors=[
        add_otel_context,
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()
logger.info("llm_call_complete", model="gpt-4o-mini", duration_ms=832)
# → {"event":"llm_call_complete","model":"gpt-4o-mini","duration_ms":832,"traceId":"4bf9...","spanId":"00f0..."}
```

### Prometheus Metrics (Python)

```python
pip install prometheus-client
```

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# Start metrics server on port 8001
start_http_server(8001)

LLM_CALLS = Counter("llm_calls_total", "Total LLM API calls", ["model", "success"])
LLM_DURATION = Histogram(
    "llm_call_duration_seconds",
    "LLM call duration",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)
LLM_TOKENS = Counter("llm_tokens_total", "Total tokens consumed", ["model", "type"])

def instrumented_llm_call(prompt: str, model: str) -> str:
    start = time.time()
    try:
        response = call_llm(prompt)
        LLM_CALLS.labels(model=model, success="true").inc()
        return response
    except Exception:
        LLM_CALLS.labels(model=model, success="false").inc()
        raise
    finally:
        LLM_DURATION.labels(model=model).observe(time.time() - start)
```

---

## Grafana Dashboard Panels (Key Panels)

| Panel | Query | Type |
|-------|-------|------|
| LLM P95 Latency | `histogram_quantile(0.95, rate(llm_call_duration_bucket[5m]))` | Time series |
| LLM Error Rate | `rate(llm_calls_total{success="false"}[5m]) / rate(llm_calls_total[5m])` | Gauge (target < 1%) |
| Tokens/min | `rate(llm_tokens_total[1m])` | Time series |
| Cost/hour | `increase(llm_call_cost_usd_sum[1h])` | Stat |
| Active Traces | `sum(traces_active)` by service | Stat |
| CB State | `resilience4j_circuitbreaker_state` | State timeline |

---

## Related Skills
- [[springboot-resilience]] — Resilience4j metrics integrate with Micrometer here
- [[langchain4j-guardrails]] — Log and trace guardrail events
- [[langchain4j-patterns]] — The AI services being observed
- [[llm-observability]] — Python-side Langfuse/Ragas evaluation
