import { Plus } from 'lucide-react';
import type { ChatSummary } from '../../../types';
import styles from './ChatToolbar.module.css';

interface ChatToolbarProps {
  chats: ChatSummary[];
  activeChatId: string;
  disabled?: boolean;
  onSelect: (chatId: string) => void;
  onNewChat: () => void;
}

export function ChatToolbar({
  chats,
  activeChatId,
  disabled = false,
  onSelect,
  onNewChat,
}: ChatToolbarProps) {
  return (
    <div className={styles.toolbar}>
      <label className="sr-only" htmlFor={`chat-history-${activeChatId || 'loading'}`}>
        Lịch sử trò chuyện
      </label>
      <select
        id={`chat-history-${activeChatId || 'loading'}`}
        value={activeChatId}
        disabled={disabled || chats.length === 0}
        onChange={(event) => onSelect(event.target.value)}
        aria-label="Chọn cuộc trò chuyện"
      >
        {chats.length === 0 && <option value="">Đang tải lịch sử...</option>}
        {chats.map((chat) => (
          <option key={chat.id} value={chat.id}>
            {chat.title}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={onNewChat}
        disabled={disabled}
        aria-label="Tạo đoạn chat mới"
        title="Tạo đoạn chat mới"
      >
        <Plus size={17} />
        <span>Chat mới</span>
      </button>
    </div>
  );
}
