---
name: springboot-resilience
description: Resilience patterns for Spring Boot + LangChain4j — Resilience4j full reference (@CircuitBreaker, @Retry with exponential backoff, @Bulkhead semaphore+threadpool, @RateLimiter, @TimeLimiter), application.yml config, fallback patterns for LLM/Vector DB calls, Micrometer metrics, programmatic API, mTLS service-to-service. Python equivalents: tenacity, circuitbreaker, asyncio timeout, httpx retries. Use when making LLM or Vector DB calls that need circuit-breaking, retry, bulkhead isolation, or rate limiting.
metadata:
  origin: sergiomc12-fork
---

# Resilience Patterns: Spring Boot + LangChain4j

## Dependency (pom.xml)

```xml
<!-- Resilience4j Spring Boot starter (includes all modules) -->
<dependency>
    <groupId>io.github.resilience4j</groupId>
    <artifactId>resilience4j-spring-boot3</artifactId>
    <version>2.2.0</version>
</dependency>
<!-- AOP required for annotation support -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-aop</artifactId>
</dependency>
<!-- Micrometer for metrics export -->
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

## Annotation Execution Order

Default precedence (inner → outer): `Retry → CircuitBreaker → RateLimiter → TimeLimiter → Bulkhead`

Override per annotation: `resilience4j.retry.retryAspectOrder=2` (higher = outermost).

---

## @CircuitBreaker

### States

```
CLOSED ──(failureRate ≥ threshold)──► OPEN ──(waitDuration elapsed)──► HALF_OPEN
                                         ▲                                    │
                          (test calls fail)──────────────────────────────────┘
                                                     │
                          (test calls pass)──► CLOSED
```

### application.yml — Full Config

```yaml
resilience4j:
  circuitbreaker:
    configs:
      default:                              # shared base config
        slidingWindowType: COUNT_BASED      # COUNT_BASED | TIME_BASED
        slidingWindowSize: 10               # number of calls (COUNT) or seconds (TIME)
        minimumNumberOfCalls: 5             # min calls before rate calculation
        failureRateThreshold: 50            # % failures to OPEN (default 50)
        slowCallRateThreshold: 100          # % slow calls to OPEN
        slowCallDurationThreshold: 2s       # what counts as "slow"
        waitDurationInOpenState: 10s        # time in OPEN before HALF_OPEN
        permittedNumberOfCallsInHalfOpenState: 3
        automaticTransitionFromOpenToHalfOpenEnabled: true
        recordExceptions:
          - java.io.IOException
          - java.util.concurrent.TimeoutException
          - feign.FeignException
        ignoreExceptions:
          - com.example.BusinessException
        registerHealthIndicator: true
        eventConsumerBufferSize: 10
    instances:
      llmService:
        baseConfig: default
        slidingWindowSize: 5
        failureRateThreshold: 40
        waitDurationInOpenState: 30s        # LLM providers may take longer to recover
      vectorDb:
        baseConfig: default
        slidingWindowSize: 20
        slowCallDurationThreshold: 500ms
```

### Java — @CircuitBreaker + @Fallback

```java
@Service
@Slf4j
public class LlmService {

    private final ChatLanguageModel llm;

    public LlmService(ChatLanguageModel llm) {
        this.llm = llm;
    }

    @CircuitBreaker(name = "llmService", fallbackMethod = "fallbackResponse")
    public String generate(String prompt) {
        return llm.generate(prompt);
    }

    // Fallback: same return type + Throwable parameter (most specific exception first)
    public String fallbackResponse(String prompt, CallNotPermittedException e) {
        log.warn("Circuit OPEN for LLM service, using cached response. Prompt: {}", prompt);
        return "Service temporarily unavailable. Please try again in a moment.";
    }

    public String fallbackResponse(String prompt, Throwable e) {
        log.error("LLM call failed, falling back. Reason: {}", e.getMessage());
        return "I'm unable to process your request right now.";
    }
}
```

### Programmatic API

```java
CircuitBreakerRegistry registry = CircuitBreakerRegistry.ofDefaults();

CircuitBreakerConfig config = CircuitBreakerConfig.custom()
    .failureRateThreshold(50)
    .slowCallDurationThreshold(Duration.ofSeconds(2))
    .slidingWindowType(SlidingWindowType.TIME_BASED)
    .slidingWindowSize(10)
    .minimumNumberOfCalls(5)
    .waitDurationInOpenState(Duration.ofSeconds(30))
    .permittedNumberOfCallsInHalfOpenState(3)
    .recordExceptions(IOException.class, TimeoutException.class)
    .build();

CircuitBreaker cb = registry.circuitBreaker("llmService", config);

// Decorate a call
Supplier<String> decorated = CircuitBreaker.decorateSupplier(cb, () -> llm.generate(prompt));
String result = Try.ofSupplier(decorated).getOrElse("fallback response");

// Listen to state transitions
cb.getEventPublisher()
    .onStateTransition(e -> log.info("CB transition: {} → {}", e.getStateTransition().getFromState(), e.getStateTransition().getToState()))
    .onCallNotPermitted(e -> log.warn("CB OPEN: call rejected"));
```

---

## @Retry

### application.yml

```yaml
resilience4j:
  retry:
    configs:
      default:
        maxAttempts: 3
        waitDuration: 500ms
        enableExponentialBackoff: true
        exponentialBackoffMultiplier: 2        # each wait * 2
        exponentialMaxBackoff: 10s             # cap at 10s
        enableRandomizedWait: true             # add jitter
        randomizedWaitFactor: 0.5              # ±50% of wait
        retryExceptions:
          - java.io.IOException
          - java.net.ConnectException
          - feign.RetryableException
        ignoreExceptions:
          - com.example.NonRetryableException
        failAfterMaxRetries: false             # true → throw MaxRetriesExceededException
    instances:
      llmRetry:
        baseConfig: default
        maxAttempts: 4
        waitDuration: 1s
        exponentialBackoffMultiplier: 2
        exponentialMaxBackoff: 30s
      vectorDbRetry:
        baseConfig: default
        maxAttempts: 2
        waitDuration: 200ms
```

### Java — @Retry

```java
@Service
public class EmbeddingService {

    private final EmbeddingStore<TextSegment> vectorStore;

    @Retry(name = "vectorDbRetry", fallbackMethod = "fallbackEmbeddingSearch")
    @CircuitBreaker(name = "vectorDb", fallbackMethod = "fallbackEmbeddingSearch")
    public List<EmbeddingMatch<TextSegment>> search(Embedding queryEmbedding, int maxResults) {
        return vectorStore.findRelevant(queryEmbedding, maxResults);
    }

    public List<EmbeddingMatch<TextSegment>> fallbackEmbeddingSearch(
            Embedding embedding, int maxResults, Throwable e) {
        log.warn("Vector DB unavailable, returning empty results: {}", e.getMessage());
        return Collections.emptyList();
    }
}
```

### Programmatic API with Exponential Backoff

```java
RetryConfig config = RetryConfig.custom()
    .maxAttempts(4)
    .intervalFunction(IntervalFunction.ofExponentialRandomBackoff(
        Duration.ofMillis(500),  // initial interval
        2.0,                      // multiplier
        0.5,                      // randomization factor
        Duration.ofSeconds(30)    // max interval
    ))
    .retryExceptions(IOException.class, HttpClientErrorException.class)
    .retryOnResult(response -> ((HttpStatus) response).is5xxServerError())
    .build();

Retry retry = Retry.of("llmRetry", config);
```

---

## @Bulkhead

Two modes: **Semaphore** (default, sync) or **ThreadPool** (async, reactive).

### application.yml

```yaml
resilience4j:
  bulkhead:
    configs:
      default:
        maxConcurrentCalls: 10             # max parallel calls
        maxWaitDuration: 0ms               # 0 = fail immediately when saturated
    instances:
      llmBulkhead:
        maxConcurrentCalls: 5              # isolate LLM calls from rest of app
        maxWaitDuration: 500ms
      vectorDbBulkhead:
        maxConcurrentCalls: 20
        maxWaitDuration: 100ms

  thread-pool-bulkhead:
    configs:
      default:
        maxThreadPoolSize: 10
        coreThreadPoolSize: 5
        queueCapacity: 20
        keepAliveDuration: 20ms
    instances:
      asyncLlmBulkhead:
        maxThreadPoolSize: 4               # isolate async LLM in its own pool
        coreThreadPoolSize: 2
        queueCapacity: 10
```

### Java

```java
// Semaphore (sync)
@Bulkhead(name = "llmBulkhead", fallbackMethod = "bulkheadFallback")
@CircuitBreaker(name = "llmService", fallbackMethod = "circuitFallback")
public String generate(String prompt) {
    return llm.generate(prompt);
}

public String bulkheadFallback(String prompt, BulkheadFullException e) {
    return "Service busy, please retry in a few seconds.";
}

// ThreadPool (async — use with @Async or CompletableFuture)
@Bulkhead(name = "asyncLlmBulkhead", type = Bulkhead.Type.THREADPOOL)
public CompletableFuture<String> generateAsync(String prompt) {
    return CompletableFuture.supplyAsync(() -> llm.generate(prompt));
}
```

---

## @RateLimiter

### application.yml

```yaml
resilience4j:
  ratelimiter:
    configs:
      default:
        limitForPeriod: 10              # permits per refresh period
        limitRefreshPeriod: 1s          # period length
        timeoutDuration: 0s             # wait for permit (0 = fail immediately)
        registerHealthIndicator: false
    instances:
      llmRateLimiter:
        limitForPeriod: 5               # max 5 LLM calls per second per instance
        limitRefreshPeriod: 1s
        timeoutDuration: 250ms          # wait up to 250ms for a permit
      perUserRateLimiter:
        limitForPeriod: 20
        limitRefreshPeriod: 60s         # 20 calls per minute
```

### Java — Per-User Rate Limiting

```java
@Service
public class LlmRateLimitedService {

    private final RateLimiterRegistry rateLimiterRegistry;
    private final ChatLanguageModel llm;

    @RateLimiter(name = "llmRateLimiter", fallbackMethod = "rateLimitedFallback")
    public String generate(String prompt) {
        return llm.generate(prompt);
    }

    // Per-user rate limiting (dynamic instance name)
    public String generateForUser(String userId, String prompt) {
        RateLimiter userLimiter = rateLimiterRegistry.rateLimiter(
            "user-" + userId,
            "perUserRateLimiter"   // use this config as base
        );
        return RateLimiter.decorateSupplier(userLimiter, () -> llm.generate(prompt)).get();
    }

    public String rateLimitedFallback(String prompt, RequestNotPermitted e) {
        return "Rate limit exceeded. Please slow down your requests.";
    }
}
```

---

## @TimeLimiter

### application.yml

```yaml
resilience4j:
  timelimiter:
    configs:
      default:
        timeoutDuration: 30s            # LLM calls can be slow
        cancelRunningFuture: true
    instances:
      llmTimeout:
        timeoutDuration: 60s            # allow up to 60s for complex prompts
      vectorDbTimeout:
        timeoutDuration: 3s
```

### Java

```java
// TimeLimiter works with async (CompletableFuture / Flux / Mono)
@TimeLimiter(name = "llmTimeout", fallbackMethod = "timeoutFallback")
@CircuitBreaker(name = "llmService", fallbackMethod = "circuitFallback")
public CompletableFuture<String> generateAsync(String prompt) {
    return CompletableFuture.supplyAsync(() -> llm.generate(prompt));
}

public CompletableFuture<String> timeoutFallback(String prompt, TimeoutException e) {
    return CompletableFuture.completedFuture("Request timed out. The model is taking too long.");
}
```

---

## LangChain4j — Full Resilient Stack

```java
@Service
@Slf4j
public class ResilientAiService {

    private final ChatLanguageModel primaryLlm;       // Azure OpenAI
    private final ChatLanguageModel fallbackLlm;      // OpenAI direct
    private final EmbeddingStore<TextSegment> vectorStore;
    private final CircuitBreakerRegistry cbRegistry;

    // Retry + CircuitBreaker + Bulkhead + TimeLimiter stacked
    @Retry(name = "llmRetry")
    @CircuitBreaker(name = "llmService", fallbackMethod = "fallbackToSecondaryLlm")
    @Bulkhead(name = "llmBulkhead")
    @TimeLimiter(name = "llmTimeout")
    public CompletableFuture<String> chat(String prompt) {
        return CompletableFuture.supplyAsync(() -> primaryLlm.generate(prompt));
    }

    // First fallback: try secondary LLM
    @CircuitBreaker(name = "fallbackLlm", fallbackMethod = "staticFallback")
    public CompletableFuture<String> fallbackToSecondaryLlm(String prompt, Throwable e) {
        log.warn("Primary LLM failed ({}), trying fallback model", e.getClass().getSimpleName());
        return CompletableFuture.supplyAsync(() -> fallbackLlm.generate(prompt));
    }

    // Second fallback: static response
    public CompletableFuture<String> staticFallback(String prompt, Throwable e) {
        log.error("Both LLMs failed. Prompt: {}", prompt, e);
        return CompletableFuture.completedFuture(
            "I'm experiencing technical difficulties. Please try again later.");
    }

    // Vector DB with retry
    @Retry(name = "vectorDbRetry")
    @CircuitBreaker(name = "vectorDb", fallbackMethod = "emptyResults")
    public List<EmbeddingMatch<TextSegment>> retrieve(Embedding query, int k) {
        return vectorStore.findRelevant(query, k);
    }

    public List<EmbeddingMatch<TextSegment>> emptyResults(Embedding q, int k, Throwable e) {
        log.warn("Vector DB unavailable, returning empty context");
        return Collections.emptyList();
    }
}
```

---

## Micrometer Metrics (Auto-Published)

```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus,metrics,circuitbreakers,circuitbreakerevents
  health:
    circuitbreakers:
      enabled: true
```

Key metrics:
- `resilience4j_circuitbreaker_calls_total{name,kind}` — kind: successful/failed/ignored/not_permitted
- `resilience4j_circuitbreaker_state{name}` — 0=CLOSED, 1=OPEN, 2=HALF_OPEN, 3=FORCED_OPEN, 4=DISABLED
- `resilience4j_circuitbreaker_failure_rate{name}`
- `resilience4j_retry_calls_total{name,kind}` — kind: successful_without_retry/successful_with_retry/failed_without_retry/failed_with_retry
- `resilience4j_bulkhead_available_concurrent_calls{name}`
- `resilience4j_ratelimiter_available_permissions{name}`

```promql
# Grafana: Circuit breaker open events per service per minute
increase(resilience4j_circuitbreaker_calls_total{kind="not_permitted"}[1m])

# Retry success rate
rate(resilience4j_retry_calls_total{kind="successful_with_retry"}[5m])
  / rate(resilience4j_retry_calls_total[5m])
```

---

## Python Equivalents

### Tenacity (Retry + Backoff)

```python
import os
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_exponential_jitter,
    retry_if_exception_type,
    retry_if_result,
    before_sleep_log,
    RetryError,
)
import logging

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def call_llm(prompt: str) -> str:
    """Call LLM with exponential backoff retry."""
    import openai
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content

# Async
from tenacity import AsyncRetrying

async def call_llm_async(prompt: str) -> str:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    ):
        with attempt:
            import openai
            client = openai.AsyncOpenAI()
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
```

### CircuitBreaker (pybreaker)

```python
pip install pybreaker
```

```python
import pybreaker
import functools

# Configure circuit breaker
llm_breaker = pybreaker.CircuitBreaker(
    fail_max=5,                   # open after 5 consecutive failures
    reset_timeout=30,             # seconds before moving to HALF_OPEN
    exclude=[ValueError],         # don't count these as failures
    name="llm_service",
)

@llm_breaker
def call_llm_with_cb(prompt: str) -> str:
    import openai
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content

# With fallback
def call_with_fallback(prompt: str) -> str:
    try:
        return call_llm_with_cb(prompt)
    except pybreaker.CircuitBreakerError:
        return "Service temporarily unavailable. Please try again shortly."
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return "Error processing your request."
```

### asyncio Timeout

```python
import asyncio

async def call_llm_with_timeout(prompt: str, timeout: float = 30.0) -> str:
    try:
        return await asyncio.wait_for(call_llm_async(prompt), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("LLM call timed out after %ss", timeout)
        return "Request timed out."
```

### Rate Limiting (Python — token bucket)

```python
pip install ratelimit
```

```python
from ratelimit import limits, sleep_and_retry

CALLS_PER_SECOND = 5
ONE_SECOND = 1

@sleep_and_retry
@limits(calls=CALLS_PER_SECOND, period=ONE_SECOND)
def rate_limited_llm_call(prompt: str) -> str:
    return call_llm(prompt)

# Per-user rate limiting with in-memory store
from collections import defaultdict
import time

class PerUserRateLimiter:
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self._calls: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: str) -> bool:
        now = time.monotonic()
        calls = self._calls[user_id]
        calls[:] = [t for t in calls if now - t < self.period]
        if len(calls) < self.max_calls:
            calls.append(now)
            return True
        return False

limiter = PerUserRateLimiter(max_calls=20, period=60.0)

def call_for_user(user_id: str, prompt: str) -> str:
    if not limiter.is_allowed(user_id):
        raise ValueError(f"Rate limit exceeded for user {user_id}")
    return call_llm(prompt)
```

---

## Related Skills
- [[langchain4j-patterns]] — LangChain4j service patterns to protect with resilience
- [[springboot-observability]] — Instrument resilience metrics with OTel + Micrometer
- [[spring-cloud-gateway]] — Rate limiting at the gateway layer
- [[langchain4j-guardrails]] — AI-specific guardrails (prompt injection, cost control)
