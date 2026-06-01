import React from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { EmotionIndicator } from './components/EmotionIndicator'
import { ChatWindow } from './components/ChatWindow'

export default function App() {
  const { connected, aiState, emotion, sendMessage, sendAudio, onEvent } = useWebSocket()

  const aiStateBusy = aiState !== 'idle'

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: '#0f0f13',
    }}>
      <EmotionIndicator
        emotion={emotion}
        state={aiState}
        connected={connected}
      />
      <ChatWindow
        sendMessage={sendMessage}
        sendAudio={sendAudio}
        onEvent={onEvent}
        connected={connected}
        aiStateBusy={aiStateBusy}
      />
    </div>
  )
}
