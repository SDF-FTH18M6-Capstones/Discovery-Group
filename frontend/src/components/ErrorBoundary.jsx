import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    if (import.meta.env.MODE !== "test") console.error("Page crashed:", error, info);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="card flex flex-col gap-3 border-danger bg-danger-soft p-5">
        <h1 className="page-title text-danger">Something went wrong on this page</h1>
        <p className="text-sm">
          Your data is safe. Reload the page, or open another page from the menu.
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="btn-secondary self-start"
        >
          Reload page
        </button>
      </div>
    );
  }
}
