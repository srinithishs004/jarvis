# JARVIS OS — Release 1 Acceptance Contract

## Release scope

Release 1 establishes the model-independent JARVIS core:

- FastAPI API
- model/provider abstraction and routing
- orchestrator
- ToolRouter execution boundary
- tool permissions and confirmations
- task lifecycle
- asynchronous worker execution
- cancellation
- global kill switch
- response engine
- persistent task/audit infrastructure
- deterministic API integration coverage

Release 1 does NOT claim support for Windows computer control,
browser automation, voice, vision, personal integrations, or long-term
memory/intelligence workflows.

## Capability matrix

| Capability | Status | Permission | Fallback | Latency target | Failure behavior | Acceptance |
|---|---|---:|---|---|---|---|
| API health | Supported | L0 | None | <1s | HTTP/API error | `/health` succeeds |
| PostgreSQL health | Supported | L0 | None | <5s | DB failure reported | `/health/db` succeeds against configured DB |
| Redis health | Supported | L0 | None | <5s | Redis failure reported | `/health/redis` succeeds against configured Redis |
| Model routing | Supported | N/A | Configured route | Provider dependent | Route/provider error | Valid configured route generates response |
| `/chat` response | Supported | N/A | Clarification | Provider dependent | Invalid decision rejected | Real orchestrator path succeeds |
| `/chat` tool call | Supported | Tool-defined | None | Tool-defined | Router error | Tool executes only through ToolRouter |
| Tool discovery | Supported | N/A | None | <1s | Empty/error response | `/tools` lists registered tools |
| `system.health` | Supported | L0 | None | <1s | Execution error | Tool returns healthy result |
| Confirmation | Supported | Protected tools | User approval | <1s | Confirmation required | Unapproved protected tool cannot execute |
| Async execution | Supported | Tool-defined | Queue failure | Tool-defined | Queue/full/execution error | Task reaches terminal state |
| Task status | Supported | N/A | None | <1s | Task-not-found | `/tasks/{task_id}` returns state |
| Task cancellation | Supported | N/A | None | <1s request | Not-cancellable/task-not-found | Cancellation is persisted |
| Global cancellation | Supported | N/A | None | <1s request | Internal error | Active tasks receive cancellation |
| Kill switch | Supported | Safety control | None | <1s request | Execution blocked | New execution is rejected while active |
| Task recovery | Supported | N/A | Reconciliation | Startup dependent | Recovery failure recorded | Queued tasks are reconciled/recovered |
| Response modes | Supported | N/A | Normal | <1ms | Deterministic fallback | All modes render correctly |
| Malformed model output | Protected | N/A | Reject | Provider dependent | Decision parsing error | No tool execution |
| Unknown tool | Protected | N/A | Reject | <1s | `tool_not_found` | No handler execution |

## Release acceptance criteria

1. Full automated test suite passes.
2. `git diff --check` passes.
3. `/health` succeeds.
4. `/health/db` succeeds against production-configured PostgreSQL.
5. `/health/redis` succeeds against production-configured Redis.
6. `/chat` can produce a normal model response.
7. `/chat` can execute `system.health`.
8. Tool calls cannot bypass ToolRouter.
9. Protected tools cannot execute without confirmation.
10. Kill switch prevents tool execution.
11. Active tasks can be cancelled.
12. Queued tasks survive/reconcile restart conditions.
13. Unknown tools are rejected.
14. Malformed model decisions are rejected without executing tools.
15. Response modes produce deterministic output.
16. At least one configured model route is operational.
17. No secrets are committed to the repository.
18. `git diff --check` is clean.
19. Release documentation does not claim unsupported Windows, browser,
    voice, vision, memory, or personal-integration capabilities.

## Explicitly deferred

The following are outside Release 1 acceptance:

- Windows agent
- desktop/computer control
- browser automation
- media control
- email/calendar integrations
- personal cloud integrations
- long-term conversational memory
- autonomous multi-step personal workflows
- voice input/output
- vision
- multi-device orchestration
- production dashboard
