/** Numbers the components need in script (charts, motion); CSS sizes live in tokens.css. */
export const chart = {
  width: 760,
  rowHeight: 64,
  pad: { top: 28, right: 32, bottom: 48, left: 220 },
  dot: 7,
  ciStroke: 3,
} as const;

export const calibrationChart = { size: 300, pad: 40, dot: 4 } as const;

export const motionTokens = {
  reveal: { duration: 0.65, ease: [0.22, 1, 0.36, 1] as const },
  stagger: 0.09,
  change: { duration: 0.25 },
} as const;

export const z95 = 1.96;
