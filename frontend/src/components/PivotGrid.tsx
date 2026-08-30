import React, { useState, useEffect } from "react";
import { PivotGridResponse, PivotRow } from "../types";
import { Layers, ArrowUpDown, Download, Filter, CheckSquare, Square } from "lucide-react";

export const PivotGrid: React.FC = () => {
  const [selectedDimensions, setSelectedDimensions] = useState<string[]>(["symbol", "session"]);
  const [pivotData, setPivotData] = useState<PivotGridResponse | null>(null);
  const [sortField, setSortField] = useState<keyof PivotRow>("total_pnl");
  const [sortAsc, setSortAsc] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const availableDimensions = [
    { id: "symbol", label: "Asset Symbol" },
    { id: "side", label: "Direction (Long/Short)" },
    { id: "day_of_week", label: "Day of Week" },
    { id: "session", label: "Trading Session" },
    { id: "hold_time_range", label: "Hold Duration" },
  ];

  const fetchPivot = (dims: string[]) => {
    setIsLoading(true);
    fetch("http://127.0.0.1:8000/api/v1/analytics/pivot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ group_by: dims }),
    })
      .then((res) => res.json())
      .then((data) => {
        setPivotData(data);
        setIsLoading(false);
      })
      .catch(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    fetchPivot(selectedDimensions);
  }, [selectedDimensions]);

  const toggleDimension = (dimId: string) => {
    let next: string[];
    if (selectedDimensions.includes(dimId)) {
      if (selectedDimensions.length === 1) return; // keep at least 1
      next = selectedDimensions.filter((d) => d !== dimId);
    } else {
      next = [...selectedDimensions, dimId];
    }
    setSelectedDimensions(next);
  };

  const handleSort = (field: keyof PivotRow) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  const sortedRows = pivotData?.rows
    ? [...pivotData.rows].sort((a, b) => {
        const valA = a[sortField];
        const valB = b[sortField];
        if (typeof valA === "number" && typeof valB === "number") {
          return sortAsc ? valA - valB : valB - valA;
        }
        return sortAsc
          ? String(valA).localeCompare(String(valB))
          : String(valB).localeCompare(String(valA));
      })
    : [];

  const exportCSV = () => {
    if (!pivotData || !pivotData.rows.length) return;
    const headers = ["Group Key", "Trades", "Win Rate %", "Total PnL", "Avg PnL", "Profit Factor", "Avg R", "SQN", "Expectancy", "Max Win", "Max Loss"];
    const csvRows = [headers.join(",")];

    for (const r of sortedRows) {
      csvRows.push([
        `"${r.group_key}"`,
        r.trades_count,
        r.win_rate,
        r.total_pnl,
        r.avg_pnl,
        r.profit_factor,
        r.avg_r_multiple,
        r.sqn,
        r.expectancy,
        r.max_win,
        r.max_loss
      ].join(","));
    }

    const blob = new Blob([csvRows.join("\n")], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.setAttribute("href", url);
    a.setAttribute("download", `kuantra_pivot_${Date.now()}.csv`);
    a.click();
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-hidden p-4 select-none font-mono space-y-4">
      {/* Header & Controls */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <Layers className="w-4 h-4 text-purple-400" />
            <span>DYNAMIC MULTI-DIMENSIONAL PIVOT GRID</span>
          </h2>
          <p className="text-xs text-slate-400">
            DuckDB Vectorized Performance Matrix & Multi-Level Stratification
          </p>
        </div>

        <button
          onClick={exportCSV}
          className="flex items-center space-x-1.5 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-white text-xs px-3 py-1.5 rounded transition"
        >
          <Download className="w-3.5 h-3.5 text-accent" />
          <span>EXPORT CSV</span>
        </button>
      </div>

      {/* Dimension Selector Bar */}
      <div className="bg-[#0d121c] p-3 rounded-lg border border-surface-border flex flex-wrap items-center gap-2">
        <span className="text-xs text-slate-400 font-bold mr-2 flex items-center space-x-1">
          <Filter className="w-3.5 h-3.5" />
          <span>Group Dimensions:</span>
        </span>
        {availableDimensions.map((dim) => {
          const isSelected = selectedDimensions.includes(dim.id);
          return (
            <button
              key={dim.id}
              onClick={() => toggleDimension(dim.id)}
              className={`flex items-center space-x-1.5 px-3 py-1 rounded text-xs transition ${
                isSelected
                  ? "bg-accent/20 border border-accent/40 text-accent font-bold"
                  : "bg-[#111722] text-slate-400 hover:text-white border border-surface-border"
              }`}
            >
              {isSelected ? <CheckSquare className="w-3.5 h-3.5" /> : <Square className="w-3.5 h-3.5 text-slate-600" />}
              <span>{dim.label}</span>
            </button>
          );
        })}
      </div>

      {/* Main Pivot Table */}
      <div className="flex-1 overflow-y-auto rounded-lg border border-surface-border bg-[#0d121c]">
        {isLoading ? (
          <div className="p-12 text-center text-slate-400">Computing DuckDB aggregation matrix...</div>
        ) : (
          <table className="w-full text-left text-xs">
            <thead className="bg-[#090d14] text-[10px] text-slate-400 uppercase tracking-wider sticky top-0 border-b border-surface-border">
              <tr>
                <th onClick={() => handleSort("group_key")} className="px-4 py-3 cursor-pointer hover:text-white">
                  <div className="flex items-center space-x-1">
                    <span>Dimension Slice</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th onClick={() => handleSort("trades_count")} className="px-4 py-3 cursor-pointer hover:text-white">
                  Trades
                </th>
                <th onClick={() => handleSort("win_rate")} className="px-4 py-3 cursor-pointer hover:text-white">
                  Win Rate
                </th>
                <th onClick={() => handleSort("total_pnl")} className="px-4 py-3 cursor-pointer hover:text-white">
                  Total PnL
                </th>
                <th onClick={() => handleSort("avg_pnl")} className="px-4 py-3 cursor-pointer hover:text-white">
                  Avg PnL
                </th>
                <th onClick={() => handleSort("profit_factor")} className="px-4 py-3 cursor-pointer hover:text-white">
                  Profit Factor
                </th>
                <th onClick={() => handleSort("avg_r_multiple")} className="px-4 py-3 cursor-pointer hover:text-white">
                  Avg R
                </th>
                <th onClick={() => handleSort("sqn")} className="px-4 py-3 cursor-pointer hover:text-white">
                  SQN
                </th>
                <th onClick={() => handleSort("expectancy")} className="px-4 py-3 cursor-pointer hover:text-white">
                  Expectancy (EV)
                </th>
                <th onClick={() => handleSort("max_win")} className="px-4 py-3 text-right cursor-pointer hover:text-white">
                  Max Win / Loss
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/40 text-[11px]">
              {sortedRows.length === 0 ? (
                <tr>
                  <td colSpan={10} className="p-8 text-center text-slate-500">
                    No records found for current dimension grouping.
                  </td>
                </tr>
              ) : (
                sortedRows.map((r, idx) => {
                  const isProfit = r.total_pnl >= 0;
                  return (
                    <tr key={idx} className="hover:bg-[#111722] transition">
                      <td className="px-4 py-2.5 font-bold text-accent">{r.group_key}</td>
                      <td className="px-4 py-2.5 text-slate-200">{r.trades_count}</td>
                      <td className="px-4 py-2.5 font-semibold text-gain">{r.win_rate}%</td>
                      <td className={`px-4 py-2.5 font-bold ${isProfit ? "text-gain" : "text-loss"}`}>
                        {isProfit ? "+" : ""}${r.total_pnl.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-slate-300">${r.avg_pnl.toFixed(2)}</td>
                      <td className="px-4 py-2.5 text-white font-semibold">{r.profit_factor}</td>
                      <td className="px-4 py-2.5 font-semibold text-accent">+{r.avg_r_multiple}R</td>
                      <td className="px-4 py-2.5 font-bold text-purple-400">{r.sqn}</td>
                      <td className="px-4 py-2.5 font-bold text-gain">+${r.expectancy}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-[10px]">
                        <span className="text-gain">+${r.max_win}</span> / <span className="text-loss">${r.max_loss}</span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};