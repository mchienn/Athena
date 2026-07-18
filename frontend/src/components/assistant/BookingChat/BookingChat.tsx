import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from 'react';
import { Bot, LoaderCircle, Mic, RefreshCw, Send } from 'lucide-react';
import { usePersistentChat } from '../../../hooks/usePersistentChat';
import { useAutoResizeTextarea } from '../../../hooks/useAutoResizeTextarea';
import { useSpeechToText } from '../../../hooks/useSpeechToText';
import { ChatToolbar } from '../ChatToolbar';
import { StructuredMessage } from '../messages/StructuredMessage';
import { VoiceInputOverlay } from '../VoiceInputOverlay';
import styles from './BookingChat.module.css';

export function BookingChat() {
  const [input, setInput] = useState('');
  const inputRef = useAutoResizeTextarea(input);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const chat = usePersistentChat();
  const speech = useSpeechToText({
    value: input,
    onChange: setInput,
    onSubmit: (value) => void submitMessage(value),
  });

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    container.scrollTo({ top: container.scrollHeight, behavior: 'auto' });
  }, [chat.messages, chat.sending]);

  async function submitMessage(value: string) {
    if (!value || chat.sending || !chat.canSend) return;
    setInput('');
    inputRef.current?.focus();
    await chat.send(value);
  }

  const sendMessage = async (event?: FormEvent) => {
    event?.preventDefault();
    const content = input.trim();
    if (!content || chat.sending || !chat.canSend) return;
    speech.stopListening(false);
    await submitMessage(content);
  };

  const handleInputKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    void sendMessage();
  };

  return (
    <section className={styles.chat} aria-label="Trợ lý hỗ trợ đặt lịch">
      {speech.listening && (
        <VoiceInputOverlay transcript={input} onStop={() => speech.stopListening(true)} />
      )}
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

      {speech.error && <p className={styles.voiceError} role="alert">{speech.error}</p>}

      <form className={styles.composer} onSubmit={(event) => void sendMessage(event)}>
        <label className="sr-only" htmlFor="booking-chat-input">Nhập câu hỏi cho trợ lý</label>
        <textarea
          ref={inputRef}
          id="booking-chat-input"
          rows={1}
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleInputKeyDown}
          placeholder="Nhập câu hỏi của bạn..."
          disabled={chat.initializing}
        />
        <button
          className={styles.micButton}
          type="button"
          onClick={speech.toggleListening}
          disabled={!speech.supported || chat.initializing}
          aria-label={speech.listening ? 'Dừng ghi âm' : 'Nhập bằng giọng nói'}
          aria-pressed={speech.listening}
          title={speech.supported ? (speech.listening ? 'Dừng ghi âm' : 'Nhập bằng giọng nói') : 'Trình duyệt không hỗ trợ nhận dạng giọng nói'}
          data-listening={speech.listening}
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
