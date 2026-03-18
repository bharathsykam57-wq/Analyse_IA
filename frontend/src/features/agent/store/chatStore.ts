import { create } from 'zustand';
import { ChatMessage } from '@/shared/types/agent';

interface ChatState {
  language: 'fr' | 'en';
  messages: ChatMessage[];
  isProcessing: boolean;
  currentTaskId: string | null;
  setLanguage: (lang: 'fr' | 'en') => void;
  addMessage: (msg: ChatMessage) => void;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  setIsProcessing: (isProcessing: boolean, taskId?: string | null) => void;
  clearMessages: () => void;
  removeLoading: () => void;
  setMessages: (messages: ChatMessage[]) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  language: 'fr',
  messages: [],
  isProcessing: false,
  currentTaskId: null,
  
  setLanguage: (language) => set({ language }),
  
  addMessage: (msg) => set((state) => ({ 
    messages: [...state.messages, msg] 
  })),
  
  updateMessage: (id, updates) => set((state) => ({
    messages: state.messages.map(msg => msg.id === id ? { ...msg, ...updates } : msg)
  })),
  
  setIsProcessing: (isProcessing, taskId = null) => set({ 
    isProcessing, 
    currentTaskId: taskId 
  }),
  
  clearMessages: () => set({ messages: [], isProcessing: false, currentTaskId: null }),
  
  removeLoading: () => set((state) => ({
    messages: state.messages.filter(m => !m.isPolling)
  })),
  
  setMessages: (messages) => set({ messages, isProcessing: false, currentTaskId: null })
}));
