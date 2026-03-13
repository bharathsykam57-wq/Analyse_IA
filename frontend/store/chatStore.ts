import { create } from 'zustand'
import { ChatMessage } from '@/types'

function generateId(): string {
  return Math.random().toString(36).slice(2, 11)
}

interface ChatStore {
  messages: ChatMessage[]
  language: 'fr' | 'en'
  isProcessing: boolean
  currentTaskId: string | null
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => string
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void
  appendToMessage: (id: string, chunk: string) => void
  setLanguage: (lang: 'fr' | 'en') => void
  setProcessing: (value: boolean) => void
  setCurrentTaskId: (id: string | null) => void
  clearMessages: () => void
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  language: 'fr',
  isProcessing: false,
  currentTaskId: null,
  addMessage: (message) => {
    const id = generateId()
    set((state) => ({
      messages: [...state.messages, { ...message, id, timestamp: new Date() }],
    }))
    return id
  },
  updateMessage: (id, updates) =>
    set((state) => ({
      messages: state.messages.map((m) => m.id === id ? { ...m, ...updates } : m),
    })),
  appendToMessage: (id, chunk) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, content: m.content + chunk } : m
      ),
    })),
  setLanguage: (language) => set({ language }),
  setProcessing: (value) => set({ isProcessing: value }),
  setCurrentTaskId: (id) => set({ currentTaskId: id }),
  clearMessages: () => set({ messages: [] }),
}))
