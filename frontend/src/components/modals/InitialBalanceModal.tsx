import React, { useState } from "react";
import { X, DollarSign, Check } from "lucide-react";
import { useTranslation } from "../../context/I18nContext";
import { apiUrl } from "../../lib/backend";

interface InitialBalanceModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentBalance?: number;
  onBalanceUpdated?: (newBalance: number) => void;
}

const PRESET_AMOUNTS = [5000, 10000, 25000, 50000, 100000];

export const InitialBalanceModal: React.FC<InitialBalanceModalProps> = ({
  isOpen,
  onClose,
  currentBalance = 0,
  onBalanceUpdated,
}) => {
  const { t } = useTranslation();
  const [balance, setBalance] = useState<number>(currentBalance);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await fetch(apiUrl("/api/v1/portfolio/set-initial-balance"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initial_balance: Number(balance) }),
      });
      if (!res.ok) throw new Error("Failed to update starting balance.");
      const data = await res.json();
      if (onBalanceUpdated) {
        onBalanceUpdated(data.initial_balance);
      }
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to save balance");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm font-mono select-none">
      <div className="bg-[#111722] border border-surface-border rounded-lg w-full max-w-md p-5 shadow-2xl space-y-4">
        <div className="flex items-center justify-between border-b border-surface-border pb-3">
          <div className="flex items-center space-x-2">
            <DollarSign className="w-5 h-5 text-accent" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wide">
              {t("initial_balance.modal_title")}
            </h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-xs text-slate-300">
          {t("initial_balance.modal_desc")}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-slate-400 block text-xs mb-1.5">
              {t("initial_balance.input_label")}
            </label>
            <div className="relative">
              <span className="absolute left-3 top-2 text-slate-500 text-sm">$</span>
              <input
                type="number"
                step="any"
                min="0"
                value={balance || ""}
                onChange={(e) => setBalance(Number(e.target.value))}
                placeholder={t("initial_balance.placeholder")}
                className="w-full bg-[#0b0e14] border border-surface-border rounded pl-8 pr-3 py-2 text-sm text-white focus:outline-none focus:border-accent font-bold"
                required
              />
            </div>
          </div>

          {/* Quick Preset Buttons */}
          <div>
            <span className="text-[11px] text-slate-400 block mb-1.5">
              {t("initial_balance.preset_label")}
            </span>
            <div className="grid grid-cols-5 gap-1.5">
              {PRESET_AMOUNTS.map((amt) => (
                <button
                  key={amt}
                  type="button"
                  onClick={() => setBalance(amt)}
                  className={`py-1 rounded text-[10px] font-bold border transition cursor-pointer ${
                    balance === amt
                      ? "bg-accent text-black border-accent"
                      : "bg-[#0d121c] text-slate-300 border-surface-border hover:border-slate-500"
                  }`}
                >
                  ${(amt / 1000).toFixed(0)}k
                </button>
              ))}
            </div>
          </div>

          {error && <p className="text-xs text-rose-400 font-semibold">{error}</p>}

          <div className="flex space-x-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 bg-[#162032] hover:bg-[#1f2d47] border border-surface-border text-slate-300 font-semibold rounded text-xs transition cursor-pointer"
            >
              {t("initial_balance.cancel")}
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 py-2 bg-accent hover:bg-sky-400 text-black font-bold rounded text-xs flex items-center justify-center space-x-1.5 transition disabled:opacity-50 cursor-pointer"
            >
              <Check className="w-4 h-4" />
              <span>{isSubmitting ? t("initial_balance.saving") : t("initial_balance.save")}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
