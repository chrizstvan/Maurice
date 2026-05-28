# Maurice

> *Your personal travel and finance assistant, living in Telegram.*

Maurice watches flight and train prices while you sleep, tracks your spending as you travel, and connects the two — so when that Jakarta→Bali flight finally drops below 500k, it also tells you whether you can actually afford it.

---

## What it does

### Watches prices so you don't have to

Tell Maurice which routes and hotels you care about and what you're willing to pay — directly from Telegram. It checks every few hours and messages you the moment a price drops to your target, with an LLM-generated analysis of the price trend and a booking recommendation grounded in historical data.

```
✈️ Jakarta → Bali

This is the lowest price in 3 weeks — IDR 389,000 vs. an average
of 520,000. The trend has been consistently falling since May 20.
Your target is 500,000 and this comfortably beats it.
Book now: prices typically rise 10–14 days before departure.
```

Flights, trains, and hotels are all supported. Add any route in seconds:

```
/addroute flights CGK DPS 2026-08-15 500000
/addroute trains GMR YK 2026-08-15 350000 EKS
/addroute hotels Bali 2026-08-15 2026-08-20 800000
```

### Reads your receipts

Snap a photo of any receipt and send it. Maurice reads it, names the merchant, guesses the category, and asks for confirmation before logging it. No manual data entry, no spreadsheet to maintain.

```
You: [photo of warung receipt]

Maurice: I see: Warung Bu Tini — IDR 32,000 (Food)
         Add to "Bali Trip"? You've spent 280k on food so far.
         Reply yes to confirm or no to cancel.

You: yes

Maurice: ✓ Added. You're 3 days in with 220k food budget left — pace looks fine.
```

### Understands how Indonesians talk about money

Type expenses the way you'd say them out loud:

```
45k food lunch
2jt rent
150rb transport ojek
```

Maurice parses the shorthand, categorizes it, and asks you to confirm.

### Thinks about your trip holistically

When you check your trip budget, Maurice doesn't just show you numbers — it looks at both your spending pattern *and* the live price data for routes you're monitoring, then gives you a real insight:

```
/trip

Trip: Bali Aug 15–20 (3 days remaining)
Budget: IDR 3,000,000 | Spent: 1,850,000 | Left: 1,150,000

Maurice: You're spending about 380k/day, which puts you slightly over
         pace for a 3-day remaining trip. Transport is your biggest
         category at 800k. The Jakarta→Bali return flight you're
         watching is currently at 412k — still below your 500k target,
         so you have flexibility on the return booking.
```

### Resets your monthly budget automatically

On the 1st of each month, Maurice creates a fresh budget, pre-loads your fixed recurring costs (rent, subscriptions, etc.), and sends you a summary. You start each month knowing exactly how much discretionary budget you actually have.

---

## How it works

Two lightweight processes, one shared brain:

**Price Monitor** runs on GitHub Actions every two hours. It checks configured routes, compares prices to your targets, and records everything to a database. No server needed — free GitHub compute handles it.

**Budget Bot** runs always-on (Render free tier). It listens for Telegram messages, processes receipts and expense entries, and answers commands. When reasoning about a trip budget, it automatically pulls in the price history from the monitor — the two halves talk through the shared database.

The LLM provider is swappable — point it at Anthropic, OpenAI, or Gemini with a single environment variable.

---

## Bot commands

**Price monitoring**

| Command | What it does |
|---------|-------------|
| `/addroute flights CGK DPS 2026-08-15 500000` | Watch a flight route |
| `/addroute trains GMR YK 2026-08-15 350000 EKS` | Watch a train route |
| `/addroute hotels Bali 2026-08-15 2026-08-20 800000` | Watch hotel prices |
| `/routes` | List everything you're watching |
| `/removeroute <id>` | Stop watching a route |

**Budgets & expenses**

| Command | What it does |
|---------|-------------|
| `/budget` | Show your active budget at a glance |
| `/report` | Full breakdown by category + LLM insight |
| `/newtrip Bali 3000000 2026-08-15 2026-08-20` | Create a trip budget |
| `/trip` | Trip summary with current price context |
| `/month` | This month's spending by category |
| `/setbudget 8000000` | Create a monthly budget (pre-loads recurring) |
| `/recurring` | List your fixed monthly costs |
| *(send a photo)* | Read a receipt and log the expense |
| *(type anything)* | Parse a quick expense like `45k food lunch` |

---

## The name

Maurice is named after the idea of a dependable friend who remembers things, watches out for deals, and keeps you honest about money — without being annoying about it.

---

## Tech

Python · Supabase · Telegram Bot API · GitHub Actions · Render · SerpAPI (Flights & Hotels) · KAI · Frankfurter
