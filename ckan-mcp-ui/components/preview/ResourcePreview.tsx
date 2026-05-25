import { CsvTablePreview } from "./CsvTablePreview";
import { JsonPreview } from "./JsonPreview";
import { TextPreview } from "./TextPreview";
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

export function isPreviewable(
  format: string | undefined,
  content: string | null | undefined,
): content is string {
  if (!content || !format) return false;
  return TEXTUAL_FORMATS.has(format.toUpperCase());
}

export function ResourcePreview({
  format,
  content,
}: {
  format: string;
  content: string;
}) {
  const f = format.toUpperCase();
  if (!TEXTUAL_FORMATS.has(f)) return null;
  if (f === "CSV") return <CsvTablePreview content={content} />;
  if (f === "JSON" || f === "GEOJSON") return <JsonPreview content={content} />;
  if (XML_FAMILY.has(f)) return <XmlPreview content={content} />;
  return <TextPreview content={content} />;
}
