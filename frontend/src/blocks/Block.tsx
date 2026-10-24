import { Button, Caption1, Card, CardHeader, Spinner, Text } from "@fluentui/react-components";
import { Dismiss16Regular } from "@fluentui/react-icons";
import type { ReactNode } from "react";

type Props = {
  title: string; loading?: boolean; error?: Error; fetchedAt?: number; refreshMs?: number;
  sec?: boolean; onRemove?: () => void; children?: ReactNode;
};

export default function Block({ title, loading, error, fetchedAt, refreshMs, sec, onRemove, children }: Props) {
  const stale = fetchedAt && refreshMs && Date.now() - fetchedAt > 2 * refreshMs;
  const asOf = fetchedAt ? new Date(fetchedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
  return (
    <Card style={{ height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }} size="small">
      <CardHeader className="drag-handle" style={{ cursor: "grab" }}
        header={<Text weight="semibold">{title}</Text>}
        description={stale || (error && fetchedAt) ? <Caption1>as of {asOf}</Caption1> : undefined}
        action={<span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {loading && <Spinner size="extra-tiny" />}
          {onRemove && <Button appearance="subtle" size="small" icon={<Dismiss16Regular />} aria-label={`Remove ${title}`} onClick={onRemove} />}
        </span>} />
      <div style={{ flex: 1, overflow: "auto" }}>
        {error && !children ? (
          <Caption1 style={{ color: "var(--dim)" }}>{sec ? error.message : "Unavailable, retrying"}</Caption1>
        ) : children}
      </div>
    </Card>
  );
}
