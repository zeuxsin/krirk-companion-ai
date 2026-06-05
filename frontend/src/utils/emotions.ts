/**
 * utils/emotions.ts
 * Centraliza mapeamentos de emoção → imagem, cor e animação CSS.
 * Fonte única da verdade — usado por AvatarMode, HudMode, Sidebar, CompactHeader.
 */
import type { EmotionType, AIState } from '../types'

export const EMOTION_TO_IMG: Record<EmotionType, string> = {
  neutral:    'neutro',
  happy:      'animada',
  excited:    'surpresa',
  thoughtful: 'pensando',
  curious:    'curiosa',
  concerned:  'cansada',
  playful:    'animada',
  angry:      'irritada',
  confused:   'confusa',
}

export const EMOTION_COLOR: Record<EmotionType, string> = {
  neutral:    '#71717a',
  happy:      '#a78bfa',
  excited:    '#f59e0b',
  thoughtful: '#60a5fa',
  curious:    '#34d399',
  concerned:  '#f87171',
  playful:    '#fb923c',
  angry:      '#ef4444',
  confused:   '#c084fc',
}

/** Animação CSS aplicada ao avatar quando AIState === 'idle'. */
export const EMOTION_ANIM: Record<EmotionType, string> = {
  neutral:    'anim-float',         // balanço neutro padrão
  happy:      'anim-bounce',        // salto suave
  excited:    'anim-bounce-fast',   // salto rápido e alto
  thoughtful: 'anim-sway',          // balanço pensativo
  curious:    'anim-lean',          // inclina para frente
  concerned:  'anim-droop',         // desce pesado
  playful:    'anim-wiggle',        // balança de lado
  angry:      'anim-shake',         // tremida rápida
  confused:   'anim-wobble',        // oscila irregular
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
