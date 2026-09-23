export const TIER_A_MODELS = ['transformer', 'autoformer', 'itransformer', 'patchtst', 'timemixer'] as const
export type TierAModel = typeof TIER_A_MODELS[number]

export function exportTierASvg(model: TierAModel) {
  const svg = document.querySelector<SVGSVGElement>('.tier-a-svg')
  if (!svg) return
  const copy = svg.cloneNode(true) as SVGSVGElement
  const originals = svg.querySelectorAll<SVGElement>('rect, circle, path, text')
  const clones = copy.querySelectorAll<SVGElement>('rect, circle, path, text')
  originals.forEach((element, index) => {
    const computed = window.getComputedStyle(element)
    const target = clones[index]
    for (const property of ['fill', 'stroke', 'stroke-width', 'stroke-dasharray', 'opacity', 'font-family', 'font-size', 'font-weight']) {
      target.style.setProperty(property, computed.getPropertyValue(property))
    }
  })
  const text = new XMLSerializer().serializeToString(copy)
  const url = URL.createObjectURL(new Blob([text], { type: 'image/svg+xml;charset=utf-8' }))
  const link = document.createElement('a')
  link.download = `archcanvas-${model}-architecture.svg`
  link.href = url
  link.click()
  URL.revokeObjectURL(url)
}
