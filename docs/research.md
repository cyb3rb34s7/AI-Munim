# Research

> Optional read. This document is the trail of evidence behind the choices in [`architecture.md`](architecture.md). If a reviewer ever asks *"why this and not that?"*, the answer is in here.

---

## 1. The D2C founder's stack

A typical Indian D2C brand at ₹50L–5Cr ARR runs 6–10 SaaS tools. Talking to a few founders and reading the public ecosystem map, the recurring stack looks like:

| Layer | Tool | What it owns |
|---|---|---|
| Storefront | **Shopify** (dominant), WooCommerce, Magento | Orders, customers, products, inventory |
| Acquisition | **Meta Ads** (largest spend), Google Ads, influencer platforms | Ad spend, campaign performance, attribution |
| Fulfilment | **Shiprocket** (dominant aggregator), Delhivery, BlueDart direct | Shipments, RTO/RTS, COD remittance, pincode coverage |
| Payments | **Razorpay** (dominant in India), Cashfree, PayU | Captures, refunds, settlements, disputes |
| Marketing engagement | Klaviyo, WebEngage, MoEngage, WhatsApp tools (Wati, Interakt) | Email/SMS/WhatsApp campaigns, segments |
| Reviews | Judge.me, Yotpo | Product reviews, UGC |
| Support | Freshdesk, Zoho Desk, Gorgias | Tickets, customer comms |
| Accounting | Tally, Zoho Books, QuickBooks | Books, GST filing |
| BI / dashboards | Looker Studio (free), TripleWhale (paid), spreadsheets | Cross-tool analytics |

The founder's painful cross-tool questions almost always touch three of these four layers: **storefront × acquisition × fulfilment × payments**. That observation is the foundation of our connector choice.

## 2. Connector landscape research

We evaluated every candidate against four practical questions:

1. Does it have an official MCP server (Model Context Protocol)? An MCP lets an LLM agent call the tool directly with structured tool definitions, which speeds integration and signals modern AI engineering.
2. Is sandbox / test access available without heavy KYC? We need to actually build and run during a 5-day window.
3. Is it representative of the Indian D2C reality? Stripe is dominant globally but not in India. Shiprocket is dominant in India but unknown abroad. Context matters.
4. Does it answer one of the founder's killer cross-tool questions when combined with the other two?

### 2.1. The full landscape we considered

| Tool | Official MCP? | Sandbox? | KYC for sandbox? | Verdict |
|---|---|---|---|---|
| **Shopify** | Yes — *Storefront MCP* + *Dev MCP* | Free dev store, instant | No | **Pick.** Universal D2C foundation. |
| **Meta Ads** | Yes — official, shipped 29 April 2026, 29 tools, OAuth | Yes, free | No (existing FB Business Manager) | **Pick.** Where Indian D2C spends most acquisition rupees. |
| **Shiprocket** | Yes — `github.com/bfrs/shiprocket-mcp` (BFRS = Bigfoot Retail Solutions, Shiprocket's parent) | No public sandbox per Shiprocket's own docs, but live API access on free signup | Aadhaar OTP, automated, 10 minutes | **Pick.** Indian fulfilment reality; signals understanding of the employer's product. |
| Razorpay | No MCP yet | Yes, instant test mode | No | Strong stretch. Test mode is easy. No MCP makes it more work for less unique signal than Shiprocket. Held as a stretch goal. |
| Stripe | Yes — official, in `stripe/ai` agent toolkit | Yes | Stripe India is **invite-only** for Indian businesses (confirmed 2025–2026) | **Drop.** Indian merchants cannot reliably use Stripe. Wrong choice for the persona. |
| Klaviyo | Yes — official | Yes, free tier | No | Pass. Engagement is downstream of acquisition; it answers a different class of question (retention, not unit economics). |
| Google Ads | No first-party MCP; community tools | Yes | Ad account setup is friction | Pass in favour of Meta Ads (larger Indian D2C spend share). |
| WooCommerce | No first-party MCP | Self-hosted, free | None | Pass. Shopify dominates Indian D2C; same problem, less signal. |
| Cashfree | No MCP | Yes | None | Pass. Razorpay covers the payments slot if needed. |
| Delhivery direct | No first-party MCP | Limited | Heavy | Pass. Shiprocket aggregates Delhivery and others. |

### 2.2. Why exactly these three: Shopify × Meta × Shiprocket

These three are not independent picks. They compose into the **founder's #1 cross-tool question**:

> *"Are my Meta campaigns actually profitable after I account for RTO losses?"*

Decomposed:

- **Shopify** tells us the order existed and how much it was worth.
- **Meta Ads** tells us which campaign brought the customer and what we spent to acquire them.
- **Shiprocket** tells us whether the order was actually delivered, or whether it returned to origin, or whether the COD was refused.

Without all three, the founder cannot compute true ROAS. Triple Whale and Northbeam charge $149–2,500/month to answer this in the global market. No good open primitive exists in the Indian-D2C-aware shape. That gap, plus the relevance to Shiprocket itself, is the entire argument for this trinity.

### 2.3. The Shiprocket-aware play

`bfrs/shiprocket-mcp` exists. The `bfrs` GitHub org is **Bigfoot Retail Solutions Pvt Ltd**, Shiprocket's legal parent (confirmed via Shiprocket's own merchant agreement and information-security policy documents). So Shiprocket's engineering team has an official MCP.

We are not duplicating it. The `bfrs/shiprocket-mcp` is a passthrough wrapper for live Shiprocket operations (create order, fetch rates, schedule pickup). Useful for live actions, not for cross-tool analytics.

Our system has a different job:

- Pull historical Shiprocket data into a universal schema with provenance.
- Combine it with Shopify and Meta data.
- Answer questions that no single MCP server can answer alone.
- Optionally expose **our** unified data as our own MCP server, so any MCP client (Claude Desktop, Cursor, an A2A agent) can query across sources.

So we use the existing official MCP where appropriate, and build the layer above it.

## 3. Agent framework research

The chat layer and the autonomous agent are the same conceptual primitive: a loop that calls tools, observes results, decides what to do next. We evaluated the obvious frameworks.

| Framework | What it is | Fit for this project |
|---|---|---|
| **LangGraph** (LangChain) | Stateful graph of LLM/tool nodes. Mature. LangSmith observability. | Pass. Heavy ecosystem dependency. Magic abstractions hide the citation contract — exactly the part we want visible to the evaluator. |
| **CrewAI** | Multi-agent collaboration framework. Designed around "crews" of role-based agents. | Pass. We have one agent and one chat. Crew metaphor adds ceremony without benefit. |
| **OpenAI Agents SDK** | Lightweight first-party agent loop with tracing. | Close. But primarily designed for OpenAI; provider-agnostic use is a workaround, not native. |
| **Anthropic SDK alone** | Native tool use; no loop framework. | We'd be reinventing PydanticAI on top of it. |
| **PydanticAI** | Pydantic-first agent framework. Provider-agnostic by design (OpenAI, Anthropic, Gemini, Groq, Mistral, Cohere, Ollama). Tools are typed Python functions. Structured outputs return Pydantic objects. Native MCP support. | **Pick.** Type discipline matches our citation contract one-to-one. Provider abstraction satisfies the user's "no lock-in" requirement out of the box. Lightweight; judges see our code, not the framework's. |
| **Hermes Agent** (NousResearch) | Self-improving generalist agent. ~17k stars, MIT. Built-in cron, tool registry, provider adapters. | Pass as a dependency, **borrow as inspiration.** Hermes is a generalist personal agent (70+ tools, 28 toolsets, ACP integration, RL training, multi-channel gateway). Importing it would obscure our domain code. The patterns we adopt: cron as a first-class data flow, tool registry, observable execution, loose coupling. |
| **Custom from scratch** | Hand-rolled tool-use loop on top of the provider SDKs. | Plan B. PydanticAI saves a few hundred lines of boilerplate without locking us in. |

Decision: **PydanticAI for the agent and chat loops; design inspired by Hermes Agent's architecture (acknowledged in the README and the architecture doc).**

## 4. UI and streaming research

The brief does not demand a particular UI surface, but the system must be demonstrable. A polished chat with inline citations, streamed responses, and generative artifacts (tables, charts, action cards) communicates the citation contract far better than CSV dumps in a terminal.

### 4.1. Vercel AI SDK

Mature TypeScript toolkit (`ai-sdk.dev`). Stream protocol, tool calling, generative UI hooks (`useChat`, `streamText`, `streamObject`). Vercel maintains an **official template** for AI SDK chat backed by a Python FastAPI streaming endpoint, so a hybrid stack is first-class supported. We use AI SDK on the Next.js side; the FastAPI side streams using AI SDK's Data Stream Protocol.

### 4.2. A2UI (Google)

Google announced **A2UI** on 15 December 2025. v0.9 shipped 17 April 2026. It is an open spec for *agent-driven generative UI*: agents emit a declarative UI tree, the host platform renders it via the host's existing design system. Cross-platform, framework-agnostic, with a streaming protocol.

A2UI's central idea is the right one: separate *what the agent wants to show* from *how the host renders it*. That decoupling is exactly what we want for citations and artifacts.

For v0 we are not implementing the full A2UI v0.9 spec — it would consume too much of our window. We are taking the **concept**: every chat tool returns not just data and citations but a typed `render` spec (e.g. `{type: "rto_action_card", props: {...}}`). The frontend has a renderer registry that maps these specs to React components built on shadcn/ui. This is A2UI-shaped and gives us a forward-compatible escape hatch.

### 4.3. Generative UI inside the chat

Following the pattern Claude.ai's artifacts established and Vercel AI SDK's `streamUI` hook formalised: tools can emit React components inline. We use this for tables (query results), charts (campaign ROAS, RTO rates per pincode), and structured action cards (the agent's RTO mitigation proposals).

## 5. Stack decision: why hybrid Python + TypeScript

| Option | Pros | Cons |
|---|---|---|
| **Hybrid: FastAPI (Python) + Next.js (TypeScript)** | Best LLM ecosystem (PydanticAI, MCP Python SDK, Pydantic schema discipline). Best UI ecosystem (shadcn, AI SDK, generative UI). Vercel officially supports this pattern. | Two languages. Slightly more setup. Mitigated by a monorepo and one `docker-compose up`. |
| Full TypeScript (Next.js everywhere) | One language. Cleaner deploy. AI SDK is excellent. | LLM ecosystem in TS is younger; MCP TS SDK is fine but Python's is more mature; would lose PydanticAI's structured outputs for the citation contract. |
| Full Python (Streamlit or Reflex) | One language. Fastest backend ship. | UI suffers. Streamlit cannot do A2UI-shaped artifacts with the polish needed to communicate the citation contract. |

**Pick: hybrid.** The polyglot signal reads as senior engineering, not as overcomplicated. Both halves use the best tool for their job.

## 6. Prior art in this space

We checked what already exists in the D2C analytics + AI space so we don't reinvent and so we can position our work honestly.

| Tool | Source | What it does | Why we're not duplicating |
|---|---|---|---|
| **Triple Whale** | Closed source, $149–2,500/mo | Shopify + Meta + Google + Klaviyo attribution. US-focused. | Closed, US-centric, expensive. No RTO awareness. |
| **Northbeam** | Closed source, premium tier | Attribution and incrementality. | Closed, attribution-only. |
| **Lebesgue** | Closed source | AI-driven Shopify analytics. | Closed. Different problem framing. |
| **Lifesight** | Closed source | Attribution + measurement. | Closed, attribution-only. |
| **Polar** | Closed source | D2C BI dashboard. | Closed. Dashboard, not agent. |
| **TrueProfit** | Closed source, Shopify-first | Profit dashboard for Shopify stores. | Closed. No agent. |
| **OpenAgents / Hermes / agent-zero etc.** | Open source generalist agents | General assistants. | Generalist; no domain schema, no D2C connectors. |
| **Airbyte / Fivetran** | Open source data movers | Pulling SaaS data into warehouses. | Pure ETL. No AI layer, no chat, no agent. |

**The gap is real.** There is no open-source AI-employee primitive for Indian D2C. That is what we are building — knowingly small, knowingly v0, but it is a primitive that does not yet exist.

## 7. RTO economics (for the agent's case)

Why the autonomous agent is an RTO Risk Mitigator and not something else.

- COD share of Indian D2C orders: **40–60%**. Source: Shiprocket and others' public reports; consistent across operators.
- RTO rates on COD orders: **15–25% baseline**, can spike to **40% for new brands** without trust signals. Sources: Shiprocket, WareIQ, Qikink industry posts (2025–2026).
- Cost per RTO to the seller: **₹150–300** end-to-end (forward shipping + reverse shipping + packaging waste + handling + amortised damage).
- For a brand doing 1,000 COD orders/month at ₹500 AOV and 20% RTO, monthly RTO bleed is **₹30,000–60,000** — roughly the salary of a junior operator, every month.

Implications for the agent:

- Even a modest improvement (intercept 25% of high-risk orders and convert to prepaid) is a six-figure annual saving. The agent's reason for existing is concrete, measurable, and Indian-D2C-specific.
- The data needed (customer history, pincode RTO rate, order value, time-of-order) crosses Shopify and Shiprocket — proving the universal schema is worth the work.
- The action space (convert to prepaid, confirmation call, no action) is small and bounded, which makes the run log easy to read.

A "True ROAS Watcher" agent is the obvious second candidate (using Meta + Shopify + Shiprocket). If time permits in week 1, we add it as the second skill. For v0 the RTO Mitigator is enough.

## 8. The few things we deliberately did not research

- **CDP / customer data platform integrations** (Segment, Rudderstack). Out of scope for a v0 focused on cross-tool analytics with citations.
- **Causal inference for attribution.** Northbeam/Triple Whale spend years on this. Not a v0 problem.
- **A2A protocol** (Google's Agent-to-Agent). Our scope is one merchant's data, not inter-agent coordination. Mentioned only as a future surface for our MCP server.
- **Fine-tuned domain models.** Off-the-shelf frontier models with good tool definitions are sufficient at this scale.

---

## Sources cited in this document

- Shopify Storefront MCP: `shopify.dev/docs/apps/build/storefront-mcp`
- Shopify Dev MCP: `shopify.dev/docs/apps/build/devmcp`
- Meta Ads official MCP, shipped 29 April 2026: `mcp.directory/blog/meta-ads-cli-mcp`
- Shiprocket MCP by BFRS: `github.com/bfrs/shiprocket-mcp`
- Stripe MCP: `docs.stripe.com/mcp`
- A2UI announcement: `developers.googleblog.com/introducing-a2ui-an-open-project-for-agent-driven-interfaces`
- A2UI v0.9: `developers.googleblog.com/a2ui-v0-9-generative-ui/`
- Hermes Agent architecture: `hermes-agent.nousresearch.com/docs/developer-guide/architecture`
- Vercel AI SDK + Python streaming template: `vercel.com/templates/next.js/ai-sdk-python-streaming`
- Stripe India invite-only status confirmed via `r/stripe` discussions and Stripe support docs, 2025–2026.
- RTO economics from Shiprocket's own blog, WareIQ, and Qikink (2025–2026).
- BFRS = Bigfoot Retail Solutions Pvt Ltd confirmed via Shiprocket's merchant agreement document (S3 hosted) and information security policy (linked from `shiprocket.in`).
