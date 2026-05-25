import { TextPreview } from "./TextPreview";

function prettyPrintXml(node: Node, depth = 0): string {
  const indent = "  ".repeat(depth);

  if (node.nodeType === Node.TEXT_NODE) {
    const text = (node.nodeValue ?? "").trim();
    return text ? `${indent}${text}\n` : "";
  }

  if (node.nodeType === Node.COMMENT_NODE) {
    return `${indent}<!--${node.nodeValue ?? ""}-->\n`;
  }

  if (node.nodeType !== Node.ELEMENT_NODE) {
    return "";
  }

  const el = node as Element;
  const attrs = Array.from(el.attributes)
    .map((a) => ` ${a.name}="${a.value}"`)
    .join("");

  const children = Array.from(el.childNodes);
  const hasElementChild = children.some((c) => c.nodeType === Node.ELEMENT_NODE);
  const textOnly =
    children.length === 1 && children[0].nodeType === Node.TEXT_NODE;

  if (children.length === 0) {
    return `${indent}<${el.tagName}${attrs}/>\n`;
  }

  if (textOnly && !hasElementChild) {
    const text = (children[0].nodeValue ?? "").trim();
    return `${indent}<${el.tagName}${attrs}>${text}</${el.tagName}>\n`;
  }

  let out = `${indent}<${el.tagName}${attrs}>\n`;
  for (const child of children) {
    out += prettyPrintXml(child, depth + 1);
  }
  out += `${indent}</${el.tagName}>\n`;
  return out;
}

export function XmlPreview({ content }: { content: string }) {
  if (typeof window === "undefined" || typeof DOMParser === "undefined") {
    return <TextPreview content={content} />;
  }
  try {
    const doc = new DOMParser().parseFromString(content, "application/xml");
    if (doc.querySelector("parsererror")) {
      return <TextPreview content={content} />;
    }
    const pretty = prettyPrintXml(doc.documentElement).trimEnd();
    return (
      <pre className="max-h-96 overflow-auto rounded bg-slate-900 p-3 font-mono text-xs whitespace-pre text-slate-100">
        {pretty}
      </pre>
    );
  } catch {
    return <TextPreview content={content} />;
  }
}
