export type AgentResponseStatus =
  | 'queued'
  | 'thinking'
  | 'streaming'
  | 'completed'
  | 'celebrating'
  | 'error'
  | 'stopped';

export type AgentStreamEventType =
  | 'response-start'
  | 'response-token'
  | 'response-status'
  | 'response-end'
  | 'response-error'
  | 'response-stop'
  | 'response-celebration';

export interface AgentStreamEvent {
  conversationId: string;
  responseId: string;
  type: AgentStreamEventType;
  status?: AgentResponseStatus;
  token?: string;
  tokens?: string[];
  content?: string;
  metadata?: Record<string, unknown>;
}

export interface AgentUserMessagePayload {
  conversationId: string;
  prompt: string;
  attachments?: unknown[];
  metadata?: Record<string, unknown>;
}

export interface AgentStopPayload {
  conversationId: string;
  responseId?: string;
  reason?: string;
}

export type AgentSocketCommand =
  | ({ type: 'user-message' } & AgentUserMessagePayload)
  | ({ type: 'stop-response' } & AgentStopPayload)
  | ({ type: 'new-session'; conversationId: string } & Record<string, unknown>);
