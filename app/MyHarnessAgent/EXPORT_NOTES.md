# Export Notes — MyHarness → MyHarnessAgent

Exported on: 2026-09-07
Strands version: strands-agents >= 1.15.0
Source harness: agentcore/app/MyHarness/harness.json
Generated agent: app/MyHarnessAgent/

## Items requiring manual follow-up

### Browser tool requires Container build — excluded from CodeZip export
The browser tool requires a Container build to run. In a CodeZip (Lambda-style) runtime the Playwright node driver cannot be executed and the tool will fail at invocation time.

Re-export with `--build Container` to include browser tool support:

  agentcore export harness --name MyHarness --target-agent-name MyHarnessAgent --build Container
