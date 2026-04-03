import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './pages/**/*.{js,ts,jsx,tsx}',
    './src/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#0066cc',
        secondary: '#666666',
        danger: '#dc3545',
        success: '#28a745',
      },
    },
  },
  plugins: [],
  corePlugins: {
    preflight: false,   // Don't override Bootstrap's base reset
    visibility: false,  // Prevent .collapse { visibility:collapse } overriding Bootstrap's .collapse
  },
}
export default config
