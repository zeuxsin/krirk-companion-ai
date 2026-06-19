/**
 * utils/emotions.ts
 * Centraliza mapeamentos de emoção → imagem, cor e animação CSS.
 * Fonte única da verdade — usado por AvatarMode, HudMode, Sidebar, CompactHeader.
 */
import type { EmotionType, AIState } from '../types'

export const EMOTION_TO_IMG: Record<EmotionType, string> = {
  // Emoções originais (inglês)
  neutral:       'neutro',
  happy:         'animada',
  excited:       'surpresa',
  thoughtful:    'pensando',
  curious:       'curiosa',
  concerned:     'cansada',
  playful:       'animada',
  angry:         'irritada',
  confused:      'confusa',
  // Emoções expandidas (português) — fallback para neutra enquanto imagens não existem
  neutra:        'neutra',
  feliz:         'feliz',
  empolgada:     'empolgada',
  triste:        'triste',
  zangada:       'zangada',
  surpresa:      'surpresa',
  assustada:     'assustada',
  envergonhada:  'envergonhada',
  timida:        'timida',
  irritada:      'irritada',
  curiosa:       'curiosa',
  concentrada:   'concentrada',
  orgulhosa:     'orgulhosa',
  cansada:       'cansada',
  determinada:   'determinada',
  codando:       'codando',
  jogando:       'jogando',
  tranquila:     'tranquila',
}

export const EMOTION_COLOR: Record<EmotionType, string> = {
  // Originais
  neutral:       '#71717a',
  happy:         '#a78bfa',
  excited:       '#f59e0b',
  thoughtful:    '#60a5fa',
  curious:       '#34d399',
  concerned:     '#f87171',
  playful:       '#fb923c',
  angry:         '#ef4444',
  confused:      '#c084fc',
  // Expandidas
  neutra:        '#71717a',
  feliz:         '#a78bfa',
  empolgada:     '#f59e0b',
  triste:        '#60a5fa',
  zangada:       '#ef4444',
  surpresa:      '#fbbf24',
  assustada:     '#f87171',
  envergonhada:  '#fb7185',
  timida:        '#e879f9',
  irritada:      '#f97316',
  curiosa:       '#34d399',
  concentrada:   '#38bdf8',
  orgulhosa:     '#a3e635',
  cansada:       '#94a3b8',
  determinada:   '#fb923c',
  codando:       '#4ade80',
  jogando:       '#f472b6',
  tranquila:     '#67e8f9',
}

/** Animação CSS aplicada ao avatar quando AIState === 'idle'. */
export const EMOTION_ANIM: Record<EmotionType, string> = {
  // Originais
  neutral:       'anim-float',
  happy:         'anim-bounce',
  excited:       'anim-bounce-fast',
  thoughtful:    'anim-sway',
  curious:       'anim-lean',
  concerned:     'anim-droop',
  playful:       'anim-wiggle',
  angry:         'anim-shake',
  confused:      'anim-wobble',
  // Expandidas
  neutra:        'anim-float',
  feliz:         'anim-bounce',
  empolgada:     'anim-bounce-fast',
  triste:        'anim-droop',
  zangada:       'anim-shake',
  surpresa:      'anim-wobble',
  assustada:     'anim-shake',
  envergonhada:  'anim-sway',
  timida:        'anim-sway',
  irritada:      'anim-shake',
  curiosa:       'anim-lean',
  concentrada:   'anim-sway',
  orgulhosa:     'anim-float',
  cansada:       'anim-droop',
  determinada:   'anim-bounce',
  codando:       'anim-sway',
  jogando:       'anim-wiggle',
  tranquila:     'anim-float',
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

/** Retorna o src da imagem PNG do avatar para uma emoção. */
export function avatarSrc(emotion: EmotionType): string {
  return `/avatar/${EMOTION_TO_IMG[emotion] ?? 'neutro'}.png`
}

/** Retorna o src SVG de fallback. */
export function avatarFallback(emotion: EmotionType): string {
  return `/avatar/${EMOTION_TO_IMG[emotion] ?? 'neutro'}.svg`
}

/**
 * Retorna src do avatar de chat (pasta separada /avatar/chat/).
 * Ordem de prioridade: /avatar/chat/{nome}.png → /avatar/{nome}.png → /avatar/neutra.png
 * O componente AvatarChatImg trata o fallback com onError.
 */
export function avatarChatSrc(emotion: EmotionType): string {
  const name = EMOTION_TO_IMG[emotion] ?? 'neutra'
  return `/avatar/chat/${name}.png`
}
