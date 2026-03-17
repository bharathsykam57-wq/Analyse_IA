"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { BackendResult } from "@/shared/types/agent";

interface WebSocketMessage {
  type: "started" | "processing" | "progress" | "result" | "error";
  message?: string;
  data?: any;
  error?: string;
}

interface UseWebSocketReturn {
  status: string;
  message: string | null;
  result: BackendResult | null;
  error: string | null;
  isConnected: boolean;
  isUsingFallback: boolean;
}

/**
 * WebSocket hook for real-time task updates
 * Falls back to polling if WebSocket fails
 */
export function useWebSocket(
  taskId: string | null,
  onPollingFallback?: () => void
): UseWebSocketReturn {
  const [status, setStatus] = useState<string>("PENDING");
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<BackendResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isUsingFallback, setIsUsingFallback] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const getApiUrl = useCallback(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    // Convert http/https to ws/wss
    return apiUrl
      .replace(/^https?:\/\//, "ws://")
      .replace(/^wss?:/, "ws:");
  }, []);

  const getAuthToken = useCallback(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("access_token");
    }
    return null;
  }, []);

  const connectWebSocket = useCallback(() => {
    if (!taskId) return;

    const token = getAuthToken();
    if (!token) {
      console.warn("No auth token available for WebSocket");
      setIsUsingFallback(true);
      onPollingFallback?.();
      return;
    }

    try {
      const wsUrl = `${getApiUrl()}/ws/${taskId}?token=${token}`;
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log("WebSocket connected");
        setIsConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0;
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);

          switch (data.type) {
            case "started":
              setStatus("STARTED");
              setMessage("Task started");
              break;

            case "processing":
              setStatus("PROCESSING");
              setMessage(data.message || "Processing...");
              break;

            case "progress":
              setStatus("PROCESSING");
              setMessage(data.message || "In progress...");
              break;

            case "result":
              setStatus("SUCCESS");
              setResult(data.data);
              setMessage(null);
              break;

            case "error":
              setStatus("FAILURE");
              setError(data.error || "Task failed");
              break;

            default:
              console.warn("Unknown WebSocket message type:", data.type);
          }
        } catch (err) {
          console.error("Failed to parse WebSocket message:", err);
        }
      };

      wsRef.current.onerror = (event) => {
        console.error("WebSocket error:", event);
        setError("WebSocket connection error");
        setIsConnected(false);
      };

      wsRef.current.onclose = () => {
        console.log("WebSocket closed");
        setIsConnected(false);

        // Attempt reconnection with exponential backoff
        if (reconnectAttemptsRef.current < 3) {
          const backoffTime = Math.pow(2, reconnectAttemptsRef.current) * 1000;
          reconnectAttemptsRef.current += 1;

          reconnectTimeoutRef.current = setTimeout(() => {
            console.log(`Attempting WebSocket reconnection (attempt ${reconnectAttemptsRef.current})...`);
            connectWebSocket();
          }, backoffTime);
        } else {
          // After 3 reconnection attempts failed, fall back to polling
          console.warn("WebSocket reconnection failed after 3 attempts, falling back to polling");
          setIsUsingFallback(true);
          onPollingFallback?.();
        }
      };
    } catch (err) {
      console.error("Failed to create WebSocket:", err);
      setIsUsingFallback(true);
      onPollingFallback?.();
    }
  }, [taskId, getAuthToken, getApiUrl, onPollingFallback]);

  useEffect(() => {
    if (!taskId) return;

    connectWebSocket();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [taskId, connectWebSocket]);

  return {
    status,
    message,
    result,
    error,
    isConnected,
    isUsingFallback,
  };
}
