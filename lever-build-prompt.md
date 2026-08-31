# Build Prompt: "Lever" — NGX Paper Trading Platform

You are building **Lever**, a paper-trading (fake money) web app for the Nigerian Exchange (NGX). Users trade with simulated capital only — no real money ever moves — but the trading mechanics themselves must be real: longing, shorting, and leverage, all governed by realistic risk rules. Everyone starts with **₦10,000** in virtual cash. There is a public leaderboard ranked by total portfolio value.

Work inside a root folder named `Lever/`, with two subfolders:

```
Lever/
  frontend/   → Next.js app
  backend/    → FastAPI app
```

Read this entire prompt before writing any code. It is organized as: (1) data source & ingestion pipeline, (2) data model, (3) trading mechanics including leverage/liquidity tiering and supply controls, (4) backend API surface, (5) frontend spec page-by-page and click-by-click, (6) auth, (7) design system, (8) non-functional requirements. Follow it precisely — where a default/threshold is given, use it but implement it as a named constant/config value so it's easy to tune later.

---

## 1. Data source: Kobo Terminal API

Base URL: `https://koboterminal.com`. Auth via header `X-API-Key: <key>`. We are on the **free "Personal" tier**: **10 requests/minute, 100 requests/day**. This budget is small and must be respected exactly — build the ingestion pipeline to be extremely frugal with calls. Never call the API from a request handler that serves a user; only a scheduled background job may call Kobo Terminal.

### 1.1 Endpoints we will use (Personal tier)
- `GET /api/ngxdata/stocks` — returns all 150+ listed NGX equities in one call: `symbol`, `name`, `current_price`, `change_percent`, `volume`, `shares_outstanding`, `sector`, `pe_ratio`. This is our **only** price source and it returns every company in a single request — huge advantage, use it.
- `GET /api/ngxdata/market-status` — returns `{status: "open"|"closed", message, timestamp}`. NGX hours are 9:00 AM–4:00 PM WAT (UTC+1, no DST), Monday–Friday, **excluding Nigerian public holidays** — this endpoint is the authority on holiday closures, so always defer to it rather than hardcoding a weekday check alone.

### 1.2 Endpoints that are NOT available to us (do not call these)
`fundamentals`, `prices/:symbol` historical series, `nasddata/*`, `forex/rates`, and history endpoints are gated to **Starter tier and above** (paid). This has a real design consequence spelled out in Section 3.2: our liquidity/leverage tiering system **cannot** use the fundamentals endpoint (beta, debt/equity, etc.) — it must be derived entirely from data we accumulate ourselves out of the free `/stocks` payload over time, stored in our own database.

### 1.3 Ingestion cadence — the core caching architecture

**Critical requirement: exactly one external API call to `/stocks` per hour, only during NGX trading hours, never fanned out per-user.** Flow:

```
Kobo Terminal API  →  Scheduler job (backend, once/hour)  →  Postgres (durable)  →  Redis (serving cache, TTL 1h)  →  all users read from Redis via our API
```

Build a scheduled job (APScheduler or a Celery-beat/RQ worker — pick one and be consistent) that runs **on the hour, every hour, Monday–Friday**, restricted to the window covering 9:00–16:00 WAT (i.e. schedule ticks at 09:00, 10:00, 11:00, 12:00, 13:00, 14:00, 15:00, 16:00 Africa/Lagos time — use the `Africa/Lagos` IANA timezone, not a manual UTC+1 offset, so DST-less correctness is guaranteed by the tz database).

**Status check happens once a day, not once per tick:**

1. At the 09:00 tick only, call `GET /api/ngxdata/market-status` (1 call). If `status != "open"` (i.e. today is a public holiday), set an in-memory/Redis flag `market:status = closed` for the day and skip every remaining tick until tomorrow's 09:00 check — do not call `/stocks` at all today.
2. If `status == "open"`, set `market:status = open` and proceed to pull prices at 09:00 and at every tick after it (10:00 through 16:00) **without re-checking market-status again** — the app simply trusts that a day that opened will run its normal 9–4 session. (We are deliberately accepting the small risk of an unannounced mid-day closure going undetected until the next day's check — not worth the extra API calls to guard against.)
3. At each price-pulling tick, call `GET /api/ngxdata/stocks` (1 call) to get all companies + prices.
4. Upsert every symbol into a `stock_price_snapshots` table (immutable, append-only — this history is our substitute for the paid historical endpoints, see 3.2) and update the `stocks` table's `current_price`/`change_percent`/`volume` "latest" columns.
5. Write the entire payload to Redis as one key `stocks:latest` (JSON array, `EX 3600`) **and** one key per symbol `stock:{SYMBOL}` (`EX 3600`) for O(1) single-symbol lookups. Setting `EX 3600` means if the scheduler ever fails to run, the cache naturally expires an hour after the last good pull rather than serving indefinitely-stale data.
6. Immediately after each price refresh, run two dependent jobs synchronously in the same tick (no extra API calls needed, they operate on data already in Postgres): (a) the **margin/liquidation sweep** (Section 3.5) against the new prices, and (b) a **portfolio snapshot** for every user (cash + mark-to-market value of open positions) written to a `portfolio_snapshots` table, which is what powers the dashboard's performance chart and the leaderboard's "as of" values.

**Rate budget sanity check:** 1 status check + 8 price-pulling ticks/day = **9 calls/day**, well inside the 100/day cap, leaving generous headroom for manual/admin refreshes, health checks, or a retry-once-on-failure policy per tick (a failed tick may retry once, capping worst case around 17 calls/day). Never call these endpoints from anywhere else in the codebase. Do not poll `market-status` on every user page load — the frontend derives "is the market open right now" from (a) the cached `status` value written by the last successful tick, plus (b) a client-side clock check against the 9–4 Mon–Fri window as a fast visual fallback while waiting for the next tick, clearly documented in code as a fallback, not a source of truth.

**Outside trading hours / weekends:** the scheduler simply doesn't tick on Saturdays/Sundays, and on a holiday it stops after the single 09:00 status check comes back closed. The last cached prices remain in Postgres as `current_price` (so the UI always has something to show — Friday's close over the weekend, etc.), but the Redis TTL will lapse; when serving stale-cache reads outside market hours, the backend should read straight from Postgres's last-known values instead of failing, and stamp the response with `as_of` + `market_status: "closed"` so the frontend can render the closed-market banner accurately.

### 1.4 Redis key design
- `stocks:latest` → JSON array of all stocks, `EX 3600`
- `stock:{SYMBOL}` → JSON object, `EX 3600`
- `market:status` → `"open" | "closed"`, set on every tick (no TTL — always overwritten by the next tick or by the closed-market fallback logic)
- `leaderboard:top` → precomputed sorted leaderboard, `EX 3600`, recomputed after each portfolio snapshot job

---

## 2. Data model (Postgres)

Design and create these tables (adjust types to your ORM, SQLAlchemy + Alembic migrations recommended):

**users**
`id (uuid pk), username (unique, 3–20 chars), email (unique), password_hash, cash_balance (numeric, default 10000.00), created_at, jwt_version (int, default 0 — bump to invalidate all issued tokens on password change)`

**stocks**
`symbol (pk), name, sector, shares_outstanding, current_price, change_percent, volume, pe_ratio, liquidity_tier (enum: BLUE_CHIP, ESTABLISHED, VOLATILE, RESTRICTED, default RESTRICTED), margin_requirement (numeric, e.g. 0.25), max_leverage (numeric, e.g. 4.0), shortable (bool, default true — RESTRICTED tier sets this false, see 3.2), tier_last_computed_at, listed_since (first date we ever saw this symbol, for the "<30 days of data" rule), updated_at`

**stock_price_snapshots** (append-only, one row per symbol per hourly tick — this is our home-grown substitute for the paid history endpoint)
`id, symbol (fk), price, change_percent, volume, captured_at (timestamptz, indexed)`

**positions** (one row per open or closed position)
`id, user_id (fk), symbol (fk), side (enum: LONG, SHORT), leverage (numeric, e.g. 1.0–4.0), entry_price, quantity (shares, can be fractional), margin_used (numeric, cash committed), liquidation_price (computed at open, recalculated on partial close), status (enum: OPEN, CLOSED, LIQUIDATED), opened_at, closed_at, exit_price (nullable), realized_pnl (nullable)`

**trades** (immutable audit log of every execution — opens, adds, partial closes, full closes, liquidations)
`id, user_id, position_id, symbol, action (enum: OPEN_LONG, OPEN_SHORT, CLOSE_LONG, CLOSE_SHORT, LIQUIDATION), leverage, price_executed (post-spread, see 3.4), quantity, cash_delta, executed_at`

**portfolio_snapshots** (one row per user per hourly tick, for the dashboard chart & leaderboard)
`id, user_id, cash_balance, positions_value, total_equity, captured_at`

**open_interest** (derived/materialized, or compute on the fly — see 3.6)
`symbol, total_long_shares, total_short_shares, updated_at`

---

## 3. Trading mechanics

### 3.1 Starting balance & basic long/short
Every new signup gets `cash_balance = 10000.00`. A **long** position profits when price rises; a **short** position profits when price falls. Both are available on every shortable stock (RESTRICTED tier disables shorting — cash-only, 1x). Users can go long or short with or without leverage, and can partially or fully close either.

### 3.2 Liquidity tiering → leverage caps (computed monthly, from our own data — not the paid fundamentals endpoint)

Because `/fundamentals` requires a paid tier, tier assignment is derived purely from what `/stocks` gives us for free, accumulated hourly into `stock_price_snapshots` over time. Run a monthly job (1st of each month, 00:00 Africa/Lagos — zero external API calls, it only reads our own Postgres history) that, for each symbol, computes over the trailing 30 calendar days of snapshots:

- `market_cap = current_price × shares_outstanding`
- `avg_daily_value_traded` = for each trading day, take that day's max `volume` snapshot (NGX volume is cumulative intraday, so the last snapshot of the day approximates the day's total shares traded) × that day's closing price, then average across the days in the window
- `volatility` = standard deviation of daily `change_percent` across the window
- `data_days` = count of distinct trading days with at least one snapshot for this symbol

Apply this default threshold table (implement as config constants, e.g. `LIQUIDITY_THRESHOLDS`, so they can be tuned without a redeploy of business logic):

| Tier | Rule | Margin requirement | Max leverage | Shortable |
|---|---|---|---|---|
| **Blue Chip** | `data_days ≥ 20` AND `market_cap ≥ ₦500B` AND `avg_daily_value_traded ≥ ₦100M` AND `volatility < 3%` | 25% | 4× | Yes |
| **Established** | `data_days ≥ 20` AND `market_cap ≥ ₦50B` AND `avg_daily_value_traded ≥ ₦20M` | 40% | 2.5× | Yes |
| **Volatile** | `data_days ≥ 20` AND has non-zero volume on most trading days in the window | 75% | 1.33× | Yes |
| **Restricted** | Anything else: `data_days < 20` (newly listed, or newly added to Lever and not yet tracked a full month), zero/near-zero volume on more than half the window's trading days, or fails all tiers above | 100% | 1× | **No** |

A stock defaults to **Restricted** the moment it's first seen (no history yet) and gets promoted at the next monthly run once it has ≥20 trading days of accumulated snapshots. Store the computed tier, `margin_requirement`, `max_leverage`, and `shortable` flag on the `stocks` row, and stamp `tier_last_computed_at`. Expose the tier and its rationale (or at least the tier name and max leverage) on the trade screen so users understand why a stock caps out at a given leverage.

### 3.3 Opening a position
Request: `{symbol, side (LONG|SHORT), leverage (1.0 – stock's max_leverage), amount (NGN notional the user wants to commit)}`.

Server-side validation, in order:
1. Market must currently be open (reject with 403 `market_closed` otherwise — see 1.3).
2. `leverage ≤ stocks.max_leverage` for that symbol; if `side == SHORT`, `stocks.shortable` must be true.
3. `amount` (this is the **margin** the user is committing, not notional exposure) must not exceed available `cash_balance`.
4. Compute `notional = amount × leverage`; `quantity = notional / execution_price` (execution price includes the spread from 3.4).
5. Open-interest cap check (Section 3.6) — reject if it would breach the per-symbol supply cap.
6. Debit `cash_balance` by `amount` (the margin — this is what's "at risk" and locked up), create the `positions` row with `margin_used = amount`, compute and store `liquidation_price` (Section 3.5), and write a `trades` row.

### 3.4 Execution price & the synthetic spread (this is also part of the "supply" mechanic)
Because prices only refresh hourly rather than tick-by-tick, all orders in a given hour execute at the same cached price, which would let users trade with zero friction and zero market impact — unrealistic and gameable. Apply a small synthetic spread based on the stock's liquidity tier when computing the execution price actually used for `entry_price`/`exit_price` (never mutate the underlying cached market price itself, only the price used for this specific trade's math):

- Blue Chip: 0.15% spread
- Established: 0.35% spread
- Volatile: 0.75% spread
- Restricted: 1.5% spread

Opening a **long** or covering (closing) a **short** buys at `mid_price × (1 + spread/2)`. Opening a **short** or closing a **long** sells at `mid_price × (1 - spread/2)`. This means every trade costs a little on entry and exit — realistic, discourages wash-trading the leaderboard, and is one of the two "supply control" levers, alongside 3.6.

### 3.5 Leverage, margin, and liquidation
`margin_used` is the cash locked against the position. Maintenance margin is set at **50% of the initial margin requirement** for that stock's tier (e.g. a Blue Chip position opened at 25% initial margin gets liquidated once the position's remaining equity falls to 12.5% of notional). At `liquidation_price`:

- Long liquidation price: `entry_price × (1 - initial_margin_fraction × 0.5 / leverage_factor_adj)` — concretely, solve for the price at which `margin_used + unrealized_pnl = maintenance_margin_requirement`, i.e. the price at which losses have eaten through half the posted margin.
- Short liquidation price: mirrored upward.

Store `liquidation_price` at open (and recompute after any partial close, since `margin_used` and `quantity` change). The **margin/liquidation sweep** (run every hourly tick, right after prices update — see 1.3 step 5) scans all `OPEN` positions and force-closes (status → `LIQUIDATED`) any position whose stored `liquidation_price` has been breached by the new `current_price`, executing at that tick's spread-adjusted price, realizing the loss, and writing a `trades` row with `action = LIQUIDATION`. Because prices only move hourly, liquidation checks only need to run once per tick, not continuously — no polling job needed beyond the existing scheduler.

### 3.6 Controlling the supply of a stock (open interest caps)
To stop the simulation from producing absurd outcomes (e.g. aggregate simulated short interest many multiples of a company's real float, or one whale cornering a thin stock), maintain running `total_long_shares` and `total_short_shares` per symbol (materialize into the `open_interest` table on every open/close/liquidation, inside the same transaction as the position change — don't recompute from scratch each time).

Enforce, at order time:
- **Float cap:** `total_long_shares + new_order_shares ≤ OPEN_INTEREST_CAP_PCT × shares_outstanding` (default `OPEN_INTEREST_CAP_PCT = 5%`), same rule applied independently to the short side. Once a symbol's side is at cap, reject new orders on that side with a clear error (`open_interest_cap_reached`) until other users close positions and free up room — this creates genuine scarcity and a first-come-first-served dynamic on thin/RESTRICTED stocks.
- **Per-order size cap relative to typical volume:** a single order's `quantity` cannot exceed `MAX_ORDER_PCT_OF_ADV × avg_daily_value_traded / current_price` (default `MAX_ORDER_PCT_OF_ADV = 2%`) — stops one order from being wildly out of scale with how the real stock actually trades.
- **Per-user concentration cap:** a single position's `margin_used` cannot exceed `MAX_POSITION_PCT_OF_EQUITY × user's total_equity` (default 50%) — encourages diversification, prevents one all-in leveraged bet from dominating the leaderboard purely on variance.

All four caps (`OPEN_INTEREST_CAP_PCT`, `MAX_ORDER_PCT_OF_ADV`, `MAX_POSITION_PCT_OF_EQUITY`, and the maintenance-margin fraction from 3.5) should live in one config module so they can be tuned as the product evolves.

### 3.7 Closing / selling a position
Request: `{position_id, quantity_to_close}` (allow partial closes — `quantity_to_close < position.quantity` reduces the position and proportionally reduces `margin_used`; full close sets `status = CLOSED`). Compute `exit_price` with the appropriate spread direction from 3.4, `realized_pnl = (exit_price - entry_price) × quantity_closed × sign(side)` scaled correctly for leverage, credit `margin_used_portion + realized_pnl` back to `cash_balance`, write a `trades` row, update `open_interest`.

---

## 4. Backend API surface (FastAPI)

Auth (JWT bearer, see Section 6):
- `POST /auth/signup` `{username, email, password}` → creates user with 10,000 cash, returns JWT
- `POST /auth/login` `{email, password}` → returns JWT
- `GET /auth/me` → current user profile + cash_balance

Market data (all served from Redis/Postgres, never trigger a live external call):
- `GET /market/status` → `{status, next_open_at}` (used to drive the closed-market banner)
- `GET /stocks` → full cached list (from `stocks:latest`), supports `?search=` query param for the trade page's search box
- `GET /stocks/{symbol}` → single stock detail including its `liquidity_tier`, `margin_requirement`, `max_leverage`, `shortable`

Trading (all require auth + all re-check market-open + all caps server-side, regardless of what the client shows):
- `POST /positions/open` → Section 3.3
- `POST /positions/{id}/close` → Section 3.7
- `GET /positions?status=open|closed` → current user's positions
- `GET /trades` → current user's trade history, paginated

Portfolio & social:
- `GET /portfolio` → `{cash_balance, positions_value, total_equity, history: [{captured_at, total_equity}]}` for the dashboard chart (pull from `portfolio_snapshots`)
- `GET /leaderboard?window=all|weekly` → ranked `{username, total_equity, rank}` from `leaderboard:top` cache

Every trading endpoint must independently re-validate market-open status, leverage caps, and open-interest caps server-side — the frontend disabling buttons is a UX nicety, not a security boundary.

---

## 5. Frontend (Next.js, App Router, TypeScript)

Use React Query (or SWR) for data fetching/caching client-side (short `staleTime` aligned to the hourly refresh, e.g. 5 minutes, with background refetch — no need to hammer our own API either). Use Recharts for the portfolio performance chart. Design for both mobile and desktop from the same responsive layout (Tailwind CSS, mobile-first breakpoints); this needs to feel fast — favor server components for static shell, client components only where interactivity (forms, charts, live-ish data) is required, and skeleton loaders everywhere data is fetched instead of blank/jumping layouts.

### 5.1 `/signup` and `/login`
Simple centered card, white background, soft green primary button. Fields: username, email, password (signup); email, password (login). On success, store the returned JWT in `localStorage` under a fixed key (e.g. `lever_token`) with the 30-day expiry baked into the JWT's own `exp` claim (Section 6) — no separate expiry bookkeeping needed client-side, just check `exp` before trusting a stored token on load and redirect to `/login` if expired. On submit click: validate fields client-side → POST to the relevant auth endpoint → on 2xx, store token, redirect to `/`; on error, show inline field-level or toast error without clearing the form.

### 5.2 `/` (Dashboard / Home)
- Top: market status banner — a pill/banner that is soft-green "Market Open · closes 4:00 PM WAT" during trading hours, or gray/muted "Market Closed · opens Monday 9:00 AM WAT" (compute the correct next-open label including skipping weekends) outside them, sourced from `GET /market/status`.
- Portfolio performance chart: line chart of `total_equity` over time from `GET /portfolio`'s `history`, with a summary header showing current total equity, cash balance, and today's/session's % change vs. the first snapshot of the current day.
- Open positions list: each row shows symbol, side (LONG/SHORT badge, green/red), leverage, entry price, current price, unrealized P&L (₦ and %), and a "Close" button that opens the partial-close modal (Section 5.4).
- A prominent floating/pinned "New Trade" button (bottom-right on mobile, top-right on desktop) that navigates to `/trade`. Disabled (grayed, tooltip "Market is closed") when `market.status === "closed"`.

### 5.3 `/trade` — click-by-click
1. Land on `/trade` (optionally `/trade?symbol=DANGCEM` if navigated from a stock elsewhere): a search box at top (autocomplete against `GET /stocks?search=`, debounced) plus a list/grid of stocks below it (sortable by name, % change, sector) for browsing when not searching.
2. **Click a stock** → the search/list collapses into a stock detail panel: symbol, name, current price, day change %, sector, and its liquidity tier badge with max leverage (e.g. "Blue Chip · up to 4×"). If the market is closed, this whole panel shows a disabled state with the closed banner instead of trade controls.
3. **Click "Long" or "Short"** (segmented control/toggle) — Short is disabled with an explanatory tooltip if `shortable === false` (Restricted tier).
4. **Choose leverage** — a slider or stepped selector from 1× up to the stock's `max_leverage`, defaulting to 1× (no leverage). Selecting leverage above 1× shows a small inline note of the resulting margin requirement.
5. **Enter amount** — an NGN amount input (this is the margin being committed), with a live-computed summary directly below updating on every keystroke: resulting notional exposure, estimated shares acquired (at the spread-adjusted execution price), margin required, and estimated liquidation price. Show a clear warning state if the amount exceeds available cash or would breach the position-concentration or open-interest caps (call a lightweight validation, or just validate against cached client-side copies of the caps and let the server be the final authority).
6. **Click "Execute Trade"** → confirmation modal restates the full order summary (symbol, side, leverage, amount, execution price incl. spread, liquidation price) → **click "Confirm"** → `POST /positions/open` → on success, success toast + redirect to `/` with the new position visible; on failure (market closed / cap breached / insufficient cash), show the specific server error inline in the modal without dismissing it, so the user can adjust and retry.

If the user already holds an open position in the selected stock, the panel instead defaults to showing that position with a "Close" action alongside the "Open additional" flow described above, so selling is reachable directly from the stock detail view, not just from the dashboard list.

### 5.4 Close/partial-close modal
Triggered from the dashboard positions list or the trade page. Shows current position (quantity, entry price, current price, unrealized P&L), an amount-or-percentage input for how much to close (default 100%), and a live-updated estimate of realized P&L and cash returned at the spread-adjusted exit price. Click **"Close Position"** (or "Sell") → confirm → `POST /positions/{id}/close` → success toast, position updates or disappears from the list if fully closed.

### 5.5 `/leaderboard`
A ranked table: rank, username, total equity (₦), % return since the ₦10,000 baseline. Highlight the current logged-in user's row if visible on the current page. Simple window toggle (All-time / This week) sourced from `?window=`.

### 5.6 Global elements
- Persistent top nav (or bottom tab bar on mobile): Dashboard, Trade, Leaderboard, Profile.
- The market-closed state must be visible from anywhere a trade could be initiated, not only the dashboard — the `/trade` page's own header should repeat the banner so a user landing there directly still sees it immediately.
- Toasts for all mutation results (trade opened, trade closed, liquidation notice if it happened since last visit, errors).

---

## 6. Authentication
- Passwords hashed with bcrypt (or argon2). Signup requires unique username (3–20 chars, alphanumeric/underscore) and unique email.
- JWT (HS256), payload includes `sub` (user id) and `jwt_version` (matched against the user row's `jwt_version` so changing a password can invalidate old tokens), `exp` set to **30 days** from issuance.
- Frontend stores the raw token string in `localStorage`; every authenticated request attaches `Authorization: Bearer <token>`. On 401 responses, clear the stored token and redirect to `/login`.
- No refresh-token flow is required given the simple 30-day persistence requirement — keep this simple.

---

## 7. Design system
- **Palette:** background `#FFFFFF` (or a near-white off-white like `#FAFAF9` for large surfaces), primary accent a soft green (e.g. `#5FAE7C` / `#EAF6EE` for tints), long/gain states use that same green family, short/loss states use a soft, non-alarming red/coral (e.g. `#E07A6B`) so the palette stays calm rather than "trading terminal aggressive." Neutral grays for secondary text and borders.
- Typography: a clean modern sans (e.g. Inter or similar), generous whitespace, rounded corners on cards/buttons (soft, friendly — not sharp/corporate).
- Charts: minimal gridlines, soft green line/area fill for the portfolio chart, tooltips on hover/tap showing exact ₦ value and timestamp.
- Keep the aesthetic clean and uncluttered — this should feel closer to a modern fintech consumer app than a Bloomberg terminal, despite exposing real trading mechanics.

---

## 8. Non-functional requirements
- Site must be fast: leverage Next.js caching/ISR where sensible for static shell content, keep client bundles lean, lazy-load the charting library, and make sure the stock list/search on `/trade` doesn't refetch on every keystroke (debounce ~250–300ms).
- All monetary values formatted consistently as ₦ with thousands separators, 2 decimal places.
- All timestamps handled in `Africa/Lagos` on the backend for scheduling logic; displayed to users in their local time but clearly labeled with "WAT" for market-hours references so there's no ambiguity about when the NGX opens/closes.
- Environment-based config (`.env`) for the Kobo Terminal API key, JWT secret, database URL, Redis URL — never hardcode secrets.
- Write the liquidity-tier thresholds, spread percentages, and open-interest/order/concentration caps from Sections 3.2, 3.4, and 3.6 as a single, clearly commented config module on the backend so the whole risk model can be tuned in one place without touching business logic.
