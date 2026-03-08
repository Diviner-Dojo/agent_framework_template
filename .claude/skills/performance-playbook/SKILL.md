---
name: performance-playbook
description: "Performance analysis techniques for Python/FastAPI applications. Reference when reviewing performance, optimizing code, or assessing scalability."
---

# Performance Playbook

## Complexity Assessment

### Common Patterns and Their Costs
| Pattern | Time Complexity | Watch For |
|---------|----------------|-----------|
| Single loop over collection | O(n) | Fine for most cases |
| Nested loops | O(n*m) or O(n^2) | Flag if n can be large |
| Loop with lookup in list | O(n*m) | Convert list to set/dict for O(n) |
| Sorting | O(n log n) | Usually acceptable |
| Recursive without memoization | Exponential | Always flag |

### Quick Assessment
For any function, ask:
1. What is n? (size of the main input)
2. How does execution time grow as n increases?
3. Is this on a hot path (called frequently)?

## FastAPI Performance Patterns

### Async Done Right
```python
# Good: async endpoint with async I/O
@router.get("/items")
async def list_items():
    return await db.fetch_all()

# Bad: async endpoint with sync I/O (blocks the event loop)
@router.get("/items")
async def list_items():
    return db.fetch_all_sync()  # This blocks!
```

### Connection Pooling
- Use connection pools for database connections
- Don't create a new connection per request
- Close connections properly (use context managers)

### Response Optimization
- Return only needed fields (don't expose entire DB rows)
- Use pagination for list endpoints
- Consider caching for frequently-read, rarely-changed data

## Database Query Patterns

### N+1 Query Detection
```python
# Bad: N+1 queries
todos = db.get_all_todos()
for todo in todos:
    todo.tags = db.get_tags_for_todo(todo.id)  # N extra queries!

# Good: Single query with join
todos = db.get_all_todos_with_tags()  # JOIN in SQL
```

### Index Usage
- Add indexes on columns used in WHERE clauses
- Add indexes on columns used in ORDER BY
- Add indexes on foreign key columns
- Monitor: if a query does a full table scan on large tables, add an index

## Profiling Techniques

### Built-in Timing
```python
import time
start = time.perf_counter()
result = expensive_operation()
elapsed = time.perf_counter() - start
print(f"Operation took {elapsed:.3f}s")
```

### Memory Profiling (when needed)
```bash
pip install memory-profiler
python -m memory_profiler script.py
```

## Red Flags
- Database queries inside loops
- Loading entire tables into memory
- Synchronous HTTP calls in async contexts
- Unbounded list/query results (no pagination)
- Repeated computation of the same value
- Large objects passed by value instead of reference
