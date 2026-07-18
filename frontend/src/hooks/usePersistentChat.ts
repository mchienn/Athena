import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { AssistantMessage, ChatSummary } from '../types';
import { assistantService } from '../services/assistantService';
import { chatRepository } from '../services/chatRepository';
import { getChatUserId } from '../services/firebaseClient';

const welcomeMessage: AssistantMessage = {
  id: 'assistant-welcome',
  role: 'assistant',
  intent: 'general',
  answer:
    'Xin chào! Tôi là trợ lý Bệnh viện Tim Hà Nội. Tôi có thể hỗ trợ thông tin bác sĩ, lịch khám và quy trình đặt lịch.',
  actions: [],
  structured_data: {},
  emergency: false,
  citations: [],
};

function userMessage(text: string): AssistantMessage {
  return {
    id: crypto.randomUUID(),
    role: 'user',
    intent: 'general',
    answer: text,
    actions: [],
    structured_data: {},
    emergency: false,
    citations: [],
  };
}

function errorMessage(error: unknown): string {
  const code = typeof error === 'object' && error !== null && 'code' in error
    ? String(error.code)
    : '';
  if (code === 'permission-denied' || code === 'firestore/permission-denied') {
    return 'Tài khoản chưa có quyền đọc hoặc ghi lịch sử chat trên Firestore. Hãy deploy firestore.rules cho đúng Firebase project.';
  }
  return error instanceof Error ? error.message : 'Đã xảy ra lỗi không xác định.';
}

interface FailedRequest {
  text: string;
  userMessageSaved: boolean;
}

export function usePersistentChat() {
  const [userId, setUserId] = useState('');
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [activeChatId, setActiveChatId] = useState('');
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [initializing, setInitializing] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [failedRequest, setFailedRequest] = useState<FailedRequest | null>(null);
  const creatingFirstChat = useRef(false);
  const activeChatIdRef = useRef('');

  useEffect(() => {
    activeChatIdRef.current = activeChatId;
  }, [activeChatId]);

  const createChat = useCallback(async (uid: string): Promise<string> => {
    const chat = await chatRepository.createChat(uid);
    activeChatIdRef.current = chat.id;
    setActiveChatId(chat.id);
    setMessages([]);
    setFailedRequest(null);
    try {
      await assistantService.ensureSession(uid, chat.id);
    } catch (sessionError) {
      setError(errorMessage(sessionError));
    }
    return chat.id;
  }, []);

  useEffect(() => {
    let unsubscribeChats: (() => void) | undefined;
    let unsubscribeActiveChat: (() => void) | undefined;
    let cancelled = false;

    void getChatUserId()
      .then((chatUserId) => {
        if (cancelled) return;
        setUserId(chatUserId);
        unsubscribeActiveChat = chatRepository.subscribeActiveChat(
          chatUserId,
          (chatId) => {
            if (!cancelled && chatId) {
              activeChatIdRef.current = chatId;
              setActiveChatId(chatId);
            }
          },
          (subscriptionError) => setError(errorMessage(subscriptionError)),
        );
        unsubscribeChats = chatRepository.subscribeChats(
          chatUserId,
          (nextChats) => {
            if (cancelled) return;
            setChats(nextChats);
            setInitializing(false);

            if (nextChats.length === 0) {
              if (!creatingFirstChat.current) {
                creatingFirstChat.current = true;
                void createChat(chatUserId)
                  .catch((creationError) => setError(errorMessage(creationError)))
                  .finally(() => {
                    creatingFirstChat.current = false;
                  });
              }
              return;
            }

            const currentId = activeChatIdRef.current;
            const selectedId = nextChats.some((chat) => chat.id === currentId)
              ? currentId
              : nextChats[0].id;
            activeChatIdRef.current = selectedId;
            setActiveChatId(selectedId);
            if (selectedId !== currentId) {
              void chatRepository
                .setActiveChat(chatUserId, selectedId)
                .catch((selectionError) => setError(errorMessage(selectionError)));
            }
          },
          (subscriptionError) => {
            setError(errorMessage(subscriptionError));
            setInitializing(false);
          },
        );
      })
      .catch((initializationError) => {
        if (!cancelled) {
          setError(errorMessage(initializationError));
          setInitializing(false);
        }
      });

    return () => {
      cancelled = true;
      unsubscribeChats?.();
      unsubscribeActiveChat?.();
    };
  }, [createChat]);

  useEffect(() => {
    if (!userId || !activeChatId) return undefined;
    setMessagesLoading(true);
    setMessages([]);
    return chatRepository.subscribeMessages(
      userId,
      activeChatId,
      (nextMessages) => {
        setMessages(nextMessages);
        setMessagesLoading(false);
      },
      (subscriptionError) => {
        setError(errorMessage(subscriptionError));
        setMessagesLoading(false);
      },
    );
  }, [activeChatId, userId]);

  const selectChat = useCallback(
    (chatId: string) => {
      if (!userId || chatId === activeChatId) return;
      activeChatIdRef.current = chatId;
      setActiveChatId(chatId);
      setFailedRequest(null);
      setError('');
      void chatRepository
        .setActiveChat(userId, chatId)
        .catch((selectionError) => setError(errorMessage(selectionError)));
    },
    [activeChatId, userId],
  );

  const newChat = useCallback(async () => {
    if (!userId || sending) return;
    setError('');
    try {
      await createChat(userId);
    } catch (creationError) {
      setError(errorMessage(creationError));
    }
  }, [createChat, sending, userId]);

  const requestAnswer = useCallback(
    async (text: string, persistUserMessage: boolean): Promise<AssistantMessage | null> => {
      if (sending) return null;
      if (!userId) {
        setError('Chưa xác định được người dùng Firebase. Vui lòng tải lại trang.');
        return null;
      }
      if (!activeChatId) {
        setError('Chưa thể tạo session chat trên Firestore. Vui lòng kiểm tra quyền truy cập Firebase.');
        return null;
      }
      setSending(true);
      setError('');
      setFailedRequest(null);
      let userMessageSaved = !persistUserMessage;

      try {
        if (persistUserMessage) {
          await chatRepository.saveMessage(userId, activeChatId, userMessage(text));
          userMessageSaved = true;
          const activeChat = chats.find((chat) => chat.id === activeChatId);
          if (activeChat?.title === chatRepository.defaultTitle) {
            await chatRepository.updateTitle(userId, activeChatId, text);
          }
        }
        const answer = await assistantService.send(userId, activeChatId, text);
        await chatRepository.saveMessage(userId, activeChatId, answer);
        return answer;
      } catch (sendError) {
        setFailedRequest({ text, userMessageSaved });
        setError(errorMessage(sendError));
        return null;
      } finally {
        setSending(false);
      }
    },
    [activeChatId, chats, sending, userId],
  );

  const send = useCallback(
    async (text: string) => requestAnswer(text.trim(), true),
    [requestAnswer],
  );
  const retry = useCallback(
    async () => failedRequest
      ? requestAnswer(failedRequest.text, !failedRequest.userMessageSaved)
      : null,
    [failedRequest, requestAnswer],
  );

  const visibleMessages = useMemo(
    () => (messages.length > 0 ? messages : [welcomeMessage]),
    [messages],
  );

  return {
    chats,
    activeChatId,
    messages: visibleMessages,
    initializing,
    messagesLoading,
    sending,
    error,
    canSend: Boolean(userId && activeChatId && !initializing),
    canRetry: Boolean(failedRequest),
    send,
    retry,
    newChat,
    selectChat,
  };
}
