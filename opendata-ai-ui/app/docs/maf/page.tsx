import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Microsoft Agent Framework (MAF) — OpenData AI",
  description:
    "Esempi pratici per costruire un agente che usa i server MCP OpenData AI dal Microsoft Agent Framework (agent-framework), via transport streamable-http.",
};

export default function Page() {
  return (
    <article className="container py-5">
      <p className="text-muted small mb-2">
        <Link href="/docs">← Documentazione</Link>
      </p>
      <h1>Microsoft Agent Framework (MAF)</h1>
      <p className="lead">
        Il backend di OpenData AI usa già il <code>agent-framework</code>{" "}
        Microsoft sotto al cofano. Questo significa che puoi costruire un
        agente locale che riusa esattamente gli stessi MCP server (CKAN,
        ISTAT, OSM) con poche righe di codice.
      </p>

      <section className="mt-4">
        <h2>Setup</h2>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`# agent-framework è pubblicato come pre-release: serve --pre
pip install --pre agent-framework anthropic

# Avvia i tre MCP server in altre shell (vedi /docs/mcp):
#   TRANSPORT=streamable-http PORT=8080 ckan-mcp
#   TRANSPORT=streamable-http PORT=8081 istat-mcp
#   TRANSPORT=streamable-http PORT=8082 osm-mcp`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Agente con un singolo MCP (CKAN)</h2>
        <p>
          Il pattern minimo: un <code>ChatAgent</code> che usa Claude come
          modello e <code>MCPStreamableHTTPTool</code> per collegarsi al
          server CKAN.
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`import asyncio
from agent_framework import ChatAgent
from agent_framework.anthropic import AnthropicChatClient
from agent_framework.mcp import MCPStreamableHTTPTool

CKAN_MCP_URL = "http://localhost:8080/mcp"
SYSTEM = (
    "Sei un assistente specializzato nei portali CKAN italiani. "
    "Usa il tool package_search per cercare dataset su dati.gov.it. "
    "Rispondi in italiano con un elenco numerato delle risorse trovate."
)

async def main() -> None:
    async with MCPStreamableHTTPTool(name="ckan", url=CKAN_MCP_URL) as ckan:
        agent = ChatAgent(
            chat_client=AnthropicChatClient(model="claude-haiku-4-5"),
            instructions=SYSTEM,
            tools=[ckan],
        )
        reply = await agent.run("Cerca dataset sulla qualità dell'aria a Milano")
        print(reply.text)

asyncio.run(main())`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Multi-MCP: CKAN + ISTAT + OSM</h2>
        <p>
          Stesso pattern, più tool. L&apos;agente decide a quale server
          chiedere in base al system prompt e al contenuto della domanda.
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`import asyncio
from contextlib import AsyncExitStack
from agent_framework import ChatAgent
from agent_framework.anthropic import AnthropicChatClient
from agent_framework.mcp import MCPStreamableHTTPTool

MCPS = {
    "ckan":  "http://localhost:8080/mcp",
    "istat": "http://localhost:8081/mcp",
    "osm":   "http://localhost:8082/mcp",
}

async def main() -> None:
    async with AsyncExitStack() as stack:
        tools = [
            await stack.enter_async_context(
                MCPStreamableHTTPTool(name=name, url=url)
            )
            for name, url in MCPS.items()
        ]
        agent = ChatAgent(
            chat_client=AnthropicChatClient(model="claude-sonnet-4-6"),
            instructions=(
                "Sei un agente per open data italiani ed europei. "
                "Usa il tool 'ckan' per portali CKAN, 'istat' per SDMX "
                "(ISTAT/Eurostat/OCSE) e 'osm' per dati geografici. "
                "Includi sempre il portale/agency di origine quando citi una risorsa."
            ),
            tools=tools,
        )
        reply = await agent.run(
            "Confronta la popolazione di Milano nel 2024 tra ISTAT ed Eurostat, "
            "e disegna i confini comunali su una mappa."
        )
        print(reply.text)

asyncio.run(main())`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Streaming dei tool</h2>
        <p>
          Per rispondere in streaming (utile in app o CLI interattive) usa{" "}
          <code>agent.run_streaming(...)</code>:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`async for chunk in agent.run_streaming("Quali dataset ISTAT sul mercato del lavoro?"):
    if chunk.delta_text:
        print(chunk.delta_text, end="", flush=True)
    if chunk.tool_calls:
        for tc in chunk.tool_calls:
            print(f"\\n  ↳ tool {tc.name}({tc.arguments})")`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Note operative</h2>
        <ul>
          <li>
            <strong>Pre-release pinning</strong>: <code>agent-framework</code>{" "}
            è pubblicato come pre-release. <code>pip install --pre</code> è
            necessario, e in CI conviene fissare la versione esatta.
          </li>
          <li>
            <strong>Hostnames in Docker</strong>: dentro al docker-compose
            usa i nomi servizio (<code>http://ckan-mcp:8080/mcp</code>); da
            host usa <code>localhost</code>.
          </li>
          <li>
            <strong>Provider alternativo</strong>: se non hai una chiave
            Anthropic, sostituisci <code>AnthropicChatClient</code> con il
            client Azure Foundry o Ollama (l&apos;SDK supporta i tre).
          </li>
          <li>
            <strong>Rate limit del backend</strong>: questo esempio chiama
            direttamente i server MCP, quindi non passa per i rate limit del
            backend OpenData AI. Se invece consumi l&apos;endpoint REST
            <code>/datasets/search</code> il limite è 60 req/min/utente —
            vedi <Link href="/docs/rate-limits">/docs/rate-limits</Link>.
          </li>
        </ul>
      </section>
    </article>
  );
}
