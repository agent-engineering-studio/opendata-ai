import { Fragment } from "react";
import { TextPreview } from "./TextPreview";

const TOKEN_RE =
  /("(?:\\.|[^"\\])*")(\s*:)?|(\b-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|(\btrue\b|\bfalse\b)|(\bnull\b)/g;

function tokenize(pretty: string) {
  const nodes: React.ReactNode[] = [];
  let lastIndex = 0;
  let i = 0;
  for (const m of pretty.matchAll(TOKEN_RE)) {
    const start = m.index ?? 0;
    if (start > lastIndex) {
      nodes.push(<Fragment key={`t${i++}`}>{pretty.slice(lastIndex, start)}</Fragment>);
    }
    const [, strLit, isKey, num, bool, nul] = m;
    if (strLit !== undefined) {
      if (isKey) {
        nodes.push(
          <span key={`k${i++}`} className="json-key">
            {strLit}
          </span>,
          <Fragment key={`c${i++}`}>{isKey}</Fragment>,
        );
      } else {
        nodes.push(
          <span key={`s${i++}`} className="json-string">
            {strLit}
          </span>,
        );
      }
    } else if (num !== undefined) {
      nodes.push(
        <span key={`n${i++}`} className="json-number">
          {num}
        </span>,
      );
    } else if (bool !== undefined) {
      nodes.push(
        <span key={`b${i++}`} className="json-boolean">
          {bool}
        </span>,
      );
    } else if (nul !== undefined) {
      nodes.push(
        <span key={`x${i++}`} className="json-null">
          {nul}
        </span>,
      );
    }
    lastIndex = start + m[0].length;
  }
  if (lastIndex < pretty.length) {
    nodes.push(<Fragment key={`t${i++}`}>{pretty.slice(lastIndex)}</Fragment>);
  }
  return nodes;
}

export function JsonPreview({ content }: { content: string }) {
  try {
    const obj = JSON.parse(content);
    const pretty = JSON.stringify(obj, null, 2);
    return (
      <pre className="max-h-96 overflow-auto rounded bg-slate-900 p-3 font-mono text-xs whitespace-pre text-slate-100">
        {tokenize(pretty)}
      </pre>
    );
  } catch {
    return <TextPreview content={content} />;
  }
}
