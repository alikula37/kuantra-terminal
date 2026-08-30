import React, { Component, ErrorInfo, ReactNode, Suspense } from "react";
import { usePluginRegistry, SlotType, PluginContribution } from "../../context/PluginRegistryContext";

interface ErrorBoundaryProps {
  pluginId: string;
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class PluginErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`[PluginErrorBoundary] Error in plugin "${this.props.pluginId}":`, error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-3 bg-red-950/40 border border-red-500/50 rounded text-red-200 text-xs flex items-center justify-between">
          <span>⚠️ Extension widget ({this.props.pluginId}) encountered an error.</span>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="px-2 py-0.5 bg-red-800/60 hover:bg-red-700 rounded text-[10px] text-white"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

interface ExtensionSlotProps {
  slot: SlotType;
  fallback?: ReactNode;
  renderItem?: (contribution: PluginContribution) => ReactNode;
}

export const ExtensionSlot: React.FC<ExtensionSlotProps> = ({ slot, fallback = null, renderItem }) => {
  const { getSlotContributions } = usePluginRegistry();
  const items = getSlotContributions(slot);

  if (items.length === 0) {
    return <>{fallback}</>;
  }

  return (
    <>
      {items.map((item) => {
        const ComponentToRender = item.component;
        return (
          <PluginErrorBoundary key={item.id} pluginId={item.pluginId}>
            <Suspense fallback={<div className="animate-pulse bg-slate-800/50 h-8 rounded" />}>
              {renderItem ? renderItem(item) : <ComponentToRender />}
            </Suspense>
          </PluginErrorBoundary>
        );
      })}
    </>
  );
};