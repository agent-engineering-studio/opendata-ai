import { CsvTablePreview } from "./CsvTablePreview";
import { JsonPreview } from "./JsonPreview";
import { PdfPreview } from "./PdfPreview";
import { TextPreview } from "./TextPreview";
import { XlsxPreview } from "./XlsxPreview";
import { XmlPreview } from "./XmlPreview";

const TEXTUAL_FORMATS = new Set([
  "CSV",
  "JSON",
  "GEOJSON",
  "TXT",
  "XML",
  "RDF",
  "KML",
  "WMS",
  "WFS",
  "WCS",
]);

const XML_FAMILY = new Set(["XML", "RDF", "KML", "WMS", "WFS", "WCS"]);
const URL_ONLY_FORMATS = new Set(["PDF", "XLSX"]);

const NUL = String.fromCharCode(0);
const GZIP_BYTE_0 = 0x1f;
const GZIP_BYTE_1 = 0x8b;

function looksBinary(content: string): boolean {
  if (content.startsWith("PK")) return true;
  if (content.startsWith("%PDF")) return true;
  if (
    content.charCodeAt(0) === GZIP_BYTE_0 &&
    content.charCodeAt(1) === GZIP_BYTE_1
  )
    return true;
  if (content.includes(NUL)) return true;
  const sample = content.slice(0, 1024);
  const replacements = (sample.match(/�/g) ?? []).length;
  return replacements / Math.max(sample.length, 1) > 0.1;
}

export function isPreviewable(
  format: string | undefined,
  content: string | null | undefined,
  url?: string | undefined,
): boolean {
  if (!format) return false;
  const f = format.toUpperCase();
  if (URL_ONLY_FORMATS.has(f)) return !!url;
  if (TEXTUAL_FORMATS.has(f)) {
    if (content && !looksBinary(content)) return true;
    return !!url; // lazy fetch via proxy
  }
  return false;
}

export function ResourcePreview({
  format,
  content,
  url,
}: {
  format: string;
  content: string | null;
  url: string;
}) {
  const f = format.toUpperCase();
  if (f === "PDF") return <PdfPreview url={url} />;
  if (f === "XLSX") return <XlsxPreview url={url} />;

  if (!TEXTUAL_FORMATS.has(f)) return null;

  const text = content && !looksBinary(content) ? content : null;
  if (f === "CSV") return <CsvTablePreview content={text} url={url} />;

  if (!text) {
    return (
      <div className="text-xs text-slate-500">
        Anteprima non disponibile inline per questo formato. Usa &quot;Apri&quot;
        per scaricare il file.
      </div>
    );
  }

  if (f === "JSON" || f === "GEOJSON") return <JsonPreview content={text} />;
  if (XML_FAMILY.has(f)) return <XmlPreview content={text} />;
  return <TextPreview content={text} />;
}
