import { ResponseBlocks, SourcesPanel, Disc } from "./ChatComponents";
import { C, F } from "../../theme";

const ZONE_MAPPING = {
  zone1: ['key_metrics', 'quote', 'table'],
  zone2: ['analysis', 'bullets', 'chart', 'warning', 'news']
};

export function ThreeZoneLayout({ blocks = [], sources = [], confidence, disclaimer, fallbackText, trace }) {
  // Categorize blocks into zones
  const zone1Blocks = blocks.filter(b => ZONE_MAPPING.zone1.includes(b.type));
  const zone2Blocks = blocks.filter(b => ZONE_MAPPING.zone2.includes(b.type));

  // Unknown block types - log warning
  const unknownBlocks = blocks.filter(b =>
    !ZONE_MAPPING.zone1.includes(b.type) &&
    !ZONE_MAPPING.zone2.includes(b.type)
  );

  if (unknownBlocks.length > 0) {
    console.warn('[ThreeZoneLayout] Unknown block types:', unknownBlocks.map(b => b.type));
  }

  // Error handling: no content in zone 2 and no fallback text
  const hasZone2Content = zone2Blocks.length > 0 || fallbackText;

  if (!hasZone2Content) {
    return (
      <div style={{
        padding: '16px',
        background: C.warnBg,
        border: `1px solid #FCD34D`,
        borderRadius: 12,
        color: C.text,
        fontSize: 13
      }}>
        分析生成失败，请重试。
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Zone 1: Data Summary */}
      {zone1Blocks.length > 0 && (
        <div style={{
          background: C.white,
          borderRadius: 12,
          border: `1px solid ${C.border}`,
          overflow: 'hidden'
        }}>
          <ResponseBlocks blocks={zone1Blocks} />
        </div>
      )}

      {/* Zone 2: Analysis */}
      {zone2Blocks.length > 0 ? (
        <ResponseBlocks blocks={zone2Blocks} />
      ) : fallbackText ? (
        <div style={{
          background: "#FAFCFF",
          borderRadius: 12,
          padding: "18px 18px 14px",
          border: "1px solid #D6E4F7",
          position: "relative",
          fontSize: 13,
          lineHeight: 1.85,
          color: C.text,
          whiteSpace: "pre-wrap",
        }}>
          <div style={{
            position: "absolute",
            top: -9,
            left: 12,
            background: C.accentL,
            color: C.accent,
            fontSize: 9.5,
            fontWeight: 700,
            padding: "2px 8px",
            borderRadius: 8,
            border: "1px solid #BFD5F0",
          }}>
            AI 分析
          </div>
          {fallbackText}
        </div>
      ) : null}

      {/* Zone 3: Meta */}
      {sources && sources.length > 0 && <SourcesPanel items={sources} />}

      <Disc text={disclaimer || "以上内容仅供参考，不构成投资建议。"} />
    </div>
  );
}
