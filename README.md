# AI-Munim

> The traditional Indian merchant had a *munim* — a bookkeeper who sat in the shop, kept all the ledgers, watched the stock, advised on margins. Modern D2C founders have Excel and vibes. This project is the modern munim: an AI employee for D2C brands that reads across their SaaS tools, answers questions with citations, and proactively flags ₹-saving actions.

> **Status:** scaffolding. Documentation-first, code follows.

---

## What this is

A working v0 of an AI employee for Indian D2C brands. It pulls data from three SaaS sources behind one connector abstraction, normalises it into a universal schema with provenance on every row, exposes a chat layer whose every numerical claim carries a citation back to source rows, runs an autonomous agent that proposes ₹-saving actions, and ships with a scale story for one merchant today to ten thousand tomorrow.

## Documentation

Start with the document that fits your time budget.

| Read | Why | Time |
|---|---|---|
| [`docs/requirements.md`](docs/requirements.md) | The ask, functional and non-functional requirements | 5 min |
| [`docs/research.md`](docs/research.md) | How we picked these 3 connectors, this framework, this agent. Optional but explains the "why". | 10 min |
| [`docs/architecture.md`](docs/architecture.md) | System diagram, schema, citation contract, agent design, scale story | 15 min |

## Quickstart

*(Code coming. Until then, this section is a placeholder.)*

```bash
git clone https://github.com/cyb3rb34s7/AI-Munim.git
cd AI-Munim
# (instructions to follow)
```

## Project layout

```
AI-Munim/
├── README.md                  This file
├── LICENSE                    MIT
├── docs/
│   ├── requirements.md        The ask + FRs + NFRs
│   ├── research.md            Connector/framework landscape, the WHYs
│   └── architecture.md        Stack, schema, flows, citation contract
├── apps/                      Code (coming)
│   ├── api/                   Python: FastAPI + PydanticAI + connectors + agent
│   └── web/                   Next.js + Vercel AI SDK + shadcn/ui
└── docker-compose.yml         (coming)
```

## License

MIT — see [LICENSE](LICENSE).
