# Architecture

The Observatory is a modular monolith for one self-hosted user.

```text
Browser
  | HTML + small progressive-enhancement JS
FastAPI web process
  | domain services and provider ports
PostgreSQL <--- worker process (hourly market / periodic news)
  |
normalized observations, list metadata, linked headline metadata
```

The web process owns request/response behavior and reads normalized state. The worker owns external calls and idempotent upserts. Both use the same image and domain/service modules; they are separate Compose services so a slow provider cannot block page requests.

Provider adapters are the boundary around changing free data sources. The application depends on `MarketDataProvider` and `NewsProvider`, not on Yahoo/RSS response formats. PostgreSQL is the source of truth for local history and list state. The worker does not require Redis or a separate queue at this scale.

The UI is server-rendered using Jinja2. HTMX may be introduced for partial refreshes after the initial vertical slice, but there is no client-side state store. This keeps startup, accessibility, and reverse-proxy deployment predictable.
