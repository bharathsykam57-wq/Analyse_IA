import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ['class'],
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './node_modules/@tremor/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: '#0F1F3D', dark: '#0A1628', medium: '#1B3A6B', light: '#243B6E' },
        accent: { DEFAULT: '#2563EB', light: '#3B82F6', dark: '#1D4ED8' },
        success: '#059669', warning: '#D97706', danger: '#DC2626',
        tremor: {
          brand: { faint: '#0B1A33', muted: '#1B3A6B', subtle: '#2563EB', DEFAULT: '#2563EB', emphasis: '#3B82F6', inverted: '#ffffff' },
          background: { muted: '#0A1628', subtle: '#0F1F3D', DEFAULT: '#1B3A6B', emphasis: '#243B6E' },
          border: { DEFAULT: '#243B6E' },
          ring: { DEFAULT: '#2563EB' },
          content: { subtle: '#6B8BB8', DEFAULT: '#A3BFE8', emphasis: '#D0E4FF', strong: '#E8F0FB', inverted: '#ffffff' },
        },
      },
      animation: {
        'slide-up': 'slideUp 0.3s ease-out',
        'fade-in': 'fadeIn 0.4s ease-out',
      },
      keyframes: {
        slideUp: { '0%': { transform: 'translateY(10px)', opacity: '0' }, '100%': { transform: 'translateY(0)', opacity: '1' } },
        fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
      },
    },
  },
  safelist: [
    { pattern: /^(bg|text|border|ring|stroke|fill)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950)$/, variants: ['hover', 'ui-selected'] },
  ],
  plugins: [],
}
export default config
