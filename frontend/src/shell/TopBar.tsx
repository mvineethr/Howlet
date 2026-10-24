import { makeStyles, tokens, Text } from "@fluentui/react-components";
import type { ReactNode } from "react";

const useStyles = makeStyles({
  bar: {
    height: "44px", display: "flex", alignItems: "center", gap: "12px", padding: "0 12px",
    backgroundColor: tokens.colorNeutralBackground1, borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  brand: { display: "flex", alignItems: "center", gap: "6px", color: tokens.colorBrandForeground1, fontWeight: 600 },
});

export default function TopBar({ center, right }: { center?: ReactNode; right?: ReactNode }) {
  const s = useStyles();
  return (
    <header className={s.bar}>
      <span className={s.brand}><img src="/static/logo.png" alt="" width={20} height={20} /><Text weight="semibold">Howlet</Text></span>
      <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>{center}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>{right}</div>
    </header>
  );
}
