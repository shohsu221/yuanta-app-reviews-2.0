/** @type {import('tailwindcss').Config} */
// Build input for replacing the Tailwind Play CDN with a static stylesheet.
// Scans BOTH the dashboard HTML and the server-rendered expert tab (expert.js)
// so no class used on the password-gated tab gets purged.
module.exports = {
  content: [
    './Yuanta_Reviews_Dashboard.html',
    './functions/api/expert.js',
  ],
  // Classes added at runtime via classList/className concatenation. They already
  // appear as literals in source (so the scanner finds them), but we pin them
  // here as belt-and-suspenders against future edits.
  safelist: [
    'hidden', 'scale-100', 'scale-95', 'opacity-0', 'opacity-100',
    'text-gray-400', 'hover:text-gray-200',
    'bg-blue-500/20', 'text-blue-400', 'border-blue-500/30',
  ],
  theme: { extend: {} },
  plugins: [],
};
