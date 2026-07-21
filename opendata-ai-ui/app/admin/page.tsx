"use client";

import { useCallback, useEffect, useState } from "react";

import { DashboardGate } from "@/components/DashboardGate";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";

// Keep in sync with backend auth.roles.VALID_ROLES.
const ROLES = ["admin", "regione", "comune", "cittadino"] as const;

const ROLE_LABEL: Record<string, string> = {
  admin: "Amministratore",
  regione: "Ente regionale",
  comune: "Comune",
  cittadino: "Cittadino",
};

type AdminUser = {
  id: number;
  clerk_user_id: string;
  email: string | null;
  display_name: string | null;
  role: string;
  subscription_tier: string;
  created_at: string;
};

type Msg = { kind: "ok" | "err"; text: string };

function AdminPanel() {
  const { getToken } = useAuth();
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<Msg | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const token = await getToken();
      const res = await apiFetch("/admin/users", { token });
      if (res.status === 403) {
        setForbidden(true);
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setUsers((await res.json()) as AdminUser[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [getToken]);

  useEffect(() => {
    void load();
  }, [load]);

  const changeRole = async (u: AdminUser, role: string) => {
    if (role === u.role) return;
    setMsg(null);
    setBusyId(u.id);
    try {
      const token = await getToken();
      const res = await apiFetch(`/admin/users/${u.id}/role`, {
        method: "PATCH",
        token,
        body: JSON.stringify({ role }),
      });
      if (!res.ok) {
        const detail = await res
          .json()
          .then((d) => d?.detail as string | undefined)
          .catch(() => undefined);
        setMsg({ kind: "err", text: detail ?? `Errore ${res.status}` });
        return;
      }
      const updated = (await res.json()) as AdminUser;
      setUsers((prev) => (prev ? prev.map((x) => (x.id === u.id ? updated : x)) : prev));
      setMsg({
        kind: "ok",
        text: `Ruolo di ${updated.email ?? updated.clerk_user_id} aggiornato a «${
          ROLE_LABEL[updated.role] ?? updated.role
        }».`,
      });
    } catch (e) {
      setMsg({ kind: "err", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusyId(null);
    }
  };

  if (forbidden) {
    return (
      <div className="alert alert-warning" role="alert">
        <strong>Accesso riservato.</strong> Questa sezione è visibile solo agli
        amministratori.
      </div>
    );
  }

  return (
    <>
      <h1 className="h3 mb-2">Amministrazione utenti</h1>
      <p className="text-muted">
        Assegna i ruoli agli utenti registrati. L&apos;autenticazione è gestita
        dall&apos;Identity Provider (SPID o registrazione via email); qui si
        governa <strong>cosa</strong> può fare ciascun utente.
      </p>

      {msg && (
        <div className={`alert ${msg.kind === "ok" ? "alert-success" : "alert-danger"}`} role="status">
          {msg.text}
        </div>
      )}
      {error && (
        <div className="alert alert-danger" role="alert">
          Impossibile caricare gli utenti: {error}
        </div>
      )}

      {users === null && !error ? (
        <p className="text-muted">Caricamento…</p>
      ) : users && users.length > 0 ? (
        <div className="table-responsive">
          <table className="table table-sm align-middle">
            <thead>
              <tr>
                <th>Utente</th>
                <th>Email</th>
                <th>Ruolo</th>
                <th className="d-none d-md-table-cell">Registrato</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.display_name ?? u.clerk_user_id}</td>
                  <td className="text-truncate" style={{ maxWidth: 240 }}>
                    {u.email ?? "—"}
                  </td>
                  <td>
                    <select
                      className="form-select form-select-sm"
                      style={{ width: "auto", display: "inline-block" }}
                      value={u.role}
                      disabled={busyId === u.id}
                      onChange={(e) => changeRole(u, e.target.value)}
                      aria-label={`Ruolo di ${u.email ?? u.clerk_user_id}`}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {ROLE_LABEL[r]}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="d-none d-md-table-cell text-muted small">
                    {new Date(u.created_at).toLocaleDateString("it-IT")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-muted">Nessun utente registrato.</p>
      )}
    </>
  );
}

export default function Page() {
  return (
    <DashboardGate>
      <div className="container py-5" style={{ maxWidth: 960 }}>
        <AdminPanel />
      </div>
    </DashboardGate>
  );
}
