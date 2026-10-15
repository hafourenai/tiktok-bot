import { useState } from "preact/hooks";
import ConversionPage from "./Conversion";
import WeatherViewer from "src/ui/components/Weather/WeatherViewer";
import "./TabbedPage.css";

type Tab = "converter" | "weather";

export default function TabbedPage() {
  const [activeTab, setActiveTab] = useState<Tab>("converter");

  return (
    <div className="tabbed-page">
      <div className="tab-navigation">
        <button
          className={`tab-button ${activeTab === "converter" ? "active" : ""}`}
          onClick={() => setActiveTab("converter")}
        >
          File Converter
        </button>
        <button
          className={`tab-button ${activeTab === "weather" ? "active" : ""}`}
          onClick={() => setActiveTab("weather")}
        >
          Weather Forecast
        </button>
      </div>

      <div className="tab-content">
        {activeTab === "converter" && <ConversionPage />}
        {activeTab === "weather" && <WeatherViewer />}
      </div>
    </div>
  );
}
