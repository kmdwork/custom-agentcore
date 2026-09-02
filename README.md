# AgentCore Project

This project was created with the [AgentCore CLI](https://github.com/aws/agentcore-cli).

## Response mode

The current implementation streams responses as Server-Sent Events (SSE).
The earlier working streaming implementation is also preserved in Git tag
`poc-streaming-v1` (commit `803bb65`).

## Project Structure

```
my-project/
├── AGENTS.md               # AI coding assistant context
├── agentcore/
│   ├── agentcore.json      # Project config (agents, memories, credentials, gateways, evaluators)
│   ├── aws-targets.json    # Deployment targets (account + region)
│   ├── .env.local          # Secrets — API keys (gitignored)
│   ├── .llm-context/       # TypeScript type definitions for AI assistants
│   │   ├── agentcore.ts    # AgentCoreProjectSpec types
│   │   ├── aws-targets.ts  # Deployment target types
│   │   └── mcp.ts          # Gateway and MCP tool types
│   └── cdk/                # CDK infrastructure (@aws/agentcore-cdk)
├── app/                    # Agent application code
└── evaluators/             # Custom evaluator code (if any)
```

## Getting Started

### Prerequisites

- **Node.js** 20.x or later
- **Python 3.10+** and **uv** for Python agents ([install uv](https://docs.astral.sh/uv/getting-started/installation/))
- **AWS credentials** configured (`aws configure` or environment variables)
- **Docker** (only for Container build agents)

### Development

Run your agent locally:

```bash
agentcore dev
```

### Deployment

Run the following commands from this project directory (`app/`) after changing
the agent source code or `agentcore/agentcore.json`.

1. Run the MyAgent unit tests:

```bash
app/MyAgent/.venv/bin/python -m unittest discover -s app/MyAgent/tests -v
```

2. Validate the AgentCore project configuration:

```bash
agentcore validate
```

3. Preview the deployment before changing AWS resources. `--dry-run` checks
   what would be deployed, and `--diff` shows the CDK resource differences:

```bash
agentcore deploy --dry-run
agentcore deploy --diff
```

Review the diff carefully when `agentcore/agentcore.json` contains resource
renames or removals. A resource name is its deployment identity, so renaming one
can replace the existing AWS resource.

4. Deploy the application and infrastructure:

```bash
agentcore deploy
```

For a non-interactive deployment after reviewing the diff, use:

```bash
agentcore deploy --yes
```

5. Confirm that the `MyAgent` Runtime and its connected resources are deployed:

```bash
agentcore status --runtime MyAgent
```

6. Perform a basic invocation against the deployed Runtime:

```bash
agentcore invoke --runtime MyAgent --stream "こんにちは"
```

This CLI invocation is a no-memory smoke test and does not reproduce the
Laravel Sanctum authentication flow. After it succeeds, verify the complete
text, image, customer-search, and memory flows from the Laravel application.

If only Python files under `app/MyAgent/` changed, the same workflow still
applies: the CodeZip package must be rebuilt and deployed for the Runtime to use
the new code. Do not edit generated files under `agentcore/cdk/`; make
infrastructure changes in `agentcore/agentcore.json` and deploy them through the
AgentCore CLI.

## Commands

| Command | Description |
| --- | --- |
| `agentcore create` | Create a new AgentCore project |
| `agentcore add` | Add resources (agent, memory, credential, gateway, evaluator, policy) |
| `agentcore remove` | Remove resources |
| `agentcore dev` | Run agent locally with hot-reload |
| `agentcore deploy` | Deploy to AWS via CDK |
| `agentcore status` | Show deployment status |
| `agentcore invoke` | Invoke agent (local or deployed) |
| `agentcore logs` | View agent logs |
| `agentcore traces` | View agent traces |
| `agentcore eval` | Run evaluations |
| `agentcore package` | Package agent artifacts |
| `agentcore validate` | Validate configuration |
| `agentcore pause` | Pause a deployed agent |
| `agentcore resume` | Resume a paused agent |
| `agentcore fetch` | Fetch remote resource definitions |
| `agentcore import` | Import existing resources |
| `agentcore update` | Check for CLI updates |

## Configuration

Edit the JSON files in `agentcore/` to configure your project. See `agentcore/.llm-context/` for type definitions and validation constraints.

The project uses a **flat resource model** — agents, memories, credentials, gateways, evaluators, and policies are top-level arrays in `agentcore.json`. Resources are independent; agents discover memories and credentials at runtime via environment variables or SDK calls.

## Authentication migration note

The working Laravel implementation that uses standard web session authentication
is preserved in the Laravel repository under the Git tag `poc-session-auth-v1`.
Use that tag as the reference point when reviewing or restoring the application
before its migration to Sanctum token authentication.

## Resources

| Resource | Purpose |
| --- | --- |
| Agent (runtime) | HTTP, MCP, or A2A agent deployed to AgentCore Runtime |
| Memory | Persistent context storage with configurable strategies |
| Credential | API key or OAuth credential providers |
| Gateway | MCP gateway that routes tool calls to targets |
| Gateway Target | Tool implementation (Lambda, MCP server, OpenAPI, Smithy, API Gateway) |
| Evaluator | Custom LLM-as-a-Judge or code-based evaluation |
| Online Eval Config | Continuous evaluation pipeline for deployed agents |
| Policy | Cedar authorization policies for gateway tools |

### Agent Types

- **Template agents**: Created from framework templates (Strands, LangChain/LangGraph, GoogleADK, OpenAI Agents, Autogen)
- **BYO agents**: Bring your own code with `agentcore add agent --type byo`
- **Import agents**: Import existing Bedrock agents with `agentcore import`

### Build Types

- **CodeZip**: Python source packaged as a zip and deployed directly to AgentCore Runtime
- **Container**: Docker image built via CodeBuild (ARM64), pushed to ECR, and deployed to AgentCore Runtime

## Documentation

- [AgentCore CLI](https://github.com/aws/agentcore-cli)
- [AgentCore CDK Constructs](https://github.com/aws/agentcore-l3-cdk-constructs)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)


## Public repository configuration

The values committed to `agentcore/agentcore.json` and
`agentcore/aws-targets.json` are public examples. Before deployment, replace
the following values locally with the actual environment settings:

- `https://laravel.example.com/api/agent-tools`
- `s3://example-agentcore-knowledge-base`
- AWS account ID `<AWS_ACCOUNT_ID>`

Do not commit `.env.local`, AgentCore CLI state, deployment logs, traces, or
generated CDK assets. The Laravel tools authenticate with short-lived Sanctum
Bearer tokens; do not place tokens or credentials in `agentcore.json`.
