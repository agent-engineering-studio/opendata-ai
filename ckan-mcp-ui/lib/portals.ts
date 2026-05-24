export type PortalPreset = {
  label: string;
  url: string;
};

export const PORTAL_PRESETS: PortalPreset[] = [
  { label: "dati.gov.it (default)", url: "https://www.dati.gov.it/opendata" },
  { label: "data.gov.uk", url: "https://data.gov.uk" },
  { label: "data.gov (US)", url: "https://data.gov" },
  { label: "open.canada.ca", url: "https://open.canada.ca/data/en" },
  { label: "data.gov.au", url: "https://data.gov.au" },
];

export const DEFAULT_PORTAL = PORTAL_PRESETS[0].url;

export const CUSTOM_PORTAL_VALUE = "__custom__";
