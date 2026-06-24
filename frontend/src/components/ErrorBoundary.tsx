import { Component, type ErrorInfo, type ReactNode } from "react";
import { Icon } from "./Icon";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

/** Catches render errors in any child view and shows a recoverable fallback
 *  instead of a blank white screen. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("View crashed:", error, info.componentStack);
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-lg gap-md">
          <Icon name="error_outline" className="text-negative text-[40px]" />
          <div>
            <h2 className="text-card-title font-semibold text-on-surface">Something went wrong on this screen</h2>
            <p className="text-body-sm text-on-surface-variant mt-1 max-w-md">
              The rest of the app is fine. Try again, or switch to another view from the sidebar.
            </p>
          </div>
          <div className="flex gap-sm">
            <button
              onClick={this.reset}
              className="h-10 px-lg rounded-lg bg-primary text-on-primary font-medium text-body-sm hover:brightness-95 transition"
            >
              Try again
            </button>
            <button
              onClick={() => window.location.reload()}
              className="h-10 px-lg rounded-lg border border-outline-variant text-on-surface font-medium text-body-sm hover:bg-bg-1 transition"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
