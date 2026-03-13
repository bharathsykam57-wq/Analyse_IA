const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

export class AgentWebSocket {
  private ws: WebSocket | null = null
  private taskId: string
  private onMessage: (chunk: string) => void
  private onComplete: (result: unknown) => void
  private onError: (error: string) => void
  // Flag so the polling fallback knows WS already finished
  public completed = false

  constructor(
    taskId: string,
    callbacks: {
      onMessage: (chunk: string) => void
      onComplete: (result: unknown) => void
      onError: (error: string) => void
    }
  ) {
    this.taskId = taskId
    this.onMessage = callbacks.onMessage
    this.onComplete = callbacks.onComplete
    this.onError = callbacks.onError
  }

  connect(): void {
    const token =
      typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
    const url = `${WS_URL}/ws/${this.taskId}${token ? `?token=${token}` : ''}`
    this.ws = new WebSocket(url)

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'chunk') {
          this.onMessage(data.content)
        } else if (data.type === 'complete') {
          this.completed = true
          this.onComplete(data.result)
          this.disconnect()
        } else if (data.type === 'error') {
          this.completed = true
          this.onError(data.message)
          this.disconnect()
        }
      } catch {
        // Raw string chunk (non-JSON) — treat as text
        this.onMessage(event.data)
      }
    }

    this.ws.onerror = () => {
      // WS failed — polling fallback will take over
      this.onError('WebSocket connection failed')
    }

    this.ws.onclose = () => {}
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}
