import { isPlatformBrowser } from '@angular/common';
import { Injectable, NgZone, PLATFORM_ID, inject, signal } from '@angular/core';
import { Subject } from 'rxjs';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { environment } from '../../environments/environment';
import {
  AgentSocketCommand,
  AgentStopPayload,
  AgentStreamEvent,
  AgentUserMessagePayload,
} from '../models/agent-stream-event.model';

export type AgentConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';

@Injectable({ providedIn: 'root' })
export class AiStreamService {
  private readonly zone = inject(NgZone);
  private readonly platformId = inject(PLATFORM_ID);
  private socket$?: WebSocketSubject<AgentStreamEvent | AgentSocketCommand>;
  private readonly eventsSubject = new Subject<AgentStreamEvent>();
  private readonly connectionStateSignal = signal<AgentConnectionStatus>('disconnected');
  private reconnectTimer?: ReturnType<typeof setTimeout>;
  private manualClose = false;
  private readonly reconnectDelayMs = 1500;

  /** Emits stream events as they arrive from the backend. */
  readonly events$ = this.eventsSubject.asObservable();
  readonly connectionState = this.connectionStateSignal.asReadonly();

  constructor() {
    if (isPlatformBrowser(this.platformId)) {
      this.connect();
    }
  }

  private connect(): void {
    if (!environment.agentSocketUrl) {
      console.warn('agentSocketUrl is not configured. Please update src/environments.');
      return;
    }

    const reconnecting = !!this.socket$;
    this.disposeSocket();
    this.connectionStateSignal.set(reconnecting ? 'reconnecting' : 'connecting');

    this.socket$ = webSocket<AgentStreamEvent | AgentSocketCommand>({
      url: environment.agentSocketUrl,
      deserializer: (e) => {
        try {
          return typeof e.data === 'string' ? JSON.parse(e.data) : e.data;
        } catch (error) {
          console.error('Failed to parse stream event', error);
          return null;
        }
      },
      openObserver: {
        next: () => this.zone.run(() => this.connectionStateSignal.set('connected')),
      },
      closeObserver: {
        next: () => this.zone.run(() => this.handleDisconnect()),
      },
    });

    this.socket$.subscribe({
      next: (payload) => this.zone.run(() => this.dispatch(payload)),
      error: (error) => this.zone.run(() => this.handleError(error)),
    });
  }

  private dispatch(payload: AgentStreamEvent | AgentSocketCommand | null): void {
    if (!payload || !('type' in payload)) {
      return;
    }

    if (typeof payload.type === 'string' && payload.type.startsWith('response')) {
      this.eventsSubject.next(payload as AgentStreamEvent);
    }
  }

  private handleDisconnect(): void {
    if (this.manualClose) {
      this.connectionStateSignal.set('disconnected');
      this.manualClose = false;
      return;
    }

    this.connectionStateSignal.set('disconnected');
    this.scheduleReconnect();
  }

  private handleError(error: unknown): void {
    console.error('AI stream socket error', error);
    this.connectionStateSignal.set('disconnected');
    this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer || !isPlatformBrowser(this.platformId)) {
      return;
    }

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = undefined;
      this.connect();
    }, this.reconnectDelayMs);
  }

  sendUserPrompt(payload: AgentUserMessagePayload): void {
    this.send({ type: 'user-message', ...payload });
  }

  stopResponse(payload: AgentStopPayload): void {
    this.send({ type: 'stop-response', ...payload });
  }

  startNewSession(conversationId: string): void {
    this.send({ type: 'new-session', conversationId });
  }

  private send(command: AgentSocketCommand): void {
    if (!this.socket$ || this.connectionStateSignal() === 'disconnected') {
      this.connect();
    }

    try {
      this.socket$?.next(command);
    } catch (error) {
      console.error('Failed to send command to AI agent', error);
    }
  }

  disconnect(): void {
    this.manualClose = true;
    this.disposeSocket();
  }

  private disposeSocket(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = undefined;
    }

    this.socket$?.complete();
    this.socket$ = undefined;
  }
}
