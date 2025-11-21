interface Conversation {
  id: string;
  name: string;
  lastMessage?: string;
  unread?: number;
}

interface ConversationsListProps {
  conversations: Conversation[];
  selectedId: string;
  onSelect: (id: string) => void;
}

export function ConversationsList({ conversations, selectedId, onSelect }: ConversationsListProps) {
  return (
    <div className="h-full flex flex-col bg-white dark:bg-gray-900">
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Conversations</h2>
      </div>
      
      <div className="flex-1 overflow-y-auto">
        {conversations.map((conv) => (
          <button
            key={conv.id}
            onClick={() => onSelect(conv.id)}
            className={`w-full px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800 border-b border-gray-100 dark:border-gray-800 transition-colors ${
              selectedId === conv.id ? 'bg-gray-100 dark:bg-gray-800' : ''
            }`}
          >
            <div className="flex items-center justify-between">
              <h3 className="font-medium text-gray-900 dark:text-white text-sm">
                {conv.name}
              </h3>
              {conv.unread && conv.unread > 0 && (
                <span className="bg-[#76B900] text-white text-xs rounded-full px-2 py-0.5 min-w-[20px] text-center">
                  {conv.unread}
                </span>
              )}
            </div>
            {conv.lastMessage && (
              <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-1">
                {conv.lastMessage}
              </p>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

