"use client";

import { useCallback, useMemo, useState, Fragment } from "react";
import { CharSheetSortButton, CharSheetTableToolbar } from "@/components/tools/CharSheetTableToolbar";
import { EveMailBody } from "@/lib/eveMailFormat";
import { formatEveTime } from "@/lib/eveTime";

export type MailHeaderRow = {
  mail_id: number;
  subject: string;
  from_id?: number | null;
  from_name?: string | null;
  timestamp?: string | null;
  is_read?: boolean;
  labels?: number[];
  recipient_count?: number;
};

type MailBody = {
  found: boolean;
  subject?: string;
  from_name?: string | null;
  timestamp?: string | null;
  body?: string;
  error?: string;
};

type SortKey = "date" | "subject" | "from" | "status";

function sortRows(rows: MailHeaderRow[], key: SortKey, asc: boolean): MailHeaderRow[] {
  const dir = asc ? 1 : -1;
  return [...rows].sort((a, b) => {
    if (key === "date") {
      const ta = Date.parse(a.timestamp || "") || 0;
      const tb = Date.parse(b.timestamp || "") || 0;
      return (ta - tb) * dir;
    }
    if (key === "from") {
      return (a.from_name || "").localeCompare(b.from_name || "") * dir;
    }
    if (key === "status") {
      const sa = a.is_read ? 1 : 0;
      const sb = b.is_read ? 1 : 0;
      return (sa - sb) * dir;
    }
    return (a.subject || "").localeCompare(b.subject || "") * dir;
  });
}

export function CharacterSheetMail({
  characterId,
  mail,
}: {
  characterId: number;
  mail: MailHeaderRow[];
}) {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortAsc, setSortAsc] = useState(false);
  const [readFilter, setReadFilter] = useState<"all" | "read" | "unread">("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [body, setBody] = useState<MailBody | null>(null);
  const [loadingBody, setLoadingBody] = useState(false);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    let filtered = mail.filter((m) => {
      if (readFilter === "read" && !m.is_read) return false;
      if (readFilter === "unread" && m.is_read) return false;
      if (!q) return true;
      const hay = [m.subject, m.from_name, formatEveTime(m.timestamp), m.timestamp]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
    return sortRows(filtered, sortKey, sortAsc);
  }, [mail, query, readFilter, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((v) => !v);
    else {
      setSortKey(key);
      setSortAsc(key === "subject" || key === "from" || key === "status");
    }
  };

  const loadBody = useCallback(
    async (mailId: number) => {
      if (selectedId === mailId && body?.found) {
        setSelectedId(null);
        setBody(null);
        return;
      }
      setSelectedId(mailId);
      setLoadingBody(true);
      setBody(null);
      try {
        const res = await fetch(`/api/audit/characters/${characterId}/mail/${mailId}`, {
          cache: "no-store",
          credentials: "same-origin",
        });
        if (!res.ok) {
          setBody({ found: false, error: "Unable to load mail body." });
        } else {
          setBody((await res.json()) as MailBody);
        }
      } catch {
        setBody({ found: false, error: "Unable to load mail body." });
      } finally {
        setLoadingBody(false);
      }
    },
    [body?.found, characterId, selectedId]
  );

  return (
    <div className="space-y-3">
      <CharSheetTableToolbar
        query={query}
        onQueryChange={setQuery}
        placeholder="Search subject, sender…"
        filters={
          <select
            className="eve-char-sheet-filter-select"
            value={readFilter}
            onChange={(e) => setReadFilter(e.target.value as "all" | "read" | "unread")}
            aria-label="Read filter"
          >
            <option value="all">All mail</option>
            <option value="unread">Unread</option>
            <option value="read">Read</option>
          </select>
        }
        shown={rows.length}
        total={mail.length}
      />

      <div className="eve-char-sheet-table-wrap">
        <table className="eve-table w-full text-[10px]">
          <thead>
            <tr>
              <th>
                <CharSheetSortButton label="Date" active={sortKey === "date"} asc={sortAsc} onClick={() => toggleSort("date")} />
              </th>
              <th>
                <CharSheetSortButton label="From" active={sortKey === "from"} asc={sortAsc} onClick={() => toggleSort("from")} />
              </th>
              <th>
                <CharSheetSortButton label="Subject" active={sortKey === "subject"} asc={sortAsc} onClick={() => toggleSort("subject")} />
              </th>
              <th>
                <CharSheetSortButton label="Status" active={sortKey === "status"} asc={sortAsc} onClick={() => toggleSort("status")} />
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={4} className="text-[var(--text-muted)]">
                  No mail in snapshot — sync character or adjust filters.
                </td>
              </tr>
            ) : (
              rows.map((m) => (
                <Fragment key={m.mail_id}>
                  <tr
                    className={`eve-char-sheet-mail-row ${selectedId === m.mail_id ? "selected" : ""} ${m.is_read ? "" : "unread"}`}
                    onClick={() => void loadBody(m.mail_id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        void loadBody(m.mail_id);
                      }
                    }}
                  >
                    <td>{formatEveTime(m.timestamp)}</td>
                    <td>{m.from_name || (m.from_id ? `Character ${m.from_id}` : "—")}</td>
                    <td>{m.subject}</td>
                    <td>{m.is_read ? "Read" : "Unread"}</td>
                  </tr>
                  {selectedId === m.mail_id ? (
                    <tr className="eve-char-sheet-mail-body-row">
                      <td colSpan={4}>
                        {loadingBody ? (
                          <p className="text-[var(--text-muted)]">Loading message…</p>
                        ) : body?.found ? (
                          <div className="eve-char-sheet-mail-body">
                            <div className="eve-char-sheet-mail-body-meta">
                              <strong>{body.subject || m.subject}</strong>
                              <span>
                                From {body.from_name || m.from_name || "Unknown"} · {formatEveTime(body.timestamp || m.timestamp)}
                              </span>
                            </div>
                            <EveMailBody body={body.body || ""} />
                          </div>
                        ) : (
                          <p className="text-[var(--warn)]">{body?.error || "Mail body unavailable."}</p>
                        )}
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
