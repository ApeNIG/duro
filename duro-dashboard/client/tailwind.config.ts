import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        page: '#0C0C0C',
        sidebar: '#080808',
        card: '#0A0A0A',
        accent: '#00FF88',
        'accent-dim': 'rgba(0, 255, 136, 0.125)',
        border: '#2f2f2f',
        error: '#FF4444',
        warning: '#FF8800',
        success: '#00FF88',
        'text-primary': '#FFFFFF',
        'text-secondary': '#8a8a8a',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
        display: ['Space Grotesk', 'system-ui', 'sans-serif'],
      },
      animation: {
        pulse: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(-4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
} satisfies Config
