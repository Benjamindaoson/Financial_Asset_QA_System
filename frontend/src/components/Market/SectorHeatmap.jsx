import { C, F } from "../../theme";

export function SectorHeatmap({ sectors }) {
  if (!sectors || sectors.length === 0) {
    return null;
  }

  return (
    <div style={{ marginBottom: 32 }}>
      <h2
        style={{
          fontSize: 16,
          fontWeight: 700,
          color: C.text,
          marginBottom: 16,
          fontFamily: F.m,
        }}
      >
        SECTOR PERFORMANCE
      </h2>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: 12,
        }}
      >
        {sectors.map((sector) => (
          <SectorCard key={sector.name} sector={sector} />
        ))}
      </div>
    </div>
  );
}

function SectorCard({ sector }) {
  const isPositive = sector.change_pct >= 0;
  const changeColor = isPositive ? "#10B981" : "#EF4444";
  const bgColor = isPositive ? "#10B98110" : "#EF444410";

  return (
    <div
      style={{
        background: bgColor,
        border: `1px solid ${changeColor}30`,
        borderRadius: 10,
        padding: "14px 16px",
        transition: "all 0.2s",
        cursor: "pointer",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = "translateY(-2px)";
        e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.08)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "translateY(0)";
        e.currentTarget.style.boxShadow = "none";
      }}
    >
      <div
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: C.text,
          marginBottom: 6,
          fontFamily: F.m,
        }}
      >
        {sector.name}
      </div>
      <div
        style={{
          fontSize: 18,
          fontWeight: 700,
          color: changeColor,
          fontFamily: F.m,
        }}
      >
        {isPositive ? "+" : ""}
        {sector.change_pct?.toFixed(2)}%
      </div>
    </div>
  );
}
