import React from "react";
import { setFlightMode, moveRelative, startCamera, stopCamera } from "../services/api";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  droneStatus?: any;
};

const FLIGHT_MODES = [
  { label: "Offboard", value: "OFFBOARD" },
  { label: "Position", value: "POSCTL" },
  { label: "Hold", value: "HOLD" },
  { label: "Takeoff", value: "AUTO.TAKEOFF" },
  { label: "Land", value: "AUTO.LAND" },
  { label: "Return (RTL)", value: "AUTO.RTL" },
  { label: "Mission", value: "AUTO.MISSION" },
];

export function ManualControlModal({ isOpen, onClose, droneStatus }: Props) {
  if (!isOpen) return null;

  const handleSetMode = async (mode: string) => {
    try {
      await setFlightMode(mode);
    } catch (err) {
      console.error("Failed to set mode", err);
    }
  };

  const handleMove = async (dx: number, dy: number, dz: number) => {
    try {
      await moveRelative(dx, dy, dz);
    } catch (err) {
      console.error("Failed to move", err);
    }
  };

  const handleCamera = async (action: "start" | "stop") => {
    try {
      if (action === "start") await startCamera();
      else await stopCamera();
    } catch (err) {
      console.error(`Failed to ${action} camera`, err);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg p-6 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-500 hover:text-gray-800"
          title="Close Modal"
        >
          ✕
        </button>
        <h2 className="text-2xl font-bold mb-4 text-gray-800">Manual Control</h2>
        
        {/* Flight Modes */}
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-2 text-gray-700">Flight Modes</h3>
          <div className="grid grid-cols-3 gap-2">
            {FLIGHT_MODES.map((mode) => (
              <button
                key={mode.value}
                onClick={() => handleSetMode(mode.value)}
                className={`py-2 px-3 rounded text-sm font-medium transition ${
                  droneStatus?.flight_mode === mode.value
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                {mode.label}
              </button>
            ))}
          </div>
        </div>

        {/* Movement */}
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-2 text-gray-700">Movement (10cm steps)</h3>
          <p className="text-xs text-red-500 mb-2 font-medium">Requires OFFBOARD mode to be active.</p>
          <div className="flex justify-around items-center bg-gray-50 p-4 rounded-lg">
            {/* Z axis */}
            <div className="flex flex-col gap-2 items-center">
              <button
                onClick={() => handleMove(0, 0, -0.1)} // dz = -0.1 is UP
                className="w-12 h-12 bg-blue-100 hover:bg-blue-200 text-blue-800 rounded-full font-bold shadow flex items-center justify-center"
                title="Up"
              >
                UP
              </button>
              <span className="text-xs font-semibold text-gray-500">Z-Axis</span>
              <button
                onClick={() => handleMove(0, 0, 0.1)} // dz = 0.1 is DOWN
                className="w-12 h-12 bg-blue-100 hover:bg-blue-200 text-blue-800 rounded-full font-bold shadow flex items-center justify-center"
                title="Down"
              >
                DN
              </button>
            </div>

            {/* X/Y axis (D-pad) */}
            <div className="grid grid-cols-3 gap-2">
              <div />
              <button
                onClick={() => handleMove(0.1, 0, 0)} // dx = 0.1 is Forward
                className="w-12 h-12 bg-indigo-100 hover:bg-indigo-200 text-indigo-800 rounded shadow font-bold text-xl flex items-center justify-center"
                title="Forward"
              >
                ▲
              </button>
              <div />
              <button
                onClick={() => handleMove(0, -0.1, 0)} // dy = -0.1 is Left
                className="w-12 h-12 bg-indigo-100 hover:bg-indigo-200 text-indigo-800 rounded shadow font-bold text-xl flex items-center justify-center"
                title="Left"
              >
                ◀
              </button>
              <button
                onClick={() => handleMove(-0.1, 0, 0)} // dx = -0.1 is Backward
                className="w-12 h-12 bg-indigo-100 hover:bg-indigo-200 text-indigo-800 rounded shadow font-bold text-xl flex items-center justify-center"
                title="Backward"
              >
                ▼
              </button>
              <button
                onClick={() => handleMove(0, 0.1, 0)} // dy = 0.1 is Right
                className="w-12 h-12 bg-indigo-100 hover:bg-indigo-200 text-indigo-800 rounded shadow font-bold text-xl flex items-center justify-center"
                title="Right"
              >
                ▶
              </button>
            </div>
          </div>
        </div>

        {/* Camera Control */}
        <div>
          <h3 className="text-lg font-semibold mb-2 text-gray-700">Camera</h3>
          <div className="flex gap-4">
            <button
              onClick={() => handleCamera("start")}
              className="flex-1 py-2 bg-green-500 hover:bg-green-600 text-white rounded font-semibold transition shadow"
            >
              Start Camera
            </button>
            <button
              onClick={() => handleCamera("stop")}
              className="flex-1 py-2 bg-red-500 hover:bg-red-600 text-white rounded font-semibold transition shadow"
            >
              Stop Camera
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
