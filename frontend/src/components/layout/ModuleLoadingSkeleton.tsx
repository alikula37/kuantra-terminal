import React from "react";
import { Loader2 } from "lucide-react";
import { useTranslation } from "../../context/I18nContext";

interface ModuleLoadingSkeletonProps {
  moduleName?: string;
}

export const ModuleLoadingSkeleton: React.FC<ModuleLoadingSkeletonProps> = ({ moduleName }) => {
  const { t } = useTranslation();

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex-1 flex flex-col h-full w-full bg-[#0b0e14] p-4 select-none font-mono space-y-4 overflow-hidden animate-pulse"
    >
      {/* Header Skeleton */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div className="space-y-1.5">
          <div className="h-4 w-64 bg-[#162032] rounded flex items-center px-2">
            <Loader2 className="w-3 h-3 text-accent animate-spin mr-1.5" />
            <span className="text-[10px] text-accent font-bold uppercase tracking-wider">
              {moduleName ? `${moduleName} — ${t("common.loading") || "Loading..."}` : t("common.loading_module") || "Loading Module..."}
            </span>
          </div>
          <div className="h-2.5 w-96 bg-[#111722] rounded" />
        </div>
        <div className="h-7 w-24 bg-[#162032] rounded" />
      </div>

      {/* Top Stat Cards Skeleton */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border space-y-2">
            <div className="h-2.5 w-20 bg-[#162032] rounded" />
            <div className="h-6 w-32 bg-[#1a263c] rounded" />
            <div className="h-2 w-28 bg-[#111722] rounded" />
          </div>
        ))}
      </div>

      {/* Main Body Skeleton */}
      <div className="flex-1 bg-[#0d121c] rounded-lg border border-surface-border p-4 flex flex-col space-y-3">
        <div className="flex items-center justify-between border-b border-surface-border/50 pb-2">
          <div className="h-3 w-40 bg-[#162032] rounded" />
          <div className="h-3 w-20 bg-[#162032] rounded" />
        </div>
        <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2 bg-[#090d14] rounded-lg border border-surface-border/40 p-4 flex items-center justify-center">
            <div className="text-center space-y-2">
              <Loader2 className="w-8 h-8 text-accent animate-spin mx-auto opacity-70" />
              <p className="text-xs text-slate-500 font-mono">
                {t("common.initializing_telemetry") || "Initializing high-frequency telemetry & graphics pipeline..."}
              </p>
            </div>
          </div>
          <div className="bg-[#090d14] rounded-lg border border-surface-border/40 p-3 space-y-2">
            <div className="h-3 w-28 bg-[#162032] rounded" />
            <div className="space-y-1.5 pt-2">
              {[...Array(6)].map((_, j) => (
                <div key={j} className="h-6 bg-[#111722] rounded flex items-center px-2 justify-between">
                  <div className="h-2 w-16 bg-[#162032] rounded" />
                  <div className="h-2 w-12 bg-[#1a263c] rounded" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
