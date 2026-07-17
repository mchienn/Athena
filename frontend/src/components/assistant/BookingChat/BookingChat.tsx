import { FormEvent, useEffect, useRef, useState } from 'react';
import { Bot, LoaderCircle, Mic, RefreshCw, Send } from 'lucide-react';
import { usePersistentChat } from '../../../hooks/usePersistentChat';
import { ChatToolbar } from '../ChatToolbar';
import { StructuredMessage } from '../messages/StructuredMessage';
import styles from './BookingChat.module.css';

export function BookingChat() {
  const [input, setInput] = useState('');
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const chat = usePersistentChat();

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    container.scrollTo({ top: container.scrollHeight, behavior: 'auto' });
  }, [chat.messages, chat.sending]);

  const sendMessage = async (event?: FormEvent) => {
    event?.preventDefault();
    const content = input.trim();
    if (!content || chat.sending || !chat.canSend) return;
    const sent = await chat.send(content);
    if (sent) setInput('');
  };

  return (
    <section className={styles.chat} aria-label="Trợ lý hỗ trợ đặt lịch">
      <header className={styles.header}>
        <span className={styles.botIcon}><Bot size={22} /></span>
        <div>
          <h2>Trợ lý Tim Hà Nội</h2>
          <p>Lịch sử được lưu theo người dùng</p>
        </div>
        <span className={styles.status}>Trực tuyến</span>
      </header>

      <ChatToolbar
        chats={chat.chats}
        activeChatId={chat.activeChatId}
        disabled={chat.initializing || chat.sending}
        onSelect={chat.selectChat}
        onNewChat={() => void chat.newChat()}
      />

      <div ref={messagesContainerRef} className={styles.messages} aria-live="polite">
        {chat.messages.map((message) => (
          <article
            key={message.id}
            className={message.role === 'user' ? styles.user : styles.assistant}
          >
            {message.role === 'assistant' && <Bot size={18} />}
            <div>
              {message.role === 'assistant' ? (
                <StructuredMessage message={message} />
              ) : (
                <p>{message.answer}</p>
              )}
            </div>
          </article>
        ))}

        {(chat.initializing || chat.messagesLoading || chat.sending) && (
          <div className={styles.loading}>
            <LoaderCircle size={18} />
            {chat.sending ? 'Đang nhận phản hồi...' : 'Đang tải lịch sử...'}
          </div>
        )}

        {chat.error && <div className={styles.error} role="alert">{chat.error}</div>}

        {chat.canRetry && (
          <button className={styles.retry} onClick={() => void chat.retry()}>
            <RefreshCw size={16} /> Thử gửi lại
          </button>
        )}
      </div>

      <div className={styles.suggestions}>
        {['Tôi nên chọn chuyên khoa nào?', 'Tìm bác sĩ phù hợp', 'Lịch khám gần nhất'].map(
          (suggestion) => (
            <button key={suggestion} onClick={() => setInput(suggestion)}>
              {suggestion}
            </button>
          ),
        )}
      </div>

      <form className={styles.composer} onSubmit={(event) => void sendMessage(event)}>
        <label className="sr-only" htmlFor="booking-chat-input">Nhập câu hỏi cho trợ lý</label>
        <input
          id="booking-chat-input"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Nhập câu hỏi của bạn..."
          disabled={chat.initializing}
        />
        <button
          className={styles.micButton}
          type="button"
          aria-label="Nhập câu hỏi bằng giọng nói (sắp có)"
          title="Nhập bằng giọng nói — sắp có"
        >
          <Mic size={18} />
        </button>
        <button
          className={styles.sendButton}
          type="submit"
          disabled={!input.trim() || chat.sending || !chat.canSend}
          aria-label="Gửi tin nhắn"
        >
          <Send size={18} />
        </button>
      </form>
    </section>
  );
}
