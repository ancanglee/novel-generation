import { Button, Toast } from "@novelgen/ui";
import { Component, type ErrorInfo, type ReactNode } from "react";
import { emit } from "../lib/telemetry";

interface State {
  error: Error | null;
}

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    emit({
      name: "UnhandledJsError",
      unit: "Count",
      value: 1,
      attrs: {
        message: (error.message ?? "unknown").slice(0, 120),
        componentStack: (info.componentStack ?? "").slice(0, 200),
      },
    });
  }

  reset = (): void => this.setState({ error: null });

  render(): ReactNode {
    if (!this.state.error) return this.props.children;
    if (this.props.fallback) return this.props.fallback;
    return (
      <div className="mx-auto max-w-xl p-8">
        <Toast variant="error" title="页面出错" description={this.state.error.message}>
          <div className="mt-3">
            <Button size="sm" variant="secondary" onClick={this.reset}>
              重试
            </Button>
          </div>
        </Toast>
      </div>
    );
  }
}
