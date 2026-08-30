import { useEffect, useRef, useCallback } from "react";
import { useMarketStore } from "../stores/marketStore";
import { useTradeStore } from "../stores/tradeStore";

const WS_URL = "ws://127.0.0.1:8000/api/v1/ws/stream";

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const pingIntervalRef = useRef<number | null>(null);

  const { setConnectionStatus, updateTick, updateCandle } = useMarketStore();
  const { updatePositionPnl } = useTradeStore();

  const connect = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      const ws = new WebSocket(WS_URL);
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
          const message = JSON.parse(event.data);

          if (message.type === "TICK") {
            updateTick(
              message.price,
              message.latency_ms || 12,
              message.timestamp || Date.now(),
              message.volume
            );
            if (message.open_positions) {
              updatePositionPnl(message.open_positions);
            }
          } else if (message.type === "CANDLE_UPDATE") {
            updateCandle(message.data);
          } else if (message.type === "SNAPSHOT") {
            if (message.last_price) {
              updateTick(message.last_price, 12, Date.now());
            }
            if (message.open_positions) {
              updatePositionPnl(message.open_positions);
            }
          }
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
  }, [setConnectionStatus, updateTick, updateCandle, updatePositionPnl]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  useEffect(() => {
    let mockInterval: number | null = null;
    const checkMock = () => {
      const isConnected = useMarketStore.getState().isConnected;
      if (!isConnected && !mockInterval) {
        let basePrice = 65200.0;
        mockInterval = window.setInterval(() => {
          if (!useMarketStore.getState().isConnected) {
            const delta = (Math.random() - 0.49) * 15;
            basePrice += delta;
            updateTick(Number(basePrice.toFixed(2)), Math.floor(Math.random() * 15) + 8, Date.now(), Number((Math.random() * 1.5).toFixed(4)));
          }
        }, 150);
      } else if (isConnected && mockInterval) {
        clearInterval(mockInterval);
        mockInterval = null;
      }
    };

    const interval = setInterval(checkMock, 1000);
    return () => {
      clearInterval(interval);
      if (mockInterval) clearInterval(mockInterval);
    };
  }, [updateTick]);
}