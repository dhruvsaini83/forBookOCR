/**
 * Universal clipboard utility with automatic fallback.
 * 
 * In non-secure contexts (e.g. accessing via local LAN IP http://192.168.x.x:5173,
 * iframe, or older browsers), `navigator.clipboard` is undefined.
 * 
 * This helper tries the modern Async Clipboard API first, and seamlessly falls back
 * to standard DOM `document.execCommand('copy')` with a temporary textarea.
 */

export async function copyToClipboard(text: string): Promise<boolean> {
  if (!text) return false;

  // 1. Try modern navigator.clipboard (available in secure contexts: HTTPS & localhost)
  if (typeof navigator !== 'undefined' && navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      console.warn('navigator.clipboard.writeText failed, attempting execCommand fallback:', err);
    }
  }

  // 2. Legacy fallback for non-secure contexts (HTTP, LAN IPs, webviews)
  if (typeof document !== 'undefined') {
    try {
      const textArea = document.createElement('textarea');
      textArea.value = text;

      // Prevent scrolling & visual jump
      textArea.style.position = 'fixed';
      textArea.style.top = '0';
      textArea.style.left = '0';
      textArea.style.width = '2em';
      textArea.style.height = '2em';
      textArea.style.padding = '0';
      textArea.style.border = 'none';
      textArea.style.outline = 'none';
      textArea.style.boxShadow = 'none';
      textArea.style.background = 'transparent';
      textArea.style.opacity = '0';
      textArea.setAttribute('readonly', '');

      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      textArea.setSelectionRange(0, text.length);

      const successful = document.execCommand('copy');
      document.body.removeChild(textArea);

      if (successful) {
        return true;
      }
    } catch (fallbackErr) {
      console.error('execCommand copy fallback failed:', fallbackErr);
    }
  }

  return false;
}

