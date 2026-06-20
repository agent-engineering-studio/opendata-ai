import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "LangGraph + langchain-mcp-adapters — OpenData AI",
  description:
    "Esempi pratici di un grafo LangGraph che usa i server MCP CKAN, ISTAT e OSM come tool, via langchain-mcp-adapters.",
};

export default function Page() {
  return (
    <article className="container py-5">
      <p className="text-muted small mb-2">
        <Link href="/docs">← Portale Sviluppatori</Link>
      </p>
      <h1>LangGraph + langchain-mcp-adapters</h1>
      <p className="lead">
        LangGraph è la libreria di LangChain per orchestrare agenti come
        grafi di stato. Con <code>langchain-mcp-adapters</code> i tool MCP
        vengono caricati a runtime e diventano nodi <code>ToolNode</code>{" "}
        utilizzabili dal grafo.
      </p>

      <section className="mt-4">
        <h2>Setup</h2>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`pip install langgraph langchain-anthropic langchain-mcp-adapters

# I server MCP devono essere in ascolto (streamable-http):
#   TRANSPORT=streamable-http PORT=8080 ckan-mcp
#   TRANSPORT=streamable-http PORT=8081 istat-mcp
#   TRANSPORT=streamable-http PORT=8082 osm-mcp`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Grafo minimale (singolo MCP)</h2>
        <p>
          <code>MultiServerMCPClient</code> carica i tool da uno o più server
          MCP; il grafo è il classico ReAct loop di LangGraph
          (<code>create_react_agent</code>).
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`import asyncio
from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

async def main() -> None:
    mcp = MultiServerMCPClient(
        {
            "ckan": {
                "transport": "streamable_http",
                "url": "http://localhost:8080/mcp",
            },
        }
    )
    tools = await mcp.get_tools()

    agent = create_react_agent(
        ChatAnthropic(model="claude-haiku-4-5"),
        tools,
        prompt=(
            "Sei un assistente per i portali CKAN italiani. "
            "Usa il tool package_search per cercare dataset su dati.gov.it."
        ),
    )
    out = await agent.ainvoke({
        "messages": [("user", "Dataset sulla qualità dell'aria a Milano")]
    })
    print(out["messages"][-1].content)

asyncio.run(main())`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Multi-MCP (CKAN + ISTAT + OSM)</h2>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`import asyncio
from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

CONFIG = {
    "ckan":  {"transport": "streamable_http", "url": "http://localhost:8080/mcp"},
    "istat": {"transport": "streamable_http", "url": "http://localhost:8081/mcp"},
    "osm":   {"transport": "streamable_http", "url": "http://localhost:8082/mcp"},
}

PROMPT = (
    "Sei un agente per open data italiani ed europei.\\n"
    "- usa il prefisso ckan_* per i portali CKAN (default dati.gov.it),\\n"
    "- usa il prefisso istat_* per SDMX 2.1 (ISTAT, Eurostat e OCSE),\\n"
    "- usa il prefisso osm_* per geocoding/POI/routing.\\n"
    "Cita sempre la fonte di ogni risorsa."
)

async def main() -> None:
    mcp = MultiServerMCPClient(CONFIG)
    tools = await mcp.get_tools()

    agent = create_react_agent(
        ChatAnthropic(model="claude-sonnet-4-6"),
        tools,
        prompt=PROMPT,
    )
    out = await agent.ainvoke({
        "messages": [(
            "user",
            "Confronta la spesa sanitaria pro capite Italia vs Germania "
            "negli ultimi 5 anni e cita i dataflow Eurostat usati.",
        )],
    })
    for m in out["messages"]:
        print(m.type, ":", m.content[:300])

asyncio.run(main())`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Streaming degli step</h2>
        <p>
          Per mostrare gli step intermedi (chiamate ai tool) usa{" "}
          <code>astream_events</code>:
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`async for event in agent.astream_events(
    {"messages": [("user", "qualità aria a Milano")]},
    version="v2",
):
    kind = event["event"]
    if kind == "on_tool_start":
        print(f"  ↳ tool {event['name']} input={event['data'].get('input')}")
    elif kind == "on_chat_model_stream":
        chunk = event["data"]["chunk"]
        if chunk.content:
            print(chunk.content, end="", flush=True)`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Grafo personalizzato (oltre il ReAct)</h2>
        <p>
          Per controllare il routing tra fonti puoi costruire il grafo a
          mano. Esempio: un nodo &ldquo;classifier&rdquo; che decide CKAN vs
          ISTAT, e poi due rami paralleli.
        </p>
        <pre
          className="bg-light border rounded p-3 small font-monospace"
          style={{ overflowX: "auto", whiteSpace: "pre" }}
        >
{`from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

class State(TypedDict):
    messages: Annotated[list, add_messages]
    next: str  # "ckan" | "istat" | "synth"

# ...definisci classifier(), synth() come funzioni che leggono state["messages"]
# e producono una nuova lista di messaggi.

graph = StateGraph(State)
graph.add_node("classifier", classifier)
graph.add_node("ckan_tools", ToolNode(ckan_tools))
graph.add_node("istat_tools", ToolNode(istat_tools))
graph.add_node("synth", synth)

graph.set_entry_point("classifier")
graph.add_conditional_edges(
    "classifier",
    lambda s: s["next"],
    {"ckan": "ckan_tools", "istat": "istat_tools"},
)
graph.add_edge("ckan_tools", "synth")
graph.add_edge("istat_tools", "synth")
graph.add_edge("synth", END)

app = graph.compile()`}
        </pre>
      </section>

      <section className="mt-4">
        <h2>Note operative</h2>
        <ul>
          <li>
            <strong>Tool naming</strong>: i tool ricevono il prefisso del
            server nel grafo (es. <code>ckan_package_search</code>). Sfrutta
            il prefisso nel prompt per guidare l&apos;agente.
          </li>
          <li>
            <strong>Persistenza</strong>: per uno stato a lunga vita aggiungi
            un <code>checkpointer</code> (es. SQLite o Postgres) al{" "}
            <code>compile()</code> del grafo.
          </li>
          <li>
            <strong>Provider</strong>: <code>ChatAnthropic</code> è un
            esempio. Funziona con <code>ChatOpenAI</code>,{" "}
            <code>ChatOllama</code> e qualunque chat-model compatibile
            LangChain con tool-calling.
          </li>
        </ul>
      </section>
    </article>
  );
}
