/**
 * bookData.ts — single source of truth for "AI Search Engineering".
 *
 * Every surface that links the book (homepage trust section, /about/, /book/,
 * footer) builds its URLs from here, so the attribution parameter is set in one
 * place instead of being pasted into each link.
 *
 * On tracking, so the next person does not re-learn it the hard way:
 * UTM parameters are read by the analytics of the DESTINATION site. Amazon does
 * not run our GA4, so UTMs on an Amazon URL tell us nothing about sales — they
 * are only useful for reading our own outbound logs. Sales attribution requires
 * either an Amazon Associates tracking id (`tag=`) or an Amazon Attribution tag.
 * Set AMAZON_TRACKING_ID below once that account exists and every link inherits it.
 */

/** Amazon Associates / Attribution id. Empty until the account is set up. */
const AMAZON_TRACKING_ID = '';

export const BOOK = {
  title: 'AI Search Engineering',
  subtitle:
    'A Technical Guide to Generative Engine Optimization (GEO), AI Citations, and Agent-Ready Websites',
  author: 'Juan Camilo Auriti',
  datePublished: '2026-09-10',
  inLanguage: 'en',
  numberOfPages: 992,
  isbn: '9798172934568',
  isbnFormatted: '979-8172934568',
  asinKindle: 'B0H8K319JM',
  asinPaperback: 'B0HJGLW5NP',
  /** Marketplace the ASINs were published on. */
  amazonHost: 'www.amazon.it',
} as const;

export type BookFormat = 'kindle' | 'paperback';

/**
 * Builds the Amazon URL for a format.
 *
 * @param format  which edition to link
 * @param content utm_content, to tell apart which surface produced the click
 */
export function amazonUrl(format: BookFormat, content: string): string {
  const asin = format === 'kindle' ? BOOK.asinKindle : BOOK.asinPaperback;
  const url = new URL(`https://${BOOK.amazonHost}/dp/${asin}`);

  // Sales attribution (the only parameter Amazon itself acts on).
  if (AMAZON_TRACKING_ID) url.searchParams.set('tag', AMAZON_TRACKING_ID);

  // Our own outbound bookkeeping; Amazon ignores these.
  url.searchParams.set('utm_source', 'geoready.dev');
  url.searchParams.set('utm_medium', 'referral');
  url.searchParams.set('utm_campaign', 'ai-search-engineering-book');
  url.searchParams.set('utm_content', content);

  return url.toString();
}

/** Canonical page for the book on this site. */
export const BOOK_PAGE = '/book/';
