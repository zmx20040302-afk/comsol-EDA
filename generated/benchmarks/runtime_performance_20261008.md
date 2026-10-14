# Runtime performance benchmark

Generated: 2026-10-08T11:33:44.827259+08:00

| Measure | Result |
|---|---:|
| COMSOL queue solve | 47.735 s |
| Direct surrogate median | 7.563 ms |
| Direct surrogate p95 | 13.439 ms |
| Direct surrogate iterations | 300 |
| Direct speedup vs COMSOL | 6312 x |
| Local HTTP median | 35.380 ms |
| Local HTTP p95 | 48.029 ms |
| Local HTTP iterations | 60 |
| HTTP speedup vs COMSOL | 1349 x |

The COMSOL value is one recorded queue solve and is a functional reference. The surrogate values are repeated measurements on the same workstation. The speedup therefore describes this fixed local case and is not a general COMSOL performance claim.
