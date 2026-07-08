/** XLSX/XLS → CSV nel browser (Quality Lab, #101).
 *
 *  Converte il primo foglio (o quello scelto) in CSV testuale, che poi segue il
 *  percorso Qualità esistente: diagnosi, auto-fix (`/quality/fix`), export. La
 *  conversione resta client-side — il backend continua a non accettare binari —
 *  con SheetJS caricato on demand (import dinamico, già in package.json).
 */

export type XlsxToCsvResult = {
  csv: string;
  foglio: string;
  fogli: string[];
};

export function isSpreadsheetFile(name: string): boolean {
  return /\.(xlsx|xls)$/i.test(name);
}

export async function xlsxToCsv(buf: ArrayBuffer, foglio?: string): Promise<XlsxToCsvResult> {
  const XLSX = await import("xlsx");
  const wb = XLSX.read(buf, { type: "array" });
  const fogli = wb.SheetNames;
  if (!fogli.length) throw new Error("Il foglio di calcolo non contiene fogli leggibili.");
  const scelto = foglio && fogli.includes(foglio) ? foglio : fogli[0];
  const csv = XLSX.utils.sheet_to_csv(wb.Sheets[scelto], { blankrows: false });
  if (!csv.trim()) throw new Error(`Il foglio "${scelto}" è vuoto.`);
  return { csv, foglio: scelto, fogli };
}
