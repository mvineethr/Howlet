import React from "react";
import ReactDOM from "react-dom/client";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import "./index.css";
import App from "./App";

// Plain HTML on purpose: must render even if Fluent itself is what failed.
class Boundary extends React.Component<{ children: React.ReactNode }, { err: Error | null }> {
  state = { err: null as Error | null };
  static getDerivedStateFromError(err: Error) { return { err }; }
  render() {
    if (!this.state.err) return this.props.children;
    return (
      <div style={{ padding: 24, fontFamily: "Segoe UI, sans-serif" }}>
        <h2>Howlet hit an error</h2>
        <pre style={{ whiteSpace: "pre-wrap" }}>{this.state.err.message}</pre>
        <p>Your watchlists, alerts and portfolio are untouched. Resetting only clears display settings and the Home layout.</p>
        <button onClick={() => { localStorage.removeItem("howlet_settings_v1"); localStorage.removeItem("howlet_home_v1"); location.reload(); }}>Reset settings</button>
        {" "}<a href="/classic">Open classic view</a>
      </div>
    );
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><Boundary><App /></Boundary></React.StrictMode>,
);
