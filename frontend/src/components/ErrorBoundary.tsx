import { Component, type ErrorInfo, type ReactNode } from "react";
import "./ErrorBoundary.css";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

/** Catches render/lifecycle exceptions anywhere below it so a bug shows a
 * recoverable screen instead of a silent white page (issue #140). React
 * only supports this via a class component -- there's no hook equivalent. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-fallback">
          <p className="error-fallback-title">문제가 발생했습니다.</p>
          <p className="error-fallback-body">
            화면을 표시하는 중 오류가 발생했습니다. 새로고침해 주세요.
          </p>
          <button
            className="error-fallback-retry"
            onClick={() => window.location.reload()}
          >
            새로고침
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
