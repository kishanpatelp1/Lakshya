# Shared Module Scaffold

Target shared locations during frontend refactor:

- `shared/api/` (split from `lib/api.ts`)
- `shared/types/` (cross-feature type definitions)
- `shared/ui/` (reusable components)
- `shared/utils/` (pure helpers)

This is a scaffold-only change to support incremental extraction from `App.tsx`.

## Current shared API split

- `shared/types/api.ts` - API request/response contracts
- `shared/api/core.ts` - base URL, error type, generic HTTP helpers
- `shared/api/external.ts` - market/news/external provider wrappers
- `shared/api/platform.ts` - chat/companies/portfolio/timeline/watchlist APIs
- `shared/api/user.ts` - profile/KYC APIs

`src/lib/api.ts` remains as a compatibility re-export layer during migration.
