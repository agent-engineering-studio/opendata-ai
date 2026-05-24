export type ExampleQuery = {
  label: string;
  query: string;
};

export const EXAMPLE_QUERIES: ExampleQuery[] = [
  {
    label: "5 dataset più recenti",
    query: "Mostrami i 5 dataset più recenti su dati.gov.it",
  },
  {
    label: "Trasporti su data.gov.uk",
    query: "List recent datasets about transport",
  },
  {
    label: "Dettagli di un dataset (UUID)",
    query:
      "Mostrami i dettagli del dataset 2908fe96-58c4-40fe-8b29-9d4d78715ba7",
  },
  {
    label: "Organizzazioni per tema trasporti",
    query: "Quali organizzazioni pubblicano dati su trasporti?",
  },
  {
    label: "Stato del portale CKAN",
    query: "Show CKAN portal status",
  },
];
