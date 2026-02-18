# Session Context

## User Prompts

### Prompt 1

Look at the last 12 hours of latencty for spans from: `env:prod service:devtoolscrape @span.kind:client resource_name:classifier.batch` in Datadog. Look how high it is! It's gone up significantly over the last two weeks or so. I can't figure out why the latency has increased so much. Can you help me troubleshoot?

### Prompt 2

Span count is unchanged, latency is up ~4x

### Prompt 3

Let's implement option 2. Make sure to write tests for any functionality that changes. Make sure all tests pass. Read @PYTHON.md before you begin.

### Prompt 4

This session is being continued from a previous conversation that ran out of context. The summary below covers the earlier portion of the conversation.

Analysis:
Let me chronologically analyze the conversation:

1. **First message**: User asked to look at Datadog latency for spans matching `env:prod service:devtoolscrape @span.kind:client resource_name:classifier.batch` over the last 12 hours, noting it had gone up significantly over the last two weeks.

2. **My initial investigation**: I check...

