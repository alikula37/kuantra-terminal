import { useEffect, useRef, useCallback } from "react";
import { useMarketStore } from "../stores/marketStore";
import { useTradeStore } from "../stores/tradeStore";
import { wsUrl } from "../lib/backend";
import { getBridge } from "../lib/bridge";
import { openStream, subscribePush } from "../lib/push";
import type { MarketDataStatus } from "../types";

// Only used by the browser dev fallback; the desktop app has no HTTP/WS listener at all.
const getWsUrl = () => wsUrl("/api/v1/ws/stream");

export function normalizeMarketDataStatus(value: unknown): MarketDataStatus {
  return value === "LIVE" || value === "DEGRADED" || value === "UNAVAILABLE" ? value : "UNAVAILABLE";
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const pingIntervalRef = useRef<number | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  const { setConnectionStatus, setMarketDataStatus, updateTick, setMarketSnapshot, updateCandle } = useMarketStore();
  const { updatePositionPnl } = useTradeStore();

  const handleMessage = useCallback(
    (message: any) => {
      if (message.type === "TICK") {
        if (!Number.isFinite(message.price) || !Number.isFinite(message.timestamp) || !Number.isFinite(message.volume)) return;
        updateTick(
          message.price,
          Number.isFinite(message.event_age_ms) ? message.event_age_ms : null,
          message.timestamp,
          message.volume,
          message.side === "BUY" || message.side === "SELL" || message.side === "UNKNOWN" ? message.side : "UNKNOWN",
        );
        if (message.open_positions) {
          updatePositionPnl(message.open_positions);
        }
      } else if (message.type === "CANDLE_UPDATE") {
        updateCandle(message.data);
      } else if (message.type === "MARKET_DATA_STATUS") {
        setMarketDataStatus(normalizeMarketDataStatus(message.status));
      } else if (message.type === "SNAPSHOT") {
        setMarketSnapshot(
          Number.isFinite(message.last_price) ? message.last_price : null,
          Number.isFinite(message.event_age_ms) ? message.event_age_ms : null,
          Number.isFinite(message.timestamp) ? message.timestamp : null,
          normalizeMarketDataStatus(message.status),
        );
        if (message.open_positions) {
          updatePositionPnl(message.open_positions);
        }
      }
    },
    [updateTick, setMarketDataStatus, setMarketSnapshot, updateCandle, updatePositionPnl]
  );

  const connect = useCallback(() => {
    // Desktop: Python pushes batches into window.__kuantraPush; there is no socket.
    if (getBridge()) {
      if (unsubscribeRef.current) return;
      unsubscribeRef.current = subscribePush(handleMessage);
      openStream()
        .then((snap) => {
          if (snap) handleMessage(snap);
          setConnectionStatus(true);
        })
        .catch(() => {
          setConnectionStatus(false);
          // Drop the subscription first, otherwise the guard above short-circuits the retry.
          if (unsubscribeRef.current) {
            unsubscribeRef.current();
            unsubscribeRef.current = null;
          }
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect();
          }, 3000);
        });
      return;
    }

    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      const ws = new WebSocket(getWsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionStatus(true);
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, 15000);
      };

      ws.onmessage = (event) => {
        try {
          if (event.data === "pong") return;
          handleMessage(JSON.parse(event.data));
        } catch {
          // ignore
        }
      };

      ws.onclose = () => {
        setConnectionStatus(false);
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 2000);
      };

      ws.onerror = () => {
        setConnectionStatus(false);
        ws.close();
      };
    } catch {
      setConnectionStatus(false);
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, 3000);
    }
  }, [handleMessage, setConnectionStatus]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
        unsubscribeRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);
}
