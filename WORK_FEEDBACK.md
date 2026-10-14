# Work Feedback and Logs

Every POST API operation returns a `work_feedback` object.

It contains:

- `action`: operation name
- `status`: success or failed
- `summary`: concise work summary
- `details`: important input/output details
- `next_steps`: recommended follow-up actions

The conversational web UI displays this feedback in the message stream after each operation.

All feedback records are also appended to:

```text
generated/work_logs.jsonl
```

This makes every file read, constraint validation, MATLAB generation, training run, and learning-summary operation traceable.
