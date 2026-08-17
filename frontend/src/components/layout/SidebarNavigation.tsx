export type NavTab =
  | "dashboard"
  | "uav"
  | "robot"
  | "warehouse"
  | "plc"
  | "vision"
  | "tasks"
  | "logs"
  | "settings";

interface Props {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
}

export function SidebarNavigation({ activeTab, onTabChange }: Props) {
  const navItems: { id: NavTab; label: string; icon: string }[] = [
    { id: "dashboard", label: "Dashboard", icon: "🎛️" },
    { id: "uav", label: "Drone (UAV)", icon: "🚁" },
    { id: "robot", label: "Robot Arm", icon: "🤖" },
    { id: "warehouse", label: "Warehouse", icon: "📦" },
    { id: "plc", label: "PLC System", icon: "⚙️" },
    { id: "vision", label: "Camera Vision", icon: "📷" },
    { id: "tasks", label: "Tasks & Orders", icon: "📋" },
    { id: "logs", label: "Logs", icon: "📑" },
    { id: "settings", label: "Settings", icon: "🛠️" },
  ];

  return (
    <aside className="hmi-sidebar">
      <nav className="hmi-nav-menu">
        {navItems.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`hmi-nav-item ${activeTab === item.id ? "active" : ""}`}
            onClick={() => onTabChange(item.id)}
          >
            <span className="hmi-nav-icon">{item.icon}</span>
            <span className="hmi-nav-label">{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="hmi-user-profile">
        <div className="profile-avatar">👨‍💻</div>
        <div className="profile-info">
          <span className="profile-name">Engineer</span>
          <span className="profile-status">● Online</span>
        </div>
      </div>
    </aside>
  );
}
