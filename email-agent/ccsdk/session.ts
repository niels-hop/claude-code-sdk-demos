import { Database } from "bun:sqlite";
import * as path from "path";
import { MessageQueue } from "./message-queue";
import type { WSClient, SDKUserMessage, SDKMessage } from "./types";
import { AIClient } from "./ai-client";

// Session class to manage a single Claude conversation
export class Session {
  public readonly id: string;
  private messageQueue: MessageQueue<SDKUserMessage>;
  private queryPromise: Promise<void> | null = null;
  private subscribers: Set<WSClient> = new Set();
  private db: Database;
  private messageCount = 0;
  private aiClient: AIClient;

  constructor(id: string, db: Database) {
    this.id = id;
    this.db = db;
    this.messageQueue = new MessageQueue();
    this.aiClient = new AIClient();
  }

  // Create async generator for streaming input mode
  private async *createMessageGenerator(): AsyncIterable<SDKUserMessage> {
    while (true) {
      const result = await this.messageQueue.next();
      if (result.done) {
        break;
      }
      yield result.value;
    }
  }

  // Start the Claude query with streaming input
  async startQuery() {
    if (this.queryPromise) {
      return; // Query already running
    }

    const messageGenerator = this.createMessageGenerator();

    console.log("starting query!");

    this.queryPromise = (async () => {
      try {
        for await (const message of this.aiClient.queryStream(messageGenerator)) {
          console.log(message);
          this.broadcastToSubscribers(message);
        }
      } catch (error) {
        console.error(`Error in session ${this.id}:`, error);
        this.broadcastError("Query failed: " + (error as Error).message);
      } finally {
        this.queryPromise = null;
        this.messageQueue.close();
      }
    })();
  }

  // Add a user message to the session
  async addUserMessage(content: string): Promise<void> {
    if (this.messageQueue.isClosed()) {
      // Create a new message queue for a new conversation
      this.messageQueue = new MessageQueue();
    }

    const userMessage: SDKUserMessage = {
      type: 'user',
      message: {
        role: 'user',
        content: content
      },
      session_id: this.id,
      parent_tool_use_id: null
    };

    await this.messageQueue.push(userMessage);
    this.messageCount++;

    // Start query if not already running
    if (!this.queryPromise) {
      this.startQuery();
    }
  }

  // Subscribe a WebSocket client to this session
  subscribe(client: WSClient) {
    this.subscribers.add(client);
    client.data.sessionId = this.id;

    // Send session info to new subscriber
    client.send(JSON.stringify({
      type: 'session_info',
      sessionId: this.id,
      messageCount: this.messageCount,
      isActive: this.queryPromise !== null
    }));
  }

  // Unsubscribe a WebSocket client from this session
  unsubscribe(client: WSClient) {
    this.subscribers.delete(client);
  }

  // Broadcast a message to all subscribers
  private broadcastToSubscribers(message: SDKMessage) {
    let wsMessage: any = null;

    if (message.type === "assistant") {
      // Stream assistant responses
      const content = message.message.content;
      if (typeof content === 'string') {
        wsMessage = {
          type: 'assistant_message',
          content: content,
          sessionId: this.id
        };
      } else if (Array.isArray(content)) {
        // Handle content blocks
        for (const block of content) {
          if (block.type === 'text') {
            wsMessage = {
              type: 'assistant_message',
              content: block.text,
              sessionId: this.id
            };
          } else if (block.type === 'tool_use') {
            wsMessage = {
              type: 'tool_use',
              toolName: block.name,
              toolId: block.id,
              toolInput: block.input,
              sessionId: this.id
            };
          } else if (block.type === 'tool_result') {
            wsMessage = {
              type: 'tool_result',
              toolUseId: block.tool_use_id,
              content: block.content,
              isError: block.is_error,
              sessionId: this.id
            };
          }
          if (wsMessage) {
            this.broadcast(wsMessage);
          }
        }
        return; // Already broadcasted block by block
      }
    } else if (message.type === "result") {
      if (message.subtype === "success") {
        wsMessage = {
          type: 'result',
          success: true,
          result: message.result,
          cost: message.total_cost_usd,
          duration: message.duration_ms,
          sessionId: this.id
        };
      } else {
        wsMessage = {
          type: 'result',
          success: false,
          error: message.subtype,
          sessionId: this.id
        };
      }
    } else if (message.type === "system") {
      wsMessage = {
        type: 'system',
        subtype: message.subtype,
        sessionId: this.id,
        data: message
      };
    } else if (message.type === "user") {
      // Echo user messages to subscribers
      wsMessage = {
        type: 'user_message',
        content: message.message.content,
        sessionId: this.id
      };
    }

    if (wsMessage) {
      this.broadcast(wsMessage);
    }
  }

  private broadcast(message: any) {
    const messageStr = JSON.stringify(message);
    for (const client of this.subscribers) {
      try {
        client.send(messageStr);
      } catch (error) {
        console.error('Error broadcasting to client:', error);
        this.subscribers.delete(client);
      }
    }
  }

  private broadcastError(error: string) {
    this.broadcast({
      type: 'error',
      error: error,
      sessionId: this.id
    });
  }

  // Check if session has any subscribers
  hasSubscribers(): boolean {
    return this.subscribers.size > 0;
  }

  // Clean up session
  async cleanup() {
    this.messageQueue.close();
    this.subscribers.clear();
  }
}