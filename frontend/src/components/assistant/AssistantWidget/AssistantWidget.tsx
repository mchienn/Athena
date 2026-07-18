import { FormEvent, useEffect, useRef, useState } from 'react';
import { Bot, LoaderCircle, MessageCircle, Mic, RefreshCw, Send, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { usePersistentChat } from '../../../hooks/usePersistentChat';
import { ChatToolbar } from '../ChatToolbar';
import { StructuredMessage } from '../messages/StructuredMessage';
import styles from './AssistantWidget.module.css';

export function AssistantWidget() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const messagesRef = useRef<HTMLDivElement>(null);
  const chat = usePersistentChat();

  useEffect(() => {
    if (!open) return;
    const container = messagesRef.current;
    container?.scrollTo({ top: container.scrollHeight, behavior: 'auto' });
  }, [chat.messages, chat.sending, open]);

  const send = async (event?: FormEvent) => {
    event?.preventDefault();
    const value = input.trim();
    if (!value || chat.sending || !chat.canSend) return;
    const answer = await chat.send(value);
    if (answer) {
      setInput('');
      const href = answer.actions.find((action) => action.id === 'open-booking-page')?.href;
      if (href) {
        const destination = new URL(href, window.location.origin);
        if (destination.origin === window.location.origin) {
          navigate(`${destination.pathname}${destination.search}${destination.hash}`);
        } else {
          window.location.assign(destination.href);
        }
      }
    }
    inputRef.current?.focus();
  };

  return (
    <div className={styles.root}>
      {open && (
        <section className={styles.panel} aria-label="Trợ lý AI">
          <header>
            <div>
              <Bot size={22} />
              <span>
                <strong>Trợ lý Tim Hà Nội</strong>
                <small>Lịch sử được đồng bộ với trang đặt lịch</small>
              </span>
            </div>
            <button onClick={() => setOpen(false)} aria-label="Đóng trợ lý"><X size={20} /></button>
          </header>

          <ChatToolbar
            chats={chat.chats}
            activeChatId={chat.activeChatId}
            disabled={chat.initializing || chat.sending}
            onSelect={chat.selectChat}
            onNewChat={() => void chat.newChat()}
          />

          <div ref={messagesRef} className={styles.messages} aria-live="polite">
            {chat.messages.map((message) => (
              <article key={message.id} className={message.role === 'user' ? styles.user : styles.assistant}>
                {message.role === 'assistant' && <Bot size={17} />}
                <div>
                  {message.role === 'assistant' ? <StructuredMessage message={message} /> : <p>{message.answer}</p>}
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
            {['Tìm bác sĩ', 'Lịch khám gần nhất', 'Chuyên khoa phù hợp'].map((text) => (
              <button key={text} onClick={() => setInput(text)}>{text}</button>
            ))}
          </div>

          <form onSubmit={(event) => void send(event)}>
            <label className="sr-only" htmlFor="assistant-input">Nhập câu hỏi</label>
            <input
              ref={inputRef}
              id="assistant-input"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Bạn cần hỗ trợ gì?"
              disabled={chat.initializing}
            />
            <button className={styles.micButton} type="button" aria-label="Nhập bằng giọng nói (sắp có)">
              <Mic size={18} />
            </button>
            <button
              type="submit"
              disabled={!input.trim() || chat.sending || !chat.canSend}
              aria-label="Gửi tin nhắn"
            >
              <Send size={18} />
            </button>
          </form>
        </section>
      )}
      <button
        className={styles.fab}
        onClick={() => setOpen((value) => !value)}
        aria-label={open ? 'Đóng trợ lý AI' : 'Mở trợ lý AI'}
      >
        {open ? <X /> : <MessageCircle />}
      </button>
    </div>
  );
}
