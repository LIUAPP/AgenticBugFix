import { CommonModule, isPlatformBrowser } from '@angular/common';
import {
  Component,
  ElementRef,
  PLATFORM_ID,
  ViewChild,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  AgentResponseStatus,
  AgentStreamEvent,
} from './models/agent-stream-event.model';
import { AiStreamService, AgentConnectionStatus } from './services/ai-stream.service';

type MessageRole = 'user' | 'agent';

interface ConversationMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: number;
  responseId?: string;
  status?: AgentResponseStatus;
  tokens?: string[];
  isStreaming?: boolean;
  finished?: boolean;
  visible: boolean;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  @ViewChild('scrollContainer') private scrollContainer?: ElementRef<HTMLDivElement>;

  private readonly platformId = inject(PLATFORM_ID);
  private readonly aiStream = inject(AiStreamService);

  protected readonly composerControl = new FormControl('', { nonNullable: true });
  protected readonly messages = signal<ConversationMessage[]>([]);
  protected readonly conversationId = signal(this.createConversationId());
  protected readonly connectionState = this.aiStream.connectionState;
  protected readonly hasStreamingResponse = computed(() =>
    this.messages().some((message) => message.role === 'agent' && message.isStreaming)
  );
  protected readonly connectionCopy: Record<AgentConnectionStatus, string> = {
    connected: 'Connected',
    connecting: 'Connecting',
    disconnected: 'Offline',
    reconnecting: 'Reconnecting',
  };
  protected readonly statusLabels: Record<AgentResponseStatus, string> = {
    queued: 'Queued',
    thinking: 'Thinking',
    streaming: 'Streaming',
    completed: 'Completed',
    error: 'Error',
    stopped: 'Stopped',
  };

  private scrollAnimationHandle?: number;

  constructor() {
    this.aiStream.events$
      .pipe(takeUntilDestroyed())
      .subscribe((event) => this.handleStreamEvent(event));

    if (isPlatformBrowser(this.platformId)) {
      effect(() => {
        this.messages();
        this.queueScrollToBottom();
      });
    }

    Promise.resolve().then(() => this.aiStream.startNewSession(this.conversationId()));
  }

  protected trackByMessageId(_: number, item: ConversationMessage): string {
    return item.id;
  }

  protected statusClass(status?: AgentResponseStatus): string {
    return `status-${status ?? 'thinking'}`;
  }

  protected submitPrompt(): void {
    const rawValue = this.composerControl.value.trim();
    if (!rawValue) {
      this.composerControl.setValue('');
      return;
    }

    const message: ConversationMessage = {
      id: this.createMessageId(),
      role: 'user',
      content: rawValue,
      createdAt: Date.now(),
      visible: true,
    };

    this.messages.update((current) => [...current, message]);
    this.aiStream.sendUserPrompt({
      conversationId: this.conversationId(),
      prompt: rawValue,
    });
    this.composerControl.setValue('');
  }

  protected handleComposerEnter(event: Event): void {
    const keyboardEvent = event as KeyboardEvent;
    if (keyboardEvent.shiftKey) {
      return;
    }

    keyboardEvent.preventDefault();
    this.submitPrompt();
  }

  protected stopStreaming(): void {
    const active = [...this.messages()]
      .reverse()
      .find((message) => message.role === 'agent' && message.isStreaming);

    if (!active?.responseId) {
      return;
    }

    this.aiStream.stopResponse({
      conversationId: this.conversationId(),
      responseId: active.responseId,
      reason: 'user-request',
    });

    this.messages.update((current) => {
      const updated = [...current];
      const index = updated.findIndex((message) => message.id === active.id);
      if (index === -1) {
        return current;
      }

      updated[index] = {
        ...updated[index],
        status: 'stopped',
        isStreaming: false,
        finished: true,
      };

      return this.releaseQueuedAgentResponses(updated);
    });
  }

  protected startNewChat(): void {
    const freshConversationId = this.createConversationId();
    this.conversationId.set(freshConversationId);
    this.messages.set([]);
    this.composerControl.setValue('');
    this.aiStream.startNewSession(freshConversationId);
  }

  private handleStreamEvent(event: AgentStreamEvent): void {
    if (event.conversationId !== this.conversationId()) {
      return;
    }

    this.messages.update((current) => {
      const updated = [...current];
      const index = this.ensureAgentMessage(updated, event);
      if (index === -1) {
        return current;
      }

      const target = updated[index];
      let nextMessage = target;

      switch (event.type) {
        case 'response-start':
          nextMessage = {
            ...target,
            status: event.status ?? 'thinking',
            isStreaming: true,
            createdAt: target.createdAt ?? Date.now(),
          };
          break;
        case 'response-token':
          nextMessage = {
            ...target,
            status: 'streaming',
            isStreaming: true,
            tokens: [...(target.tokens ?? []), event.token ?? ''],
            content: `${target.content ?? ''}${event.token ?? ''}`,
          };
          break;
        case 'response-status':
          nextMessage = {
            ...target,
            status: event.status ?? target.status,
            isStreaming: event.status === 'thinking' || event.status === 'streaming',
          };
          break;
        case 'response-end':
          nextMessage = {
            ...target,
            status: event.status ?? 'completed',
            isStreaming: false,
            finished: true,
            content: event.content ?? target.content ?? '',
          };
          break;
        case 'response-error':
          nextMessage = {
            ...target,
            status: 'error',
            isStreaming: false,
            finished: true,
          };
          break;
        case 'response-stop':
          nextMessage = {
            ...target,
            status: 'stopped',
            isStreaming: false,
            finished: true,
          };
          break;
      }

      updated[index] = nextMessage;
      if (nextMessage.finished) {
        return this.releaseQueuedAgentResponses(updated);
      }

      return updated;
    });
  }

  private ensureAgentMessage(messages: ConversationMessage[], event: AgentStreamEvent): number {
    const existingIndex = messages.findIndex(
      (message) => message.responseId === event.responseId && message.role === 'agent'
    );

    if (existingIndex !== -1) {
      return existingIndex;
    }

    const hasActiveAgent = messages.some(
      (message) => message.role === 'agent' && !message.finished
    );

    const initialStatus: AgentResponseStatus =
      event.status ?? (event.type === 'response-token' ? 'streaming' : 'thinking');

    const insertion: ConversationMessage = {
      id: event.responseId ?? this.createMessageId(),
      role: 'agent',
      responseId: event.responseId,
      createdAt: Date.now(),
      content: event.content ?? '',
      tokens: event.tokens ?? [],
      status: initialStatus,
      isStreaming: initialStatus === 'thinking' || initialStatus === 'streaming',
      finished: false,
      visible: !hasActiveAgent,
    };

    messages.push(insertion);
    return messages.length - 1;
  }

  private releaseQueuedAgentResponses(messages: ConversationMessage[]): ConversationMessage[] {
    const hiddenIndex = messages.findIndex(
      (message) => message.role === 'agent' && !message.visible
    );

    if (hiddenIndex === -1) {
      return messages;
    }

    const previousAgent = [...messages]
      .slice(0, hiddenIndex)
      .reverse()
      .find((message) => message.role === 'agent');

    if (!previousAgent || previousAgent.finished) {
      const target = messages[hiddenIndex];
      const cloned = [...messages];
      cloned[hiddenIndex] = { ...target, visible: true };
      return cloned;
    }

    return messages;
  }

  private queueScrollToBottom(): void {
    if (!isPlatformBrowser(this.platformId)) {
      return;
    }

    if (this.scrollAnimationHandle) {
      cancelAnimationFrame(this.scrollAnimationHandle);
    }

    this.scrollAnimationHandle = requestAnimationFrame(() => {
      this.scrollAnimationHandle = undefined;
      const container = this.scrollContainer?.nativeElement;
      if (!container) {
        return;
      }

      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth',
      });
    });
  }

  private createConversationId(): string {
    return typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `conversation-${Date.now()}`;
  }

  private createMessageId(): string {
    return typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `message-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }
}
