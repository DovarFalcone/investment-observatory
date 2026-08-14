# Data sources and free-tier policy

The application is intentionally provider-agnostic. A provider adapter must return normalized data plus source and retrieval timestamps; templates must not know provider-specific response shapes.

## Initial adapters

### Yahoo public chart/search endpoints (`yahoo_chart`)

- **Provides:** search identity metadata and daily chart history for many equities, ETFs, and mutual funds.
- **Key:** none for the public endpoints used by this low-frequency adapter.
- **Practicality:** a small, one-user list with hourly polling is technically modest, but requests are cached and history is only backfilled on add or when needed.
- **Limitations:** unofficial endpoints, no contractual SLA, possible throttling or breakage, symbol/asset coverage varies, and the endpoint may return delayed or end-of-day data.
- **Storage/display:** current Yahoo terms and any applicable data-provider terms must be reviewed before deployment. The app stores normalized observations only, never raw responses or article bodies. If the terms change, replace the adapter rather than weakening the data model.

### Google News RSS (`google_rss`)

- **Provides:** headlines, links, publisher labels, and publication timestamps for a symbol/name query.
- **Key:** none.
- **Practicality:** occasional per-security refresh is appropriate; the adapter only keeps metadata and links.
- **Limitations:** coverage, ranking, canonical links, and publisher attribution can change. It is not a guaranteed financial-news feed and should not be treated as a complete source.
- **Storage/display:** do not copy full article text. Retain only the headline, publisher, timestamp, canonical link, source, and security association. Respect publisher and feed terms; remove or disable a feed if its terms prohibit caching.

## Candidates for replacement

- **Alpha Vantage:** documented stock/ETF/other time series and news endpoints, but the free tier is commonly limited to 25 requests/day and rate limits are restrictive. It is not the default because a modest list plus history/news can exhaust the allowance. Re-evaluate current official limits before enabling it.
- **Stooq:** useful free historical datasets for some markets and asset types, but there is no stable general-purpose API contract and mutual-fund/metadata coverage needs validation. Treat as a historical fallback, not an automatic primary.
- **SEC EDGAR:** a strong free source for US company identity/filing metadata, not a quote or general news provider. Any adapter must use a descriptive User-Agent and stay below the official fair-access limit.

## Required provider behavior

- Cache successful responses and enforce minimum request intervals.
- Mark partial, stale, closed-market, and unavailable states separately.
- Never represent a failed provider request as a zero price or zero percentage change.
- Record provider name, source-observed timestamp, retrieval timestamp, and quality status.
- Keep live-provider tests opt-in; deterministic fixtures cover normal and error cases in CI.
