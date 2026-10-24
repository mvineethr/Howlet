import { Body1, Link, Title3 } from "@fluentui/react-components";

export default function PlaceholderPage({ title }: { title: string }) {
  return (
    <div style={{ padding: 24 }}>
      <Title3>{title}</Title3>
      <Body1 block style={{ marginTop: 8 }}>
        Coming in the next update. Until then it lives in the <Link href="/classic">classic view</Link>.
      </Body1>
    </div>
  );
}
