import { Button, Tab, TabList } from "@fluentui/react-components";
import AddBlockDialog from "../blocks/AddBlockDialog";
import { Add16Regular } from "@fluentui/react-icons";
import { useLayoutEffect, useRef, useState } from "react";
import { Responsive, type Layout } from "react-grid-layout";
import { HOME_KEY, loadHome, type HomeState } from "../lib/legacy";
import { writeJson } from "../lib/storage";
import { BLOCKS, blockFor, firstRunHome } from "../blocks/registry";

export default function HomePage() {
  const boxRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    setWidth(el.clientWidth);
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const [home, setHome] = useState<HomeState>(() => loadHome(firstRunHome));
  const save = (h: HomeState) => { setHome(h); writeJson(HOME_KEY, h); };
  const tab = home.tabs.find((t) => t.id === home.active) ?? home.tabs[0];

  const onLayout = (layout: Layout[]) => {
    const pos = new Map(layout.map((l) => [l.i, l]));
    save({ ...home, tabs: home.tabs.map((t) => t.id !== tab.id ? t : {
      ...t, blocks: t.blocks.map((b) => { const l = pos.get(b.i); return l ? { ...b, x: l.x, y: l.y, w: l.w, h: l.h } : b; }),
    }) });
  };
  const [adding, setAdding] = useState(false);
  const addBlock = (type: string, config: Record<string, string>) => {
    const { w, h } = BLOCKS[type].defaultSize;
    const block = { i: `${type}-${Date.now().toString(36)}`, type, config, x: 0, y: Infinity, w, h };
    save({ ...home, tabs: home.tabs.map((t) => t.id === tab.id ? { ...t, blocks: [...t.blocks, block] } : t) });
  };
  const removeBlock = (i: string) =>
    save({ ...home, tabs: home.tabs.map((t) => t.id === tab.id ? { ...t, blocks: t.blocks.filter((b) => b.i !== i) } : t) });

  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <TabList selectedValue={tab.id} onTabSelect={(_, d) => save({ ...home, active: String(d.value) })}>
          {home.tabs.map((t) => <Tab key={t.id} value={t.id}>{t.name}</Tab>)}
        </TabList>
        <Button icon={<Add16Regular />} appearance="subtle" onClick={() => setAdding(true)}>Add block</Button>
      </div>
      <AddBlockDialog open={adding} onClose={() => setAdding(false)} onAdd={(t, c) => { addBlock(t, c); setAdding(false); }} />
      <div ref={boxRef}>
        {width > 0 && (
          <Responsive width={width} className="layout" rowHeight={28} margin={[10, 10]} draggableHandle=".drag-handle"
            breakpoints={{ lg: 0 }} cols={{ lg: 12 }}
            layouts={{ lg: tab.blocks.map(({ i, x, y, w, h }) => ({ i, x, y, w, h, minW: 3, minH: 4 })) }}
            onLayoutChange={onLayout}>
            {tab.blocks.map((b) => <div key={b.i}>{blockFor(b.type).render(b.config, () => removeBlock(b.i))}</div>)}
          </Responsive>
        )}
      </div>
    </div>
  );
}
