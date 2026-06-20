/**
 * utils/emotions.ts
 * Centraliza mapeamentos de emoção → imagem, cor e animação CSS.
 * Fonte única da verdade — usado por AvatarMode, HudMode, Sidebar, CompactHeader.
 */
import type { EmotionType, AIState } from '../types'

// Legado: nomes em inglês (ou variante neutra) que o backend pode ainda retornar
const LEGACY_MAP: Record<string, EmotionType> = {
  neutral:    'neutro',
  neutra:     'neutro',
  happy:      'feliz',
  excited:    'empolgada',
  thoughtful: 'pensando',
  curious:    'curiosa',
  concerned:  'cansada',
  playful:    'feliz',
  angry:      'irritada',
  confused:   'confusa',
  animada:    'empolgada',
}

/** Normaliza emoção recebida do backend para EmotionType canônico. */
export function normalizeEmotion(e: string): EmotionType {
  return (LEGACY_MAP[e] ?? e) as EmotionType
}

// Todas as 20 emoções mapeiam diretamente para o próprio nome de arquivo
export const EMOTION_TO_IMG: Record<EmotionType, string> = {
  neutro:       'neutro',
  surpresa:     'surpresa',
  pensando:     'pensando',
  curiosa:      'curiosa',
  cansada:      'cansada',
  irritada:     'irritada',
  confusa:      'confusa',
  feliz:        'feliz',
  empolgada:    'empolgada',
  triste:       'triste',
  zangada:      'zangada',
  assustada:    'assustada',
  envergonhada: 'envergonhada',
  timida:       'timida',
  concentrada:  'concentrada',
  orgulhosa:    'orgulhosa',
  determinada:  'determinada',
  codando:      'codando',
  jogando:      'jogando',
  tranquila:    'tranquila',
}

export const EMOTION_COLOR: Record<EmotionType, string> = {
  neutro:       '#71717a',
  feliz:        '#a78bfa',
  empolgada:    '#f59e0b',
  triste:       '#60a5fa',
  zangada:      '#ef4444',
  surpresa:     '#fbbf24',
  assustada:    '#f87171',
  envergonhada: '#fb7185',
  timida:       '#e879f9',
  irritada:     '#f97316',
  curiosa:      '#34d399',
  concentrada:  '#38bdf8',
  orgulhosa:    '#a3e635',
  cansada:      '#94a3b8',
  determinada:  '#fb923c',
  codando:      '#4ade80',
  jogando:      '#f472b6',
  tranquila:    '#67e8f9',
  pensando:     '#60a5fa',
  confusa:      '#c084fc',
}

/** Animação CSS aplicada ao avatar quando AIState === 'idle'. */
export const EMOTION_ANIM: Record<EmotionType, string> = {
  neutro:       'anim-float',
  feliz:        'anim-bounce',
  empolgada:    'anim-bounce-fast',
  triste:       'anim-droop',
  zangada:      'anim-shake',
  surpresa:     'anim-wobble',
  assustada:    'anim-shake',
  envergonhada: 'anim-sway',
  timida:       'anim-sway',
  irritada:     'anim-shake',
  curiosa:      'anim-lean',
  concentrada:  'anim-sway',
  orgulhosa:    'anim-float',
  cansada:      'anim-droop',
  determinada:  'anim-bounce',
  codando:      'anim-sway',
  jogando:      'anim-wiggle',
  tranquila:    'anim-float',
  pensando:     'anim-sway',
  confusa:      'anim-wobble',
}

/**
 * Animação por AIState — tem prioridade sobre EMOTION_ANIM quando não idle.
 * Em idle, usa EMOTION_ANIM para personalidade por emoção.
 */
export const ANIM_BY_STATE: Record<AIState, string | null> = {
  idle:      null,             // usa EMOTION_ANIM
  speaking:  'anim-float-fast',
  thinking:  'anim-sway',
  listening: 'anim-pulse',
  executing: '',
}

/** Retorna a classe CSS de animação correta para o avatar. */
export function avatarAnimClass(aiState: AIState, emotion: EmotionType): string {
  const stateAnim = ANIM_BY_STATE[aiState]
  if (stateAnim !== null) return stateAnim
  return EMOTION_ANIM[emotion] ?? 'anim-float'
}

/** Retorna o src da imagem PNG do avatar para uma emoção (pasta /avatar/). */
export function avatarSrc(emotion: EmotionType): string {
  return `/avatar/${EMOTION_TO_IMG[emotion] ?? 'neutro'}.png`
}

/** Retorna o src SVG de fallback. */
export function avatarFallback(emotion: EmotionType): string {
  return `/avatar/${EMOTION_TO_IMG[emotion] ?? 'neutro'}.svg`
}

/**
 * Retorna src do avatar de chat (pasta /avatar/chat/).
 * Usa os mesmos filenames do EMOTION_TO_IMG.
 * Fallback via onError no componente: /avatar/chat/neutro.png
 */
export function avatarChatSrc(emotion: EmotionType): string {
  return `/avatar/chat/${EMOTION_TO_IMG[emotion] ?? 'neutro'}.png`
}
