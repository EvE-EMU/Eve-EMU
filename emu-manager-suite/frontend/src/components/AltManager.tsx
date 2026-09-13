"use client";

import clsx from "clsx";
import { characterPortraitUrl } from "@/lib/evetech";
import { useAuth, type LinkedAlt } from "./AuthProvider";
import { Tooltip } from "./Tooltip";

function AltRow({
  alt,
  active,
  onSelect,
}: {
  alt: LinkedAlt;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={clsx("eve-alt-row", active && "is-active")}
      onClick={onSelect}
      disabled={alt.token_valid === false}
      title={alt.token_valid !== false ? alt.character_name : `${alt.character_name} — re-link via SSO`}
    >
      <img src={characterPortraitUrl(alt.character_id, 64)} alt="" width={28} height={28} className="eve-alt-portrait" />
      <span className="eve-alt-name truncate">{alt.character_name}</span>
      {alt.is_main ? <span className="eve-alt-badge">Main</span> : null}
      {!alt.token_valid ? <span className="eve-alt-badge warn">Re-link</span> : null}
    </button>
  );
}

export function AltManager() {
  const { session, switching, switchCharacter, linkAltUrl, switchError } = useAuth();

  if (!session.authenticated) {
    return null;
  }

  const alts = session.alts ?? [];
  const activeId = session.character_id;

  return (
    <div className="eve-alt-manager">
      <Tooltip label="Pilot roster" hint="Combined character sheet for all alts, or switch active pilot for SSO actions" side="bottom">
        <details className="eve-alt-dropdown">
          <summary className="eve-alt-trigger">
            <img
              src={characterPortraitUrl(activeId ?? alts[0].character_id, 64)}
              alt=""
              width={24}
              height={24}
              className="eve-alt-trigger-portrait"
            />
            <span className="eve-alt-trigger-label truncate max-w-[100px]">{session.character_name}</span>
            {alts.length > 1 ? <span className="eve-alt-count">{alts.length}</span> : null}
          </summary>
          <div className="eve-alt-menu">
            <p className="eve-alt-menu-head">Linked characters</p>
            {alts.map((alt) => (
              <AltRow
                key={alt.character_id}
                alt={alt}
                active={alt.character_id === activeId}
                onSelect={() => {
                  if (alt.character_id !== activeId && !switching) {
                    void switchCharacter(alt.character_id);
                  }
                }}
              />
            ))}
            <a href={linkAltUrl || "/api/auth/sso/link"} className="eve-alt-link-btn">
              + Link alt via EVE SSO
            </a>
            {switchError ? <p className="eve-alt-switch-error">{switchError}</p> : null}
          </div>
        </details>
      </Tooltip>
    </div>
  );
}
