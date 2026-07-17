import { FormEvent, useEffect, useRef, useState } from 'react';
import { Bot, LoaderCircle, Mic, RefreshCw, Send } from 'lucide-react';
import { assistantService } from '../../../services';
import type { AssistantMessage } from '../../../types';
import { StructuredMessage } from '../messages/StructuredMessage';
import styles from './BookingChat.module.css';

const welcomeMessage: AssistantMessage = {
  id: 'booking-welcome',
  role: 'assistant',
  intent: 'general',
  answer:
    'Xin chào! Tôi có thể hỗ trợ bạn chọn chuyên khoa, bác sĩ và giải đáp thông tin trước khi đặt lịch.',
  actions: [],
  structured_data: {},
  emergency: false,
  citations: [],
};

export function BookingChat() {
  const [messages, setMessages] = useState<AssistantMessage[]>([welcomeMessage]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [failedMessage, setFailedMessage] = useState('');
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    container.scrollTo({
      top: container.scrollHeight,
      behavior: messages.length > 1 ? 'smooth' : 'auto',
    });
  }, [loading, messages]);

  const sendMessage = async (event?: FormEvent) => {
    event?.preventDefault();
    const content = (failedMessage || input).trim();
    if (!content || loading) return;

    setFailedMessage('');
    setInput('');
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        role: 'user',
        intent: 'general',
        answer: content,
        actions: [],
        structured_data: {},
        emergency: false,
        citations: [],
      },
    ]);
    setLoading(true);

    try {
      const response = await assistantService.send(content);
      setMessages((current) => [...current, response]);
    } catch {
      setFailedMessage(content);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className={styles.chat} aria-label="Trợ lý hỗ trợ đặt lịch">
      <header className={styles.header}>
        <span className={styles.botIcon}><Bot size={22} /></span>
        <div>
          <h2>Trợ lý Tim Hà Nội</h2>
          <p>Hỗ trợ lựa chọn trước khi đặt lịch</p>
        </div>
        <span className={styles.status}>Trực tuyến</span>
      </header>

      <div ref={messagesContainerRef} className={styles.messages} aria-live="polite">
        {messages.map((message) => (
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
        {loading && (
          <div className={styles.loading}>
            <LoaderCircle size={18} /> Đang tìm thông tin...
          </div>
        )}
        {failedMessage && (
          <button className={styles.retry} onClick={() => void sendMessage()}>
            <RefreshCw size={16} /> Không thể kết nối. Thử lại
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
        <label className="sr-only" htmlFor="booking-chat-input">
          Nhập câu hỏi cho trợ lý
        </label>
        <input
          id="booking-chat-input"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Nhập câu hỏi của bạn..."
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
          disabled={!input.trim() || loading}
          aria-label="Gửi tin nhắn"
        >
          <Send size={18} />
        </button>
      </form>
    </section>
  );
}
