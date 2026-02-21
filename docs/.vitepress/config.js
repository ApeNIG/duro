import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Duro',
  description: 'Memory layer for AI agents that compounds intelligence over time',

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/logo.svg' }],
    ['meta', { name: 'theme-color', content: '#10B981' }],
  ],

  themeConfig: {
    logo: '/logo.svg',

    nav: [
      { text: 'Guide', link: '/guide/getting-started' },
      { text: 'Reference', link: '/reference/tools' },
      { text: 'Concepts', link: '/concepts/memory' },
      {
        text: 'Resources',
        items: [
          { text: 'Cheat Sheet', link: '/guide/cheatsheet' },
          { text: 'Roadmap', link: '/about/roadmap' },
          { text: 'GitHub', link: 'https://github.com/ApeNIG/duro' }
        ]
      }
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Getting Started',
          items: [
            { text: 'Introduction', link: '/guide/introduction' },
            { text: 'Quick Start', link: '/guide/getting-started' },
            { text: 'Installation', link: '/guide/installation' },
            { text: 'Configuration', link: '/guide/configuration' }
          ]
        },
        {
          text: 'Core Workflows',
          items: [
            { text: 'Storing Knowledge', link: '/guide/storing-knowledge' },
            { text: 'Searching Memory', link: '/guide/searching' },
            { text: 'Validating Decisions', link: '/guide/validation' },
            { text: 'Debugging with Duro', link: '/guide/debugging' }
          ]
        },
        {
          text: 'Resources',
          items: [
            { text: 'Cheat Sheet', link: '/guide/cheatsheet' },
            { text: 'Troubleshooting', link: '/guide/troubleshooting' }
          ]
        }
      ],
      '/reference/': [
        {
          text: 'MCP Tools',
          items: [
            { text: 'Overview', link: '/reference/tools' },
            { text: 'Memory Tools', link: '/reference/memory-tools' },
            { text: 'Search Tools', link: '/reference/search-tools' },
            { text: 'Validation Tools', link: '/reference/validation-tools' },
            { text: 'Debug Tools', link: '/reference/debug-tools' },
            { text: 'System Tools', link: '/reference/system-tools' }
          ]
        },
        {
          text: 'Data Types',
          items: [
            { text: 'Artifacts', link: '/reference/artifacts' },
            { text: 'Facts', link: '/reference/facts' },
            { text: 'Decisions', link: '/reference/decisions' },
            { text: 'Episodes', link: '/reference/episodes' }
          ]
        }
      ],
      '/concepts/': [
        {
          text: 'Builder\'s Compass',
          items: [
            { text: 'Overview', link: '/concepts/builders-compass' },
            { text: 'Memory', link: '/concepts/memory' },
            { text: 'Verification', link: '/concepts/verification' },
            { text: 'Orchestration', link: '/concepts/orchestration' },
            { text: 'Expertise', link: '/concepts/expertise' }
          ]
        },
        {
          text: 'How It Works',
          items: [
            { text: 'Architecture', link: '/concepts/architecture' },
            { text: 'Confidence & Decay', link: '/concepts/confidence' },
            { text: 'Provenance', link: '/concepts/provenance' },
            { text: 'The 48-Hour Rule', link: '/concepts/48-hour-rule' }
          ]
        }
      ]
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/ApeNIG/duro' }
    ],

    footer: {
      message: 'Built by builders who don\'t want to ship nonsense.',
      copyright: 'MIT License'
    },

    search: {
      provider: 'local'
    },

    editLink: {
      pattern: 'https://github.com/ApeNIG/duro/edit/master/docs/:path',
      text: 'Edit this page on GitHub'
    }
  },

  markdown: {
    theme: {
      light: 'github-light',
      dark: 'github-dark'
    }
  }
})
