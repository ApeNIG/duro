import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Backgrounds - Terminal Austere (single deep black)
        'bg-void': '#050708',
        'bg-panel': '#050708',
        'bg-card': '#050708',
        'bg-elevated': '#0a0d10',
        'bg-active': '#0f1318',

        // Legacy compatibility
        page: '#050708',
        sidebar: '#050708',
        card: '#050708',

        // Single accent - cyan only (restraint principle)
        accent: '#00FFE5',
        'accent-dim': 'rgba(0, 255, 229, 0.08)',

        // Type tags - semantic colors only
        'tag-fact': '#00FFE5',
        'tag-decision': '#B14EFF',
        'tag-episode': '#FF6B00',
        'tag-audit': '#FF2D55',
        'tag-skill': '#39FF14',

        // Semantic
        error: '#FF2D55',
        warning: '#FF6B00',
        success: '#00FFE5',

        // Text - high contrast, minimal palette
        'text-primary': '#e2e8f0',
        'text-secondary': '#8a9199',
        'text-muted': '#4a5568',
        'text-dim': '#2d3748',

        // Borders - visible, structural
        border: '#1a1f26',
        'border-active': 'rgba(0, 255, 229, 0.3)',

        // Legacy neon colors (for type tags)
        'neon-cyan': '#00FFE5',
        'neon-purple': '#B14EFF',
        'neon-green': '#39FF14',
        'neon-orange': '#FF6B00',
        'neon-red': '#FF2D55',

        // Glass (not used in Terminal Austere)
        'glass-border': '#1a1f26',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
        display: ['Space Grotesk', 'system-ui', 'sans-serif'],
        data: ['Orbitron', 'Share Tech Mono', 'monospace'],
      },
      backdropBlur: {
        glass: '20px',
      },
      boxShadow: {
        'glass-glow': '0 0 30px rgba(0, 255, 229, 0.1)',
        'neon-cyan': '0 0 20px rgba(0, 255, 229, 0.3)',
        'neon-magenta': '0 0 20px rgba(255, 0, 255, 0.3)',
        'neon-blue': '0 0 20px rgba(0, 168, 255, 0.3)',
        'neon-purple': '0 0 20px rgba(177, 78, 255, 0.3)',
        'neon-green': '0 0 20px rgba(57, 255, 20, 0.3)',
        'neon-red': '0 0 20px rgba(255, 45, 85, 0.3)',
        card: '0 4px 24px rgba(0, 0, 0, 0.5)',
        'card-hover': '0 8px 32px rgba(0, 0, 0, 0.6), 0 0 20px rgba(0, 255, 229, 0.1)',
      },
      animation: {
        pulse: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'slide-down': 'slideDown 0.4s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
        'scan-line': 'scanLine 4s linear infinite',
        'data-stream': 'dataStream 2s linear infinite',
        'border-glow': 'borderGlow 3s ease-in-out infinite',
        float: 'float 6s ease-in-out infinite',
        shimmer: 'shimmer 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(-4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 4px var(--neon-cyan, #00FFE5)' },
          '50%': { boxShadow: '0 0 20px var(--neon-cyan, #00FFE5)' },
        },
        scanLine: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
        dataStream: {
          '0%': { backgroundPosition: '0% 0%' },
          '100%': { backgroundPosition: '0% 100%' },
        },
        borderGlow: {
          '0%, 100%': { borderColor: 'rgba(0, 255, 229, 0.15)' },
          '50%': { borderColor: 'rgba(0, 255, 229, 0.4)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      backgroundImage: {
        'grid-pattern': `linear-gradient(rgba(0, 255, 229, 0.03) 1px, transparent 1px),
                         linear-gradient(90deg, rgba(0, 255, 229, 0.03) 1px, transparent 1px)`,
        'gradient-radial': 'radial-gradient(circle, var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(var(--tw-gradient-stops))',
        'shimmer-gradient': 'linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent)',
      },
      backgroundSize: {
        grid: '50px 50px',
      },
    },
  },
  plugins: [],
} satisfies Config
