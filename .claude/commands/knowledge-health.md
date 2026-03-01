---
description: "Run the knowledge pipeline dashboard. Reports on capture, extraction, pattern mining, Layer 3 health, promotion throughput, agent effectiveness, and adoption log status."
allowed-tools: ["Bash", "Read"]
---

# Knowledge Pipeline Dashboard

Run the knowledge pipeline health dashboard to assess the state of all pipeline layers.

## Step 1: Run Dashboard

```bash
python scripts/knowledge_dashboard.py
```

## Step 2: Interpret Results

Present the dashboard output to the developer, highlighting:

1. **Health Score**: Overall pipeline health (0-7 scale)
2. **Gaps**: Any section scoring zero (pipeline stage not yet active)
3. **Trends**: Compare to previous runs in `metrics/knowledge_pipeline_log.jsonl` if available
4. **Action Items**: Suggest specific actions for low-scoring areas:
   - Low capture → Are discussions being created for reviews/builds?
   - Low extraction → Run `python scripts/backfill_findings.py`
   - Low mining → Run `python scripts/mine_patterns.py`
   - Empty Layer 3 → Run `/promote` on pending candidates
   - No effectiveness data → Run `python scripts/compute_agent_effectiveness.py --all`
   - High pending adoptions → Run `/batch-evaluate`

## Step 3: Trend Analysis (if data available)

If `metrics/knowledge_pipeline_log.jsonl` has 2+ entries:

```bash
python -c "
import json, pathlib
log = pathlib.Path('metrics/knowledge_pipeline_log.jsonl')
if log.exists():
    entries = [json.loads(l) for l in log.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
    if len(entries) >= 2:
        prev, curr = entries[-2], entries[-1]
        print('=== Trend (last 2 runs) ===')
        for key in ['health_score']:
            p, c = prev.get(key, 0), curr.get(key, 0)
            delta = c - p
            arrow = '↑' if delta > 0 else '↓' if delta < 0 else '→'
            print(f'  {key}: {p} → {c} ({arrow}{abs(delta)})')
    else:
        print('Only 1 entry — trend analysis available after 2+ runs.')
else:
    print('No trend log yet — will be created on first dashboard run.')
"
```
