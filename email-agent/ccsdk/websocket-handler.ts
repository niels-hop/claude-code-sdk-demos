import { Database } from "bun:sqlite";
import { Session } from "./session";
import type { WSClient, IncomingMessage } from "./types";
import { DATABASE_PATH } from "../database/config";
import { PythonBackendProxy } from "./python-proxy";

// Main WebSocket handler class
export class WebSocketHandler {
  private db: Database;
  private sessions: Map<string, Session> = new Map();
  private clients: Map<string, WSClient> = new Map();
  private pythonProxy: PythonBackendProxy;
  private usePythonBackend: boolean;

  constructor(dbPath: string = DATABASE_PATH, usePythonBackend: boolean = true) {
    this.db = new Database(dbPath);
    this.usePythonBackend = usePythonBackend;
    this.pythonProxy = new PythonBackendProxy();

    // Connect to Python backend if enabled
    if (this.usePythonBackend) {
      this.pythonProxy.connect().then(() => {
        console.log("[WebSocketHandler] Python backend proxy connected");
      }).catch(err => {
        console.error("[WebSocketHandler] Failed to connect to Python backend:", err);
        console.log("[WebSocketHandler] Falling back to TypeScript backend");
        this.usePythonBackend = false;
      });
    }

    this.initEmailWatcher();
  }

  private async initEmailWatcher() {
    // Poll for email updates every 5 seconds
    setInterval(() => {
      this.broadcastInboxUpdate();
    }, 5000);

    // Send initial inbox on first load
    this.broadcastInboxUpdate();
  }

  private async getRecentEmails(limit: number = 30) {
    try {
      const emails = this.db.prepare(`
        SELECT
          message_id as id,
          message_id,
          subject,
          from_address,
          from_name,
          date_sent,
          snippet,
          is_read,
          is_starred,
          has_attachments,
          folder
        FROM emails
        ORDER BY date_sent DESC
        LIMIT ?
      `).all(limit);

      return emails;
    } catch (error) {
      console.error('Error fetching recent emails:', error);
      return [];
    }
  }

  private async broadcastInboxUpdate() {
    const emails = await this.getRecentEmails();
    const message = JSON.stringify({
      type: 'inbox_update',
      emails
    });

    // Broadcast to all connected clients
    for (const client of this.clients.values()) {
      try {
        client.send(message);
      } catch (error) {
        console.error('Error sending inbox update to client:', error);
      }
    }
  }

  private generateSessionId(): string {
    return 'session-' + Date.now() + '-' + Math.random().toString(36).substring(7);
  }

  private getOrCreateSession(sessionId?: string): Session {
    if (sessionId && this.sessions.has(sessionId)) {
      return this.sessions.get(sessionId)!;
    }

    const newSessionId = sessionId || this.generateSessionId();
    const session = new Session(newSessionId, this.db);
    this.sessions.set(newSessionId, session);
    return session;
  }

  public async onOpen(ws: WSClient) {
    const clientId = Date.now().toString() + '-' + Math.random().toString(36).substring(7);
    this.clients.set(clientId, ws);
    console.log('WebSocket client connected:', clientId);

    ws.send(JSON.stringify({
      type: 'connected',
      message: 'Connected to email assistant',
      availableSessions: Array.from(this.sessions.keys())
    }));

    // Send initial inbox
    const emails = await this.getRecentEmails();
    ws.send(JSON.stringify({
      type: 'inbox_update',
      emails
    }));
  }

  public async onMessage(ws: WSClient, message: string) {
    try {
      const data = JSON.parse(message) as IncomingMessage;

      switch (data.type) {
        case 'chat': {
          // Forward chat messages to Python backend if enabled
          if (this.usePythonBackend && this.pythonProxy.isConnected()) {
            console.log("[WebSocketHandler] Forwarding chat to Python backend");
            await this.pythonProxy.forwardChatMessage(ws, data);
          } else {
            // Fallback to TypeScript backend
            console.log("[WebSocketHandler] Using TypeScript backend (Python unavailable)");
            const session = this.getOrCreateSession(data.sessionId);

            // Auto-subscribe the sender to the session
            if (!ws.data.sessionId || ws.data.sessionId !== session.id) {
              session.subscribe(ws);
            }

            // Check if this is a request to start a new conversation
            if (data.newConversation) {
              session.endConversation();
            }

            // Add the user message to the session
            await session.addUserMessage(data.content);
          }
          break;
        }

        case 'subscribe': {
          // Subscribe to a specific session
          const session = this.sessions.get(data.sessionId);
          if (session) {
            // Unsubscribe from current session if any
            if (ws.data.sessionId && ws.data.sessionId !== data.sessionId) {
              const currentSession = this.sessions.get(ws.data.sessionId);
              currentSession?.unsubscribe(ws);
            }

            session.subscribe(ws);
            ws.send(JSON.stringify({
              type: 'subscribed',
              sessionId: data.sessionId
            }));
          } else {
            ws.send(JSON.stringify({
              type: 'error',
              error: 'Session not found'
            }));
          }
          break;
        }

        case 'unsubscribe': {
          // Unsubscribe from a session
          const session = this.sessions.get(data.sessionId);
          if (session) {
            session.unsubscribe(ws);
            ws.data.sessionId = '';
            ws.send(JSON.stringify({
              type: 'unsubscribed',
              sessionId: data.sessionId
            }));
          }
          break;
        }

        case 'request_inbox': {
          // Send current inbox to requesting client
          const emails = await this.getRecentEmails();
          ws.send(JSON.stringify({
            type: 'inbox_update',
            emails
          }));
          break;
        }

        default:
          ws.send(JSON.stringify({
            type: 'error',
            error: 'Unknown message type'
          }));
      }
    } catch (error) {
      console.error('WebSocket error:', error);
      ws.send(JSON.stringify({
        type: 'error',
        error: 'Failed to process message'
      }));
    }
  }

  public onClose(ws: WSClient) {
    // Unsubscribe from any session
    if (ws.data.sessionId) {
      const session = this.sessions.get(ws.data.sessionId);
      session?.unsubscribe(ws);
    }

    // Remove from clients map
    const clientsArray = Array.from(this.clients.entries());
    for (const [id, client] of clientsArray) {
      if (client === ws) {
        this.clients.delete(id);
        console.log('WebSocket client disconnected:', id);
        break;
      }
    }

    // Clean up empty sessions
    this.cleanupEmptySessions();
  }

  private cleanupEmptySessions() {
    for (const [id, session] of this.sessions) {
      if (!session.hasSubscribers()) {
        // Keep session for a grace period (could be made configurable)
        setTimeout(() => {
          if (!session.hasSubscribers()) {
            session.cleanup();
            this.sessions.delete(id);
            console.log('Cleaned up empty session:', id);
          }
        }, 60000); // 1 minute grace period
      }
    }
  }

  public getActiveSessionsCount(): number {
    return this.sessions.size;
  }

  public getActiveSessions(): string[] {
    return Array.from(this.sessions.keys());
  }

  public cleanup() {
    // Clean up sessions
    for (const session of this.sessions.values()) {
      session.cleanup();
    }
  }
}