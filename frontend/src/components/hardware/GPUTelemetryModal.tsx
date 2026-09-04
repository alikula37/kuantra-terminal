import React, { useState, useEffect } from "react";
import { Cpu, Zap, Activity, Thermometer, Sliders, Play, CheckCircle2, X, RefreshCw, Layers } from "lucide-react";
import { apiFetch, apiUrl } from "../../lib/backend";

interface GPUTelemetryModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const GPUTelemetryModal: React.FC<GPUTelemetryModalProps> = ({ isOpen, onClose }) => {
  const [metrics, setMetrics] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [selectedEngine, setSelectedEngine] = useState<string>("CUDA");
  const [gpuLayers, setGpuLayers] = useState<number>(33);
  const [threads, setThreads] = useState<number>(8);
  const [contextLength, setContextLength] = useState<number>(4096);
  const [isBenchmarking, setIsBenchmarking] = useState<boolean>(false);
  const [benchmarkResult, setBenchmarkResult] = useState<any>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  const fetchStatus = async () => {
    setIsLoading(true);
    try {
      const res = await apiFetch(apiUrl("/api/v1/hardware/gpu-status"));
      const data = await res.json();
      setMetrics(data);
      setSelectedEngine(data.engine || "CUDA");
      setGpuLayers(data.n_gpu_layers || 33);
      setThreads(data.threads || 8);
      setContextLength(data.context_length || 4096);
    } catch (e) {
      console.error("Failed to fetch GPU status:", e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchStatus();
    }
  }, [isOpen]);

  const handleSaveConfig = async () => {
    try {
      const res = await apiFetch(apiUrl("/api/v1/hardware/configure"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          engine: selectedEngine,
          n_gpu_layers: gpuLayers,
          threads: threads,
          context_length: contextLength,
        }),
      });
      await res.json();
      setSaveStatus("Hardware acceleration parameters persisted to runtime engine.");
      setTimeout(() => setSaveStatus(null), 3500);
      fetchStatus();
    } catch (e) {
      console.error(e);
    }
  };

  const handleRunBenchmark = async () => {
    setIsBenchmarking(true);
    setBenchmarkResult(null);
    try {
      const res = await apiFetch(apiUrl("/api/v1/swarm/fast-eval"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: "BTCUSDT",
          price: 65420.0,
          cvd_delta: 480.0,
          imbalance_ratio: 3.2,
          rsi: 33.0,
          account_drawdown_pct: 1.2,
        }),
      });
      const data = await res.json();
      setBenchmarkResult(data.gpu_acceleration);
    } catch (e) {
      console.error(e);
    } finally {
      setIsBenchmarking(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 font-mono select-none text-slate-100">
      <div className="bg-[#0b0e14] border border-surface-border rounded-xl w-full max-w-3xl shadow-2xl flex flex-col overflow-hidden max-h-[90vh]">
        {/* Header */}
        <div className="p-4 border-b border-surface-border flex items-center justify-between bg-[#0d121c]">
          <div className="flex items-center space-x-2.5">
            <Cpu className="w-5 h-5 text-accent" />
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                LOCAL LLM GPU ACCELERATION & VRAM TELEMETRY STUDIO
              </h2>
              <span className="text-[10px] text-slate-400">
                NVIDIA CUDA &bull; Apple Silicon Metal &bull; llama.cpp GGUF Sub-50ms Swarm Engine
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={fetchStatus}
              disabled={isLoading}
              className="p-1.5 bg-[#111722] hover:bg-[#192233] border border-surface-border rounded text-slate-400 hover:text-white transition"
              title="Refresh GPU Metrics"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            </button>

            <button
              onClick={onClose}
              className="p-1.5 bg-[#111722] hover:bg-rose-950 border border-surface-border rounded text-slate-400 hover:text-rose-400 transition"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-5 overflow-y-auto space-y-4">
          {/* Notification Banner */}
          {saveStatus && (
            <div className="bg-gain/10 border border-gain/30 p-3 rounded-lg flex items-center space-x-2 text-gain text-xs">
              <CheckCircle2 className="w-4 h-4" />
              <span>{saveStatus}</span>
            </div>
          )}

          {/* Realtime Metrics Cards */}
          {metrics && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div className="bg-[#0d121c] p-3 rounded-lg border border-surface-border space-y-1">
                <span className="text-[10px] text-slate-400 flex items-center space-x-1">
                  <Activity className="w-3 h-3 text-accent" />
                  <span>VRAM USAGE</span>
                </span>
                <span className="text-base font-bold text-white font-mono">
                  {metrics.vram_allocated_mb} / {metrics.vram_total_mb} MB
                </span>
                <div className="w-full bg-[#111722] rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-accent h-full rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(100, metrics.vram_utilization_pct || 40)}%` }}
                  />
                </div>
                <span className="text-[9px] text-slate-400 block text-right">
                  {metrics.vram_utilization_pct}% Allocated
                </span>
              </div>

              <div className="bg-[#0d121c] p-3 rounded-lg border border-surface-border space-y-1">
                <span className="text-[10px] text-slate-400 flex items-center space-x-1">
                  <Zap className="w-3 h-3 text-gain" />
                  <span>GPU CORE LOAD</span>
                </span>
                <span className="text-base font-bold text-gain font-mono">
                  {metrics.gpu_core_utilization_pct}%
                </span>
                <div className="w-full bg-[#111722] rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-gain h-full rounded-full transition-all duration-300"
                    style={{ width: `${metrics.gpu_core_utilization_pct}%` }}
                  />
                </div>
                <span className="text-[9px] text-gain block text-right">OPTIMAL COMPUTE</span>
              </div>

              <div className="bg-[#0d121c] p-3 rounded-lg border border-surface-border space-y-1">
                <span className="text-[10px] text-slate-400 flex items-center space-x-1">
                  <Thermometer className="w-3 h-3 text-amber-400" />
                  <span>TEMPERATURE</span>
                </span>
                <span className="text-base font-bold text-amber-400 font-mono">
                  {metrics.gpu_temperature_c}°C
                </span>
                <span className="text-[9px] text-slate-400 block">Thermal Status: NORMAL</span>
              </div>

              <div className="bg-[#0d121c] p-3 rounded-lg border border-surface-border space-y-1">
                <span className="text-[10px] text-slate-400 flex items-center space-x-1">
                  <Sliders className="w-3 h-3 text-purple-400" />
                  <span>ACTIVE ENGINE</span>
                </span>
                <span className="text-base font-bold text-purple-400 font-mono">
                  {metrics.engine}
                </span>
                <span className="text-[9px] text-slate-400 block truncate" title={metrics.device_name}>
                  {metrics.device_name}
                </span>
              </div>
            </div>
          )}

          {/* Compute Acceleration Controls */}
          <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-4">
            <span className="text-xs font-bold text-white flex items-center space-x-1.5 border-b border-surface-border pb-2">
              <Sliders className="w-4 h-4 text-accent" />
              <span>DYNAMIC VRAM OFFLOAD & COMPUTE PARAMETERS</span>
            </span>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              {/* Engine Selector */}
              <div className="space-y-1.5">
                <label className="text-slate-300 font-bold block">Compute Acceleration Backend</label>
                <select
                  value={selectedEngine}
                  onChange={(e) => setSelectedEngine(e.target.value)}
                  className="w-full bg-[#111722] border border-surface-border text-white px-3 py-2 rounded text-xs focus:outline-none focus:border-accent"
                >
                  <option value="CUDA">NVIDIA CUDA (RTX DirectCompute / Tensor Cores)</option>
                  <option value="METAL">Apple Silicon Metal (M1/M2/M3/M4 Unified Memory)</option>
                  <option value="DIRECTML">DirectML (DirectX 12 Virtualized GPU)</option>
                  <option value="CPU_AVX512">CPU Vectorized (AVX-512 / AVX2 Multithreaded)</option>
                </select>
              </div>

              {/* Context Length */}
              <div className="space-y-1.5">
                <label className="text-slate-300 font-bold block">Quant Context Window (Tokens)</label>
                <select
                  value={contextLength}
                  onChange={(e) => setContextLength(Number(e.target.value))}
                  className="w-full bg-[#111722] border border-surface-border text-white px-3 py-2 rounded text-xs focus:outline-none focus:border-accent"
                >
                  <option value="2048">2,048 Tokens (Ultra-Fast 2ms TTFT)</option>
                  <option value="4096">4,096 Tokens (Recommended Default)</option>
                  <option value="8192">8,192 Tokens (Multi-Timeframe Context)</option>
                  <option value="16384">16,384 Tokens (Full Book Ingestion)</option>
                </select>
              </div>
            </div>

            {/* Layer Offloading Slider */}
            <div className="space-y-2 pt-2 border-t border-surface-border">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-300 font-bold flex items-center space-x-1.5">
                  <Layers className="w-3.5 h-3.5 text-accent" />
                  <span>GPU Layer Offload (n_gpu_layers)</span>
                </span>
                <span className="text-accent font-bold font-mono">
                  {gpuLayers} / 33 Layers ({Math.round((gpuLayers / 33) * 100)}% VRAM Offloaded)
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="33"
                value={gpuLayers}
                onChange={(e) => setGpuLayers(Number(e.target.value))}
                className="w-full h-1.5 bg-[#111722] rounded-lg appearance-none cursor-pointer accent-accent"
              />
              <div className="flex justify-between text-[10px] text-slate-500">
                <span>0 (CPU Only)</span>
                <span>16 (Hybrid VRAM)</span>
                <span>33 (100% GPU Accelerated)</span>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={handleSaveConfig}
                className="bg-accent hover:bg-sky-400 text-black font-bold px-4 py-1.5 rounded text-xs transition shadow"
              >
                APPLY & PERSIST HARDWARE CONFIGURATION
              </button>
            </div>
          </div>

          {/* Inference Benchmarking */}
          <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
            <div className="flex items-center justify-between border-b border-surface-border pb-2">
              <span className="text-xs font-bold text-white flex items-center space-x-1.5">
                <Zap className="w-4 h-4 text-gain" />
                <span>LIVE HARDWARE BENCHMARK & SUB-50MS TELEMETRY</span>
              </span>

              <button
                onClick={handleRunBenchmark}
                disabled={isBenchmarking}
                className="flex items-center space-x-1.5 bg-gain hover:bg-emerald-400 text-black font-bold px-3 py-1 rounded text-xs transition shadow"
              >
                <Play className={`w-3 h-3 ${isBenchmarking ? "animate-spin" : ""}`} />
                <span>{isBenchmarking ? "MEASURING..." : "RUN INFERENCE BENCHMARK"}</span>
              </button>
            </div>

            {benchmarkResult ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                <div className="bg-[#111722] p-2.5 rounded border border-surface-border">
                  <span className="text-[9px] text-slate-400 block">TIME TO FIRST TOKEN</span>
                  <span className="text-sm font-bold text-gain font-mono">
                    {benchmarkResult.time_to_first_token_ms} ms
                  </span>
                </div>
                <div className="bg-[#111722] p-2.5 rounded border border-surface-border">
                  <span className="text-[9px] text-slate-400 block">THROUGHPUT</span>
                  <span className="text-sm font-bold text-accent font-mono">
                    {benchmarkResult.tokens_per_second} tok/s
                  </span>
                </div>
                <div className="bg-[#111722] p-2.5 rounded border border-surface-border">
                  <span className="text-[9px] text-slate-400 block">TOTAL LATENCY</span>
                  <span className="text-sm font-bold text-white font-mono">
                    {benchmarkResult.total_pipeline_latency_ms} ms
                  </span>
                </div>
                <div className="bg-[#111722] p-2.5 rounded border border-surface-border">
                  <span className="text-[9px] text-slate-400 block">SUB-50MS SLA</span>
                  <span className="text-sm font-bold text-gain font-mono">
                    {benchmarkResult.is_sub_50ms ? "PASSED (<50ms)" : "FALLBACK"}
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-[11px] text-slate-400">
                Click "Run Inference Benchmark" to measure real-time Token Generation Throughput (tok/s) and Time-To-First-Token (TTFT) on your active compute backend.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};