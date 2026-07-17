import type { AssistantMessage } from '../types';
import { adkClient } from './adkClient';

export const assistantService = {
  ensureSession(userId: string, sessionId: string): Promise<void> {
    return adkClient.ensureSession(userId, sessionId);
  },

  send(userId: string, sessionId: string, text: string): Promise<AssistantMessage> {
    return adkClient.sendMessage(userId, sessionId, text);
  },
};
