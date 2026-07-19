import { useState } from "react";
import "./styles.css";
import { HomePage } from "./pages/HomePage";
import { CreateOrderPage } from "./pages/CreateOrderPage";
import { OrderStatusPage } from "./pages/OrderStatusPage";
import { AddressManagerPage } from "./pages/AddressManagerPage";
import type { DeliveryType } from "./types/customer";

export type Page = "home" | "create-order" | "order-status" | "addresses";

export default function App() {
  const [page, setPage] = useState<Page>("home");
  const [orderType, setOrderType] = useState<DeliveryType>("RECEIVE_FROM_WAREHOUSE");

  const goHome = () => setPage("home");

  const goCreateOrder = (type: DeliveryType) => {
    setOrderType(type);
    setPage("create-order");
  };

  return (
    <div className="app-shell">
      {/* Navigation */}
      <nav className="nav">
        <button
          className="nav-logo"
          style={{ background: "none", border: "none", cursor: "pointer" }}
          onClick={goHome}
        >
          <span className="logo-icon">🚁</span>
          <span style={{ background: "linear-gradient(135deg,#3b82f6,#8b5cf6)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
            DroneGo
          </span>
        </button>
        <div className="nav-links">
          <button
            className={`nav-link ${page === "home" ? "active" : ""}`}
            onClick={goHome}
          >
            Trang chủ
          </button>
          <button
            className={`nav-link ${page === "order-status" ? "active" : ""}`}
            onClick={() => setPage("order-status")}
          >
            Đơn hàng
          </button>
          <button
            className={`nav-link ${page === "addresses" ? "active" : ""}`}
            onClick={() => setPage("addresses")}
          >
            Địa chỉ
          </button>
        </div>
      </nav>

      {/* Pages */}
      <main className="main-content">
        {page === "home" && <HomePage onSelectType={goCreateOrder} />}
        {page === "create-order" && (
          <CreateOrderPage
            deliveryType={orderType}
            onBack={goHome}
            onSuccess={() => setPage("order-status")}
          />
        )}
        {page === "order-status" && <OrderStatusPage />}
        {page === "addresses" && <AddressManagerPage />}
      </main>

      <footer className="footer">
        🚁 DroneGo — Giao hàng bằng drone. Nhanh. Tự động. Chính xác.
      </footer>
    </div>
  );
}
