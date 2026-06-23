# loops/local/ — project-promoted recipes (SKIN, project-local)

Reusable goal-contract **recipes this project has promoted** from its own successful
`/goal-loop` runs (via `/promote`, Layer-3 human approval). Same shape as `../starter/`
recipes, but authored here rather than shipped by the framework.

## Propagation contract (SKIN)
This directory is **SKIN**: `/apply-framework` **never touches** it. It is namespaced apart
from `../starter/` (CORE, framework-shipped) so that framework updates can add starter
recipes additively without ever colliding with or overwriting a recipe you promoted locally.

This separation is the concrete answer to the past distribution ID-collision lesson:
`starter/` = CORE additive-merge, `local/` = SKIN never-touched.
