import type { WSClient } from "./types";

/**
 * Proxy client that forwards chat messages to Python backend
 * and relays responses back to the frontend client
 */
export class PythonBackendProxy {
  private pythonWs: WebSocket | null = null;
  private reconnectTimeout: Timer | null = null;
  private isConnecting = false;
  private messageQueue: any[] = [];

  private readonly pythonBackendUrl: string;

  constructor(pythonBackendUrl: string = "ws://127.0.0.1:3001/ws") {
    this.pythonBackendUrl = pythonBackendUrl;
  }

  async connect(): Promise<void> {
    if (this.pythonWs && this.pythonWs.readyState === WebSocket.OPEN) {
      console.log("[PythonProxy] Already connected");
      return;
    }

    if (this.isConnecting) {
      console.log("[PythonProxy] Connection already in progress");
      return;
    }

    this.isConnecting = true;

    return new Promise((resolve, reject) => {
      try {
        console.log(`[PythonProxy] Connecting to Python backend: ${this.pythonBackendUrl}`);
        this.pythonWs = new WebSocket(this.pythonBackendUrl);

        this.pythonWs.onopen = () => {
          console.log("[PythonProxy] Connected to Python backend");
          this.isConnecting = false;

          // Process queued messages
          while (this.messageQueue.length > 0) {
            const msg = this.messageQueue.shift();
            this.sendToPython(msg);
          }

          resolve();
        };

        this.pythonWs.onerror = (error) => {
          console.error("[PythonProxy] WebSocket error:", error);
          this.isConnecting = false;
        };

        this.pythonWs.onclose = () => {
          console.log("[PythonProxy] Connection closed, will reconnect in 5s");
          this.pythonWs = null;
          this.isConnecting = false;

          // Auto-reconnect after 5 seconds
          this.reconnectTimeout = setTimeout(() => {
            this.connect().catch(err => {
              console.error("[PythonProxy] Reconnect failed:", err);
            });
          }, 5000);
        };

        // Timeout if connection takes too long
        setTimeout(() => {
          if (this.isConnecting) {
            this.isConnecting = false;
            if (this.pythonWs && this.pythonWs.readyState !== WebSocket.OPEN) {
              this.pythonWs.close();
            }
            reject(new Error("Connection timeout"));
          }
        }, 10000);

      } catch (error) {
        this.isConnecting = false;
        reject(error);
      }
    });
  }

  isConnected(): boolean {
    return this.pythonWs !== null && this.pythonWs.readyState === WebSocket.OPEN;
  }

  /**
   * Forward a chat message to Python backend
   */
  async forwardChatMessage(
    frontendClient: WSClient,
    message: any
  ): Promise<void> {
    if (!this.isConnected()) {
      console.log("[PythonProxy] Not connected, queueing message");
      this.messageQueue.push(message);

      // Try to connect if not already connecting
      if (!this.isConnecting) {
        this.connect().catch(err => {
          console.error("[PythonProxy] Failed to connect:", err);
          // Send error to frontend
          frontendClient.send(JSON.stringify({
            type: 'error',
            error: 'Python backend unavailable. Using TypeScript backend as fallback.',
            usingFallback: true
          }));
        });
      }
      return;
    }

    // Set up message handler for responses from Python
    if (this.pythonWs) {
      // Remove previous listeners to avoid duplicates
      this.pythonWs.onmessage = (event) => {
        try {
          // Forward response to frontend client
          frontendClient.send(event.data);
        } catch (error) {
          console.error("[PythonProxy] Error forwarding response:", error);
        }
      };
    }

    // Forward the message to Python
    this.sendToPython(message);
  }

  private sendToPython(message: any): void {
    if (!this.isConnected() || !this.pythonWs) {
      console.error("[PythonProxy] Cannot send, not connected");
      return;
    }

    try {
      const messageStr = typeof message === 'string' ? message : JSON.stringify(message);
      this.pythonWs.send(messageStr);
      console.log(`[PythonProxy] Forwarded message type: ${typeof message === 'string' ? JSON.parse(message).type : message.type}`);
    } catch (error) {
      console.error("[PythonProxy] Error sending to Python:", error);
    }
  }

  disconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.pythonWs) {
      this.pythonWs.close();
      this.pythonWs = null;
    }

    console.log("[PythonProxy] Disconnected");
  }
}
