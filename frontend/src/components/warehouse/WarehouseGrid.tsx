import React, { useState } from "react";

export interface SlotData {
  slot_id: string;
  status: "EMPTY" | "OCCUPIED" | "MOVING" | "RESERVED" | "ERROR";
  product_id?: string;
  updated_at?: string;
}

interface Props {
  slots?: SlotData[];
  n1DockStatus?: "READY" | "OCCUPIED" | "LANDING" | "OFFLINE";
  onSlotClick?: (slotId: string) => void;
}

const DEFAULT_SLOTS: SlotData[] = [
  { slot_id: "A1", status: "EMPTY" },
  { slot_id: "A2", status: "OCCUPIED", product_id: "PRD-1001" },
  { slot_id: "A3", status: "EMPTY" },
  { slot_id: "B1", status: "EMPTY" },
  { slot_id: "B2", status: "MOVING", product_id: "PRD-1002" },
  { slot_id: "B3", status: "OCCUPIED", product_id: "PRD-1003" },
  { slot_id: "C1", status: "RESERVED" },
  { slot_id: "C2", status: "RESERVED" },
  { slot_id: "C3", status: "RESERVED" },
];

export const WarehouseGrid = React.memo(function WarehouseGrid({
  slots = DEFAULT_SLOTS,
  n1DockStatus = "READY",
  onSlotClick,
}: Props) {
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);

  const getSlot = (id: string) =>
    slots.find((s) => s.slot_id === id) || {
      slot_id: id,
      status: id.startsWith("C") ? ("RESERVED" as const) : ("EMPTY" as const),
    };

  const handleSlotClick = (id: string) => {
    setSelectedSlot(id);
    if (onSlotClick) {
      onSlotClick(id);
    }
  };

  return (
    <div className="hmi-card warehouse-grid-card">
      <div className="card-header flex-between">
        <h3>📦 WAREHOUSE MAP (3x3: A1..B3 HOẠT ĐỘNG) + N1 DOCK</h3>
        <div className="legend-pills">
          <span className="legend-item"><span className="dot empty"></span> EMPTY</span>
          <span className="legend-item"><span className="dot occupied"></span> OCCUPIED</span>
          <span className="legend-item"><span className="dot moving"></span> MOVING</span>
          <span className="legend-item"><span className="dot reserved"></span> DỰ PHÒNG</span>
          <span className="legend-item"><span className="dot error"></span> ERROR</span>
        </div>
      </div>

      <div className="card-body warehouse-layout">
        {/* Top Docking Station Node N1 */}
        <div className="n1-dock-container">
          <div className={`n1-dock-box ${n1DockStatus.toLowerCase()}`}>
            <div className="dock-icon">🚁</div>
            <div className="dock-info">
              <span className="dock-id">N1 DRONE DOCK</span>
              <span className="dock-status">{n1DockStatus}</span>
            </div>
          </div>
          <div className="dock-link-line"></div>
        </div>

        {/* 3x3 Grid Matrix */}
        <div className="grid-3x3-matrix">
          {["A", "B", "C"].map((row) => (
            <div key={`row-${row}`} className="grid-matrix-row">
              {[1, 2, 3].map((col) => {
                const slotId = `${row}${col}`;
                const slot = getSlot(slotId);
                const isSymbolic = row === "C" || slot.status === "RESERVED";
                const isSelected = selectedSlot === slotId;

                return (
                  <button
                    key={slotId}
                    type="button"
                    className={`slot-card status-${slot.status.toLowerCase()} ${
                      isSymbolic ? "symbolic-slot" : ""
                    } ${isSelected ? "selected" : ""}`}
                    onClick={() => {
                      if (!isSymbolic) {
                        handleSlotClick(slotId);
                      }
                    }}
                    title={isSymbolic ? `Ô ${slotId} là ô kho dự phòng tượng trưng` : undefined}
                  >
                    <div className="slot-header flex-between">
                      <span className="slot-name">{slotId}</span>
                      <span className="status-badge">
                        {isSymbolic ? "DỰ PHÒNG" : slot.status}
                      </span>
                    </div>

                    <div className="slot-body">
                      {isSymbolic ? (
                        <span className="symbolic-placeholder">DỰ PHÒNG</span>
                      ) : slot.product_id ? (
                        <div className="product-box">
                          <span className="prod-icon">📦</span>
                          <span className="prod-id">{slot.product_id}</span>
                        </div>
                      ) : (
                        <span className="empty-placeholder">TRỐNG</span>
                      )}
                    </div>

                    {slot.status === "MOVING" && (
                      <div className="moving-spinner">
                        <span>ROBOT MOVING</span>
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      <div className="card-footer hint-text">
        <span>💡 Click vào ô kho để xem chi tiết hoặc thực hiện thao tác gắp/đặt.</span>
      </div>
    </div>
  );
});
