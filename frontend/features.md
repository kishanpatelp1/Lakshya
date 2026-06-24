# Frontend Roadmap (Updated)

This document tracks **what is left to build** on frontend in **priority order**.

---

## ✅ Already Implemented (for context)

- Themed app shell with light/dark mode and animated transition
- Command palette (`Cmd/Ctrl + K`) + keyboard navigation
- Global search (`Cmd/Ctrl + J`) with contextual navigation
- Dashboard with live backend widgets + personalization (density + show/hide)
- News & sentiment workspace (ticker-based)
- Filings workspace (search + filter)
- Thematic discovery workspace
- Timeline/feed workspace
- Notifications center + toasts
- Alert rules builder (frontend simulation)
- Favorites/watchlist-style saved items
- Company workspace (per-symbol context)
- Comparison workspace (side-by-side)
- Report generation workspace (title/sections/audience + text export)

---

## 🔴 Priority P0 (Build Next)

### 1) Demo/Mock Mode Toggle (Global)

Status: [x] Completed

**Why now:** Backend auth/config still causes intermittent 401s. Demo mode guarantees stable showcase.

#### Scope
- [x] Global switch: `Live API` / `Demo Data`
- [x] Deterministic mock providers for dashboard, filings, news, sentiment, portfolio, compare, company
- [x] Visual badge showing current data mode
- [x] Keep existing UI flows identical across modes

#### Acceptance
- [x] App is fully usable end-to-end with backend turned off
- [x] No broken panels or empty dead-ends in demo mode

---

### 2) Lakshya Copilot Sessions + Thread History

Status: [x] Completed

**Why now:** Chat is primary differentiator; needs persistent workflow.

#### Scope
- [x] Multiple chat threads
- [x] Rename/delete/pin thread
- [x] Persist threads in local storage
- [x] Quick prompt library sidebar
- [x] Thread search/filter in sidebar

#### Acceptance
- [x] User can leave and return to prior chat sessions without losing context

---

### 3) Report Export Upgrade (PDF)

Status: [x] Completed

**Why now:** Report builder exists; PDF output makes it interview/viva ready.

#### Scope
- [x] PDF export template (cover, summary, risks, financials, themes)
- [x] Two templates: `Retail` and `Analyst`
- [x] Include generation metadata (symbol/date/mode)

#### Acceptance
- [x] Downloaded report opens as professional PDF with consistent formatting

---

## 🟠 Priority P1 (High Value)

### 4) Comparison → Report Workflow

Status: [x] Completed

#### Scope
- [x] Generate report from selected comparison symbols
- [x] Shared insights section: winners/laggards/risk spread
- [x] Auto-open company report workspace prefilled for comparison mode

---

### 5) Company Workspace Deep Data Tabs

Status: [x] Completed

#### Scope
- [x] Replace placeholder tabs with richer data blocks:
  - [x] Filings detail list
  - [x] Sentiment timeline mini-chart
  - [x] Key ratio snapshot
  - [x] Contextual chat prompts tied to active tab

---

### 6) Portfolio Analytics v2 (Chart Library Integration)

Status: [x] Completed

#### Scope
- [x] Integrate proper charting (Recharts/Chart.js)
- [x] Risk vs return scatter
- [x] Sector donut chart
- [x] Drawdown/volatility trends

---

### 7) Alert Rules v2 (Real Rule Engine UX)

#### Scope
- Rule categories + severity levels + schedule frequency
- Trigger history log per rule
- Dry-run simulation panel for each rule

---

## 🟡 Priority P2 (Product Maturity)

### 8) Authentication + Role-Based UI Shell

#### Scope
- Login/signup UI
- Session persistence
- Role-gated views (`Retail`, `Analyst`, `Admin`)

---

### 9) Document Viewer + Citation Highlighting (Frontend Shell)

#### Scope
- PDF viewer panel
- Highlight anchor placeholders for future backend citations

---

### 10) Accessibility + UX Hardening

#### Scope
- Keyboard nav audit for all overlays/drawers
- Focus traps + aria labeling pass
- Contrast + reduced-motion verification

---

## 🟢 Priority P3 (Showcase / Advanced)

### 11) Theme Heatmap Visualization

#### Scope
- Grid/cluster visualization for hot themes
- Company density overlays

---

### 12) Explainability Layer

#### Scope
- “Why this insight?” panel in compare/company/news cards
- Confidence and assumption badges

---

### 13) Real-time Streaming Wiring (when backend-ai is ready)

#### Scope
- Token streaming in chat via WebSocket/SSE
- Progressive render of sections + citation chips

---

## Suggested Build Sequence (short)

1. Demo/Mock Mode Toggle  
2. Chat Sessions  
3. PDF Export  
4. Comparison→Report  
5. Company tabs deepening  
6. Portfolio charts v2
