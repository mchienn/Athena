import {
  collection,
  doc,
  onSnapshot,
  orderBy,
  query,
  setDoc,
  Timestamp,
  updateDoc,
  type DocumentData,
  type QueryDocumentSnapshot,
  type Unsubscribe,
} from 'firebase/firestore';
import type { AssistantMessage, ChatSummary } from '../types';
import { getFirebaseServices } from './firebaseClient';

const DEFAULT_CHAT_TITLE = 'Cuộc trò chuyện mới';

function timestampToMillis(value: unknown): number {
  return value instanceof Timestamp ? value.toMillis() : Date.now();
}

function mapChat(snapshot: QueryDocumentSnapshot<DocumentData>): ChatSummary {
  const data = snapshot.data();
  return {
    id: snapshot.id,
    title: typeof data.title === 'string' ? data.title : DEFAULT_CHAT_TITLE,
    createdAt: timestampToMillis(data.createdAt),
    updatedAt: timestampToMillis(data.updatedAt),
  };
}

function mapMessage(snapshot: QueryDocumentSnapshot<DocumentData>): AssistantMessage {
  const data = snapshot.data();
  return {
    id: snapshot.id,
    role: data.role === 'user' ? 'user' : 'assistant',
    intent: data.intent || 'general',
    answer: typeof data.answer === 'string' ? data.answer : '',
    actions: Array.isArray(data.actions) ? data.actions : [],
    structured_data: data.structured_data || {},
    emergency: data.emergency === true,
    citations: Array.isArray(data.citations) ? data.citations : [],
  } as AssistantMessage;
}

function createTitle(text: string): string {
  const compact = text.replace(/\s+/g, ' ').trim();
  return compact.length > 48 ? `${compact.slice(0, 48)}…` : compact;
}

export const chatRepository = {
  defaultTitle: DEFAULT_CHAT_TITLE,

  subscribeActiveChat(
    userId: string,
    onData: (chatId: string) => void,
    onError: (error: Error) => void,
  ): Unsubscribe {
    const { firestore } = getFirebaseServices();
    return onSnapshot(
      doc(firestore, 'users', userId, 'chat_settings', 'current'),
      (snapshot) => {
        const activeChatId = snapshot.data()?.activeChatId;
        onData(typeof activeChatId === 'string' ? activeChatId : '');
      },
      (error) => onError(error),
    );
  },

  subscribeChats(
    userId: string,
    onData: (chats: ChatSummary[]) => void,
    onError: (error: Error) => void,
  ): Unsubscribe {
    const { firestore } = getFirebaseServices();
    const chatsQuery = query(
      collection(firestore, 'users', userId, 'chats'),
      orderBy('updatedAt', 'desc'),
    );
    return onSnapshot(
      chatsQuery,
      (snapshot) => onData(snapshot.docs.map(mapChat)),
      (error) => onError(error),
    );
  },

  subscribeMessages(
    userId: string,
    chatId: string,
    onData: (messages: AssistantMessage[]) => void,
    onError: (error: Error) => void,
  ): Unsubscribe {
    const { firestore } = getFirebaseServices();
    const messagesQuery = query(
      collection(firestore, 'users', userId, 'chats', chatId, 'messages'),
      orderBy('createdAt', 'asc'),
    );
    return onSnapshot(
      messagesQuery,
      (snapshot) => onData(snapshot.docs.map(mapMessage)),
      (error) => onError(error),
    );
  },

  async createChat(userId: string): Promise<ChatSummary> {
    const { firestore } = getFirebaseServices();
    const chatRef = doc(collection(firestore, 'users', userId, 'chats'));
    const now = Timestamp.now();
    await setDoc(chatRef, {
      title: DEFAULT_CHAT_TITLE,
      adkUserId: userId,
      adkSessionId: chatRef.id,
      createdAt: now,
      updatedAt: now,
    });
    await chatRepository.setActiveChat(userId, chatRef.id);
    return { id: chatRef.id, title: DEFAULT_CHAT_TITLE, createdAt: now.toMillis(), updatedAt: now.toMillis() };
  },

  async setActiveChat(userId: string, chatId: string): Promise<void> {
    const { firestore } = getFirebaseServices();
    await setDoc(
      doc(firestore, 'users', userId, 'chat_settings', 'current'),
      { activeChatId: chatId, updatedAt: Timestamp.now() },
      { merge: true },
    );
  },

  async saveMessage(userId: string, chatId: string, message: AssistantMessage): Promise<void> {
    const { firestore } = getFirebaseServices();
    const messageRef = doc(
      firestore,
      'users',
      userId,
      'chats',
      chatId,
      'messages',
      message.id,
    );
    const cleanMessage = JSON.parse(JSON.stringify(message)) as AssistantMessage;
    await setDoc(messageRef, { ...cleanMessage, createdAt: Timestamp.now() });
    await updateDoc(doc(firestore, 'users', userId, 'chats', chatId), {
      updatedAt: Timestamp.now(),
    });
  },

  async updateTitle(userId: string, chatId: string, text: string): Promise<void> {
    const { firestore } = getFirebaseServices();
    await updateDoc(doc(firestore, 'users', userId, 'chats', chatId), {
      title: createTitle(text),
      updatedAt: Timestamp.now(),
    });
  },
};
