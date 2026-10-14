# Runtime performance benchmark

Generated: 2026-10-09T14:38:47.591789+08:00

| Measure | Result |
|---|---:|
| COMSOL queue-equivalent solve median | 18.744 s |
| Direct surrogate median | 3.651 ms |
| Direct surrogate p95 | 4.287 ms |
| Direct surrogate iterations | 300 |
| Direct speedup vs COMSOL | 5134 x |
| Local HTTP median | 29.890 ms |
| Local HTTP p95 | 35.233 ms |
| Local HTTP iterations | 60 |
| HTTP speedup vs COMSOL | 627 x |

The COMSOL value is the median of repeated queue-equivalent LiveLink solves. The surrogate values are repeated measurements on the same workstation. The speedup therefore describes this fixed local case and is not a general COMSOL performance claim.
