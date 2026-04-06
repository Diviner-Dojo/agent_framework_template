# Solution-Path Taxonomy

## Compound Tag Format

Solution paths use compound tags in the format `domain/sub-concept` to enable precise cross-project lookup. Tags are hierarchical — searching for `auth` finds all `auth/*` entries; searching for `auth/session-management` finds only that specific sub-concept.

### Format

```
[domain/sub-concept]
```

### Examples

```
auth/session-management
auth/oauth-integration
auth/role-based-access

api/rate-limiting
api/versioning
api/error-handling

data/migration-strategy
data/caching-layer
data/search-indexing

ui/state-management
ui/form-validation
ui/accessibility

infra/deployment-pipeline
infra/monitoring
infra/secret-management

testing/integration-strategy
testing/mock-boundaries
testing/fixture-patterns
```

## Usage Rules

1. **Use existing tags when possible** — check this file before creating new ones.
2. **Domain is the broad category**, sub-concept is the specific problem area.
3. **Tags are lowercase**, words separated by hyphens within each level.
4. **Multiple tags per solution path** — a solution often spans domains (e.g., `auth/session-management` + `security/token-handling`).
5. **New tags are welcome** — add them to the examples above when you introduce them, so future searches find them.

## Searching Solution Paths

```bash
# Find all auth-related solution paths across all projects
grep -ri "auth/" memory/projects/

# Find a specific sub-concept
grep -ri "auth/session-management" memory/projects/

# Find all solution paths for a domain
grep -ri "\[.*data/.*\]" memory/projects/
```

## Forgetting Curve

Solution paths are subject to a 90/180-day forgetting curve:
- **90 days**: Solution paths without recent references are flagged for review.
- **180 days**: Unflagged entries may be archived to `memory/archive/`.

This prevents the knowledge base from accumulating stale advice. Active, referenced solution paths persist indefinitely.
