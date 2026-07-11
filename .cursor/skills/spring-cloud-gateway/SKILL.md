---
name: spring-cloud-gateway
description: Spring Cloud Gateway 5.x (latest stable) — API gateway for microservices. Covers both WebFlux (reactive, RouteLocatorBuilder) and WebMVC (ServerMvcRequest/RouterFunction) modes, all predicate factories, all filter factories, Redis rate limiting, CircuitBreaker filter, TokenRelay OAuth2 propagation, GlobalFilter for correlation IDs, CORS, YAML config, and load-balancer integration. Python equivalents: Traefik + FastAPI, Kong, AWS API Gateway. Use when building a centralized API gateway for Spring Boot microservices, AI backends, or multi-service architectures.
metadata:
  origin: sergiomc12-fork
---

# Spring Cloud Gateway 5.x

Spring Cloud Gateway 5.0.x is the current production-ready release. Choose one of two modes:

| Mode | Base | When to Use |
|------|------|-------------|
| **WebFlux** (default) | `spring-cloud-starter-gateway` | Fully reactive, non-blocking, high throughput |
| **WebMVC** | `spring-cloud-starter-gateway-mvc` | Existing Spring MVC app, blocking I/O acceptable |

---

## Dependencies

```xml
<!-- pom.xml — Spring Cloud Gateway WebFlux (reactive) -->
<properties>
    <spring-cloud.version>2025.0.0</spring-cloud.version>
</properties>

<dependencies>
    <dependency>
        <groupId>org.springframework.cloud</groupId>
        <artifactId>spring-cloud-starter-gateway</artifactId>
    </dependency>
    <!-- Optionally add reactive Redis for rate limiting -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-data-redis-reactive</artifactId>
    </dependency>
    <!-- OAuth2 token relay -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-oauth2-client</artifactId>
    </dependency>
    <!-- CircuitBreaker -->
    <dependency>
        <groupId>org.springframework.cloud</groupId>
        <artifactId>spring-cloud-starter-circuitbreaker-reactor-resilience4j</artifactId>
    </dependency>
</dependencies>

<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-dependencies</artifactId>
            <version>${spring-cloud.version}</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

```xml
<!-- pom.xml — Spring Cloud Gateway WebMVC (blocking) -->
<dependency>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-starter-gateway-mvc</artifactId>
</dependency>
```

---

## YAML Configuration (Recommended for Most Cases)

```yaml
spring:
  application:
    name: api-gateway
  cloud:
    gateway:
      # Global defaults
      default-filters:
        - DedupeResponseHeader=Access-Control-Allow-Origin Access-Control-Allow-Credentials, RETAIN_UNIQUE
        - AddResponseHeader=X-Gateway, spring-cloud-gateway
      # Global CORS
      globalcors:
        cors-configurations:
          "[/**]":
            allowed-origins:
              - "https://app.example.com"
              - "http://localhost:4200"
            allowed-methods:
              - GET
              - POST
              - PUT
              - DELETE
              - OPTIONS
            allowed-headers: "*"
            allow-credentials: true
            max-age: 3600
      routes:
        # ─────────────────────────────────────────────────
        # AI Backend — LangChain4j / Spring Boot AI service
        # ─────────────────────────────────────────────────
        - id: ai-backend
          uri: lb://AI-BACKEND           # via Spring Cloud LoadBalancer (Eureka/K8s)
          predicates:
            - Path=/api/ai/**
          filters:
            - StripPrefix=2              # removes /api/ai → passes /<rest> to upstream
            - TokenRelay=               # forwards OAuth2 Bearer token to upstream
            - name: RequestRateLimiter
              args:
                redis-rate-limiter.replenishRate: 10
                redis-rate-limiter.burstCapacity: 20
                redis-rate-limiter.requestedTokens: 1
                key-resolver: "#{@userKeyResolver}"
            - name: CircuitBreaker
              args:
                name: ai-backend-cb
                fallbackUri: forward:/fallback/ai-unavailable

        # ─────────────────────────────────────────────────
        # User Service
        # ─────────────────────────────────────────────────
        - id: user-service
          uri: lb://USER-SERVICE
          predicates:
            - Path=/api/users/**
            - Method=GET,POST,PUT,DELETE
          filters:
            - StripPrefix=2
            - RewritePath=/api/users/(?<segment>.*), /${segment}
            - AddRequestHeader=X-Internal-Source, api-gateway
            - TokenRelay=

        # ─────────────────────────────────────────────────
        # Public API (no auth)
        # ─────────────────────────────────────────────────
        - id: public-api
          uri: lb://PUBLIC-SERVICE
          predicates:
            - Path=/api/public/**
          filters:
            - StripPrefix=2
            - name: RequestRateLimiter
              args:
                redis-rate-limiter.replenishRate: 50
                redis-rate-limiter.burstCapacity: 100
                redis-rate-limiter.requestedTokens: 1
                key-resolver: "#{@ipKeyResolver}"

  # Redis for rate limiting
  data:
    redis:
      host: ${REDIS_HOST:localhost}
      port: ${REDIS_PORT:6379}
      password: ${REDIS_PASSWORD:}

# Eureka (if using service discovery)
eureka:
  client:
    service-url:
      defaultZone: http://eureka:8761/eureka/

management:
  endpoints:
    web:
      exposure:
        include: health,info,gateway
  endpoint:
    gateway:
      enabled: true
```

---

## Predicate Factories

| Predicate | Example | Description |
|-----------|---------|-------------|
| `Path` | `Path=/api/**` | URL path match (Ant-style) |
| `Method` | `Method=GET,POST` | HTTP methods |
| `Host` | `Host=**.example.com` | Host header match |
| `Header` | `Header=X-Request-Id, \d+` | Header name + regex |
| `Query` | `Query=version, v2` | Query param + optional regex |
| `Cookie` | `Cookie=session, abc.*` | Cookie match |
| `After` | `After=2025-01-01T00:00:00Z` | Time-based activation |
| `Before` | `Before=2025-12-31T23:59:59Z` | Time-based deactivation |
| `Between` | `Between=2025-01-01..., 2025-12-31...` | Time window |
| `Weight` | `Weight=group1, 80` | Traffic split (canary) |
| `RemoteAddr` | `RemoteAddr=192.168.1.0/24` | IP range |
| `XForwardedRemoteAddr` | `XForwardedRemoteAddr=10.0.0.0/8` | Behind load balancer IP |

---

## Filter Factories

### Request Modification

```yaml
filters:
  - AddRequestHeader=X-Tenant-Id, acme-corp
  - AddRequestParameter=version, v2
  - SetRequestHeader=X-Real-User, #{@jwtHelper.extractUser(request)}
  - RemoveRequestHeader=X-Internal-Token
  - RewritePath=/api/v1/(?<path>.*), /v2/${path}    # regex rewrite
  - StripPrefix=1                                    # strip first path segment
  - PrefixPath=/internal                             # prepend prefix
  - SetPath=/api/{segment}                           # replace path completely
```

### Response Modification

```yaml
filters:
  - AddResponseHeader=X-Response-Time, #{T(System).currentTimeMillis()}
  - RemoveResponseHeader=X-Powered-By
  - SetResponseHeader=Cache-Control, no-store
  - RewriteResponseHeader=Location, , /api/          # rewrite redirects
  - DedupeResponseHeader=Access-Control-Allow-Origin, RETAIN_UNIQUE
```

### Security Filters

```yaml
filters:
  - TokenRelay=                              # forward OAuth2 Bearer to downstream
  - SecureHeaders=                           # adds X-Frame-Options, X-XSS-Protection, etc.
  - RemoveRequestHeader=Cookie               # strip cookies (e.g., for external APIs)
```

### Routing Filters

```yaml
filters:
  - name: CircuitBreaker
    args:
      name: my-circuit-breaker
      fallbackUri: forward:/fallback/error   # internal forward on open
  - name: Retry
    args:
      retries: 3
      statuses: BAD_GATEWAY,SERVICE_UNAVAILABLE
      methods: GET
      backoff:
        firstBackoff: 100ms
        maxBackoff: 500ms
        factor: 2
        basedOnPreviousValue: false
  - name: RequestSize
    args:
      maxSize: 5MB                           # reject oversized uploads
```

---

## Java Configuration — WebFlux

```java
@Configuration
@Slf4j
public class GatewayConfig {

    // Rate limiting: per authenticated user
    @Bean
    public KeyResolver userKeyResolver() {
        return exchange -> exchange.getPrincipal()
            .map(Principal::getName)
            .defaultIfEmpty("anonymous");
    }

    // Rate limiting: per IP (for public endpoints)
    @Bean
    public KeyResolver ipKeyResolver() {
        return exchange -> Mono.just(
            exchange.getRequest().getRemoteAddress().getAddress().getHostAddress()
        );
    }

    // Programmatic route definition (alternative to YAML)
    @Bean
    public RouteLocator customRoutes(RouteLocatorBuilder builder) {
        return builder.routes()
            .route("ai-ws-route", r -> r
                .path("/ai/stream/**")
                .and().header("Upgrade", "websocket")
                .filters(f -> f
                    .stripPrefix(2)
                    .addRequestHeader("X-Gateway-Source", "websocket-route"))
                .uri("ws://ai-backend:8080"))
            .route("health-check", r -> r
                .path("/health")
                .filters(f -> f.setStatus(200))
                .uri("no://op"))
            .build();
    }
}
```

---

## Java Configuration — WebMVC

```java
@Configuration
public class GatewayMvcConfig {

    @Bean
    public RouterFunction<ServerResponse> routes(
            HandlerFunction<ServerResponse> proxyHandler) {

        return RouterFunctions.route()
            .GET("/api/ai/**", request -> {
                ServerRequest proxiedRequest = ServerRequest.from(request)
                    .header("X-Gateway-Source", "api-gateway")
                    .build();
                return proxyHandler.handle(proxiedRequest);
            })
            .POST("/api/ai/**", request -> {
                return proxyHandler.handle(request);
            })
            .build();
    }

    // WebMVC filter bean (equivalent to GlobalFilter in reactive)
    @Bean
    public FilterRegistrationBean<OncePerRequestFilter> correlationIdFilter() {
        FilterRegistrationBean<OncePerRequestFilter> bean = new FilterRegistrationBean<>();
        bean.setFilter(new OncePerRequestFilter() {
            @Override
            protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res,
                                            FilterChain chain) throws ServletException, IOException {
                String correlationId = Optional.ofNullable(req.getHeader("X-Correlation-Id"))
                    .orElse(UUID.randomUUID().toString());
                res.setHeader("X-Correlation-Id", correlationId);
                MDC.put("correlationId", correlationId);
                try {
                    chain.doFilter(req, res);
                } finally {
                    MDC.remove("correlationId");
                }
            }
        });
        bean.addUrlPatterns("/*");
        bean.setOrder(1);
        return bean;
    }
}
```

---

## GlobalFilter — Correlation ID + Logging

```java
@Component
@Slf4j
public class CorrelationIdGlobalFilter implements GlobalFilter, Ordered {

    private static final String CORRELATION_HEADER = "X-Correlation-Id";

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String correlationId = Optional
            .ofNullable(exchange.getRequest().getHeaders().getFirst(CORRELATION_HEADER))
            .orElse(UUID.randomUUID().toString());

        ServerHttpRequest mutatedRequest = exchange.getRequest().mutate()
            .header(CORRELATION_HEADER, correlationId)
            .build();

        ServerHttpResponse mutatedResponse = exchange.getResponse();
        mutatedResponse.getHeaders().add(CORRELATION_HEADER, correlationId);

        long startTime = System.currentTimeMillis();
        return chain.filter(exchange.mutate().request(mutatedRequest).build())
            .doFinally(signalType -> {
                long duration = System.currentTimeMillis() - startTime;
                log.info("method={} path={} status={} correlationId={} durationMs={}",
                    exchange.getRequest().getMethod(),
                    exchange.getRequest().getPath(),
                    exchange.getResponse().getStatusCode(),
                    correlationId,
                    duration
                );
            });
    }

    @Override
    public int getOrder() {
        return -1;   // run before route filters
    }
}
```

---

## JWT Auth Filter

```java
@Component
@Slf4j
public class JwtAuthGatewayFilter implements GlobalFilter, Ordered {

    private static final List<String> PUBLIC_PATHS = List.of(
        "/api/public/", "/actuator/health", "/fallback/"
    );

    private final JwtDecoder jwtDecoder;

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String path = exchange.getRequest().getPath().value();

        if (PUBLIC_PATHS.stream().anyMatch(path::startsWith)) {
            return chain.filter(exchange);
        }

        String authHeader = exchange.getRequest().getHeaders().getFirst(HttpHeaders.AUTHORIZATION);

        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
            return exchange.getResponse().setComplete();
        }

        String token = authHeader.substring(7);
        try {
            Jwt jwt = jwtDecoder.decode(token);
            String userId = jwt.getSubject();
            String tenantId = jwt.getClaimAsString("tenant_id");

            ServerHttpRequest enrichedRequest = exchange.getRequest().mutate()
                .header("X-User-Id", userId)
                .header("X-Tenant-Id", tenantId)
                .header("X-User-Roles", String.join(",", jwt.getClaimAsStringList("roles")))
                .build();

            return chain.filter(exchange.mutate().request(enrichedRequest).build());

        } catch (JwtException ex) {
            log.warn("Invalid JWT: {}", ex.getMessage());
            exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
            return exchange.getResponse().setComplete();
        }
    }

    @Override
    public int getOrder() {
        return 0;
    }
}
```

---

## Redis Rate Limiter

```java
@Configuration
public class RateLimiterConfig {

    // Custom rate limiter: different limits by user tier
    @Bean
    public RateLimiter customRateLimiter(ReactiveStringRedisTemplate redisTemplate) {
        return new AbstractRateLimiter<Config>(redisTemplate, "custom_rate_limiter", Config.class) {
            @Override
            public Mono<Response> isAllowed(String routeId, String id) {
                // id = userId from keyResolver
                // Fetch tier from cache or database, then apply limit
                return Mono.fromCallable(() -> {
                    String tier = getUserTier(id);   // from cache
                    long ratePerSecond = switch (tier) {
                        case "premium" -> 100;
                        case "basic"   -> 20;
                        default        -> 5;           // free
                    };
                    // Delegate to Redis sliding window...
                    return new Response(true, Map.of(
                        "X-RateLimit-Limit", String.valueOf(ratePerSecond),
                        "X-RateLimit-Remaining", "N/A"
                    ));
                });
            }
        };
    }
}
```

---

## Fallback Endpoints

```java
@RestController
@RequestMapping("/fallback")
public class FallbackController {

    @RequestMapping("/ai-unavailable")
    public ResponseEntity<Map<String, Object>> aiUnavailable() {
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(Map.of(
            "error", "AI service temporarily unavailable",
            "message", "Our AI assistant is experiencing high load. Please try again in a few moments.",
            "retryAfterSeconds", 30
        ));
    }

    @RequestMapping("/error")
    public ResponseEntity<Map<String, Object>> genericError(ServerWebExchange exchange) {
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(Map.of(
            "error", "Service unavailable",
            "path", exchange.getRequest().getPath().value()
        ));
    }
}
```

---

## Canary / Blue-Green Deployments

```yaml
spring:
  cloud:
    gateway:
      routes:
        # 10% traffic to new version
        - id: ai-backend-v2
          uri: lb://AI-BACKEND-V2
          predicates:
            - Path=/api/ai/**
            - Weight=ai-backend-group, 10

        # 90% traffic to stable version
        - id: ai-backend-v1
          uri: lb://AI-BACKEND-V1
          predicates:
            - Path=/api/ai/**
            - Weight=ai-backend-group, 90
```

---

## Observability

```yaml
management:
  tracing:
    sampling:
      probability: 1.0
  otlp:
    tracing:
      endpoint: http://otel-collector:4318/v1/traces
  endpoints:
    web:
      exposure:
        include: health,info,gateway,prometheus,metrics
  metrics:
    tags:
      application: ${spring.application.name}
```

Key gateway metrics exposed via Micrometer:
- `spring.cloud.gateway.requests` — request count by route, status
- `spring.cloud.gateway.requests.seconds` — latency histogram by route
- `spring.cloud.gateway.circuit-breaker.*` — CB state per route

---

## Python Equivalent: Traefik + FastAPI

For Python microservices architectures, Traefik replaces Spring Cloud Gateway as the reverse proxy / API gateway:

```yaml
# docker-compose.yml with Traefik
services:
  traefik:
    image: traefik:v3.1
    command:
      - --api.insecure=true
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --entryPoints.web.address=:80
      - --metrics.prometheus=true
    ports:
      - "80:80"
      - "8080:8080"   # Traefik dashboard
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

  ai-service:
    image: my-ai-service:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.ai.rule=PathPrefix(`/api/ai`)"
      - "traefik.http.routers.ai.middlewares=strip-ai-prefix,rate-limit"
      - "traefik.http.middlewares.strip-ai-prefix.stripprefix.prefixes=/api/ai"
      - "traefik.http.middlewares.rate-limit.ratelimit.average=10"
      - "traefik.http.middlewares.rate-limit.ratelimit.burst=20"
      - "traefik.http.services.ai.loadbalancer.server.port=8000"
```

**Traefik middlewares (equivalent to Gateway filters):**

```yaml
# traefik-dynamic.yml
http:
  middlewares:
    # Rate limiting
    api-rate-limit:
      rateLimit:
        average: 100
        burst: 200
        period: 1s
        sourceCriterion:
          ipStrategy:
            depth: 1

    # JWT validation (via ForwardAuth to auth service)
    jwt-auth:
      forwardAuth:
        address: http://auth-service:8080/validate
        authResponseHeaders:
          - X-User-Id
          - X-Tenant-Id
          - X-User-Roles
        trustForwardHeader: true

    # Add correlation ID header
    correlation-id:
      headers:
        customRequestHeaders:
          X-Correlation-Id: "{{random_uuid}}"

    # CORS
    cors-headers:
      headers:
        accessControlAllowMethods:
          - GET
          - POST
          - PUT
          - DELETE
          - OPTIONS
        accessControlAllowOriginList:
          - "https://app.example.com"
        accessControlAllowHeaders:
          - Content-Type
          - Authorization
        accessControlMaxAge: 3600
        addVaryHeader: true
```

**FastAPI JWT validation microservice (used with ForwardAuth):**

```python
import os
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
import jwt

app = FastAPI()
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "RS256"

@app.get("/validate")
async def validate_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        response = Response(status_code=200)
        response.headers["X-User-Id"] = payload["sub"]
        response.headers["X-Tenant-Id"] = payload.get("tenant_id", "default")
        response.headers["X-User-Roles"] = ",".join(payload.get("roles", []))
        return response
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

---

## Alternative Python API Gateways

| Option | Best For | Notes |
|--------|----------|-------|
| **Traefik v3** | Docker/K8s native, automatic service discovery | Label-based config, built-in metrics |
| **Kong (OSS)** | Plugin ecosystem, PostgreSQL-backed | Extensive plugin library (auth, rate-limit, OTel) |
| **Apache APISIX** | High performance, Lua plugins | etcd-based, cloud-native |
| **AWS API Gateway** | AWS-hosted services | Managed, Lambda authorizer for JWT |
| **NGINX + OpenResty** | Custom Lua scripting | Highly configurable but manual |
| **FastAPI** itself | Internal service-to-service | For simple cases, skip dedicated gateway |

---

## Routing Decision Guide

```
Starting a new AI microservices project?
    → Spring Cloud Gateway WebFlux (reactive)
      — high throughput, reactive Redis rate limiting, R4j circuit breaker

Existing Spring MVC app adding a gateway layer?
    → Spring Cloud Gateway WebMVC
      — same dev experience, blocking but simpler

Docker Compose / Kubernetes with Python services?
    → Traefik v3
      — label-based, zero-code config, automatic service discovery

Need a rich plugin ecosystem (caching, auth, JWT, analytics)?
    → Kong OSS or Apache APISIX

AWS-native deployment?
    → AWS API Gateway + Lambda Authorizer
```

---

## Common Pitfalls

1. **`StripPrefix` off by one** — If your route is `/api/ai/**` and upstream expects `/**`, use `StripPrefix=2` (strips `/api` and `/ai`). Use `StripPrefix=1` if upstream path starts with `/ai/`.

2. **Redis not available** — `RequestRateLimiter` filter will throw if Redis is down. Wrap with circuit breaker or add a `default-rate-limiter` fallback.

3. **TokenRelay without OAuth2 client configured** — Add `spring-boot-starter-oauth2-client` and configure `spring.security.oauth2.client.*` or TokenRelay silently passes no token.

4. **WebFlux ≠ WebMVC** — `spring-cloud-starter-gateway` (WebFlux) and `spring-cloud-starter-gateway-mvc` (WebMVC) are **mutually exclusive** — do not add both.

5. **GlobalFilter order** — Lower `getOrder()` value = higher priority. Gateway built-in filters use negative values; keep custom filters at 0 or positive to run after built-ins.

6. **Circuit breaker fallback path** — `fallbackUri: forward:/fallback/xxx` must match a real endpoint in the gateway app itself, not the downstream service.

---

## Related Skills
- [[springboot-resilience]] — Resilience4j patterns referenced by CircuitBreaker filter
- [[springboot-observability]] — OTel tracing, Prometheus metrics for the gateway layer
- [[langchain4j-guardrails]] — What the gateway protects; guardrails live in the upstream AI service
- [[springboot-patterns]] — Upstream Spring Boot services behind this gateway
