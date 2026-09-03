import React, { useState } from "react";
import { VisionParseResult } from "../types";
import { Camera, Upload, CheckCircle2, ArrowRight, RefreshCw, X } from "lucide-react";
import { apiFetch, apiUrl } from "../lib/backend";

interface ChartVisionUploaderProps {
  isOpen: boolean;
  onClose: () => void;
  onTradeLogged?: () => void;
}

export const ChartVisionUploader: React.FC<ChartVisionUploaderProps> = ({
  isOpen,
  onClose,
  onTradeLogged,
}) => {
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [parseResult, setParseResult] = useState<VisionParseResult | null>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result as string;
      setImagePreview(base64);
      triggerVisionParse(base64);
    };
    reader.readAsDataURL(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result as string;
      setImagePreview(base64);
      triggerVisionParse(base64);
    };
    reader.readAsDataURL(file);
  };

  const triggerVisionParse = async (base64Data: string) => {
    setIsScanning(true);
    setParseResult(null);
    setSuccessMessage(null);

    try {
      const res = await apiFetch(apiUrl("/api/v1/ai/parse-chart"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_data: base64Data }),
      });
      const data: VisionParseResult = await res.json();
      setParseResult(data);
    } catch (err) {
      console.error("Vision OCR error:", err);
    } finally {
      setIsScanning(false);
    }
  };

  const handleLogTrade = async () => {
    if (!parseResult) return;
    setIsSaving(true);

    try {
      const payload = {
        symbol: parseResult.symbol,
        side: parseResult.side,
        entry_price: parseResult.entry_price,
        qty: 1.0,
        stop_loss: parseResult.stop_loss,
        take_profit: parseResult.take_profit,
        entry_time: new Date().toISOString(),
        notes: `Vision OCR Trade Setup (${parseResult.timeframe}) | RR: ${parseResult.risk_reward_ratio}R | Confidence: ${(parseResult.confidence_score * 100).toFixed(0)}%`,
      };

      const res = await apiFetch(apiUrl("/api/v1/trades"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setSuccessMessage("Trade logged successfully into SQLite & DuckDB!");
        if (onTradeLogged) onTradeLogged();
        setTimeout(() => {
          onClose();
        }, 1500);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 font-mono select-none">
      <div className="bg-[#0d121c] border border-surface-border rounded-xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col space-y-4 p-5">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-surface-border pb-3">
          <div className="flex items-center space-x-2">
            <Camera className="w-5 h-5 text-accent" />
            <div>
              <h3 className="text-sm font-bold text-white">MULTIMODAL VISION OCR CHART PARSER</h3>
              <p className="text-[11px] text-slate-400">
                Upload TradingView screenshot for 1-click trade parameter extraction
              </p>
            </div>
          </div>

          <button onClick={onClose} className="text-slate-400 hover:text-white transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Drop Zone / Image Preview */}
        {!imagePreview ? (
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className="border-2 border-dashed border-slate-700 hover:border-accent rounded-lg p-8 flex flex-col items-center justify-center cursor-pointer bg-[#090d14] transition"
          >
            <Upload className="w-8 h-8 text-slate-500 mb-2" />
            <span className="text-xs font-bold text-slate-200">Drag & Drop Chart Screenshot</span>
            <span className="text-[10px] text-slate-500 mt-1">PNG, JPG, WEBP (TradingView, MT5, cTrader)</span>
            <label className="mt-4 px-3 py-1.5 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-white text-xs rounded cursor-pointer transition">
              Browse Image
              <input type="file" accept="image/*" onChange={handleFileUpload} className="hidden" />
            </label>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="relative rounded-lg overflow-hidden border border-surface-border bg-[#090d14] max-h-44 flex items-center justify-center">
              <img src={imagePreview} alt="Chart preview" className="object-contain max-h-44 w-full" />
              {isScanning && (
                <div className="absolute inset-0 bg-accent/20 backdrop-blur-xs flex items-center justify-center flex-col space-y-2">
                  <RefreshCw className="w-6 h-6 text-accent animate-spin" />
                  <span className="text-xs font-bold text-white bg-black/70 px-3 py-1 rounded">
                    Scanning Price Nodes & OCR Matrix...
                  </span>
                </div>
              )}
            </div>

            <div className="flex justify-end">
              <label className="text-[10px] text-slate-400 hover:text-accent cursor-pointer flex items-center space-x-1">
                <RefreshCw className="w-3 h-3" />
                <span>Upload different image</span>
                <input type="file" accept="image/*" onChange={handleFileUpload} className="hidden" />
              </label>
            </div>
          </div>
        )}

        {/* Extracted Fields Matrix */}
        {parseResult && (
          <div className="bg-[#111722] p-4 rounded-lg border border-surface-border space-y-3">
            <div className="flex items-center justify-between border-b border-surface-border/60 pb-2">
              <div className="flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-gain" />
                <span className="text-xs font-bold text-white">OCR Extraction Verified</span>
              </div>
              <span className="text-[10px] text-accent font-bold bg-accent/10 px-2 py-0.5 rounded border border-accent/30">
                Confidence: {(parseResult.confidence_score * 100).toFixed(0)}%
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2 text-xs">
              <div className="bg-[#0d121c] p-2 rounded border border-surface-border">
                <span className="text-[10px] text-slate-400 block">ASSET / TIMEFRAME</span>
                <span className="font-bold text-white">
                  {parseResult.symbol} ({parseResult.timeframe})
                </span>
              </div>

              <div className="bg-[#0d121c] p-2 rounded border border-surface-border">
                <span className="text-[10px] text-slate-400 block">DIRECTION</span>
                <span className={`font-bold ${parseResult.side === "BUY" ? "text-gain" : "text-loss"}`}>
                  {parseResult.side}
                </span>
              </div>

              <div className="bg-[#0d121c] p-2 rounded border border-surface-border">
                <span className="text-[10px] text-slate-400 block">REWARD:RISK</span>
                <span className="font-bold text-accent">1 : {parseResult.risk_reward_ratio}</span>
              </div>

              <div className="bg-[#0d121c] p-2 rounded border border-surface-border">
                <span className="text-[10px] text-slate-400 block">ENTRY PRICE</span>
                <span className="font-bold text-slate-200">${parseResult.entry_price.toLocaleString()}</span>
              </div>

              <div className="bg-[#0d121c] p-2 rounded border border-surface-border">
                <span className="text-[10px] text-slate-400 block">STOP LOSS</span>
                <span className="font-bold text-loss">${parseResult.stop_loss.toLocaleString()}</span>
              </div>

              <div className="bg-[#0d121c] p-2 rounded border border-surface-border">
                <span className="text-[10px] text-slate-400 block">TAKE PROFIT</span>
                <span className="font-bold text-gain">${parseResult.take_profit.toLocaleString()}</span>
              </div>
            </div>

            <div className="text-[10px] text-slate-400">
              <strong className="text-slate-300">Sanity Notes:</strong> {parseResult.validation_notes}
            </div>

            {successMessage && (
              <div className="p-2 bg-emerald-950/60 border border-gain text-gain text-xs font-bold rounded text-center">
                {successMessage}
              </div>
            )}

            <button
              onClick={handleLogTrade}
              disabled={isSaving}
              className="w-full flex items-center justify-center space-x-2 bg-accent hover:bg-sky-400 text-black font-bold py-2 rounded text-xs transition"
            >
              <span>{isSaving ? "Saving..." : "1-CLICK LOG EXTRACTED TRADE"}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};